import os
import pandas as pd
import re
from itertools import combinations
from collections import defaultdict

from neo4j_utils import get_driver, get_neo4j_settings

# ── Config ────────────────────────────────────────────────────────────────────
EXCEL_FILE  = os.getenv("PSI_PROCESSED_FILE", "../data/papers_filtered.csv")
CLEAR_DB_ON_START = os.getenv("CLEAR_DB_ON_START", "true").lower() == "true"
BATCH_SIZE  = 500
# ─────────────────────────────────────────────────────────────────────────────


def split_semicolon_values(raw: str) -> list[str]:
    if pd.isna(raw) or str(raw).strip().lower() in ("nan", ""):
        return []
    return [item.strip() for item in str(raw).split(";") if item.strip()]


def normalize_name(name: str | None) -> str:
    return " ".join(str(name or "").split()).strip()


def parse_processed_nc_people(row) -> list[dict]:
    """
    Parse NC authors from the processed CSV.

    The `nc_authors` column is the source of truth for author identities used by
    the current Neo4j workflow.
    """
    names = split_semicolon_values(row.get("nc_authors", ""))

    people = []
    for name in names:
        canonical_name = normalize_name(name)
        if not canonical_name:
            continue

        people.append({
            "name": canonical_name,
        })

    if people:
        return people

    # Fallback for older files that may not have derived columns yet.
    raw_entries = split_semicolon_values(row.get("nc_state_people", ""))
    for entry in raw_entries:
        match = re.match(r"^\s*(.+?)\s*\((.*?)\)\s*$", entry)
        if match:
            canonical_name = normalize_name(match.group(1))
        else:
            canonical_name = normalize_name(re.sub(r"\s*\([A-Za-z0-9_.-]*\)\s*$", "", entry))

        if not canonical_name:
            continue

        people.append({
            "name": canonical_name,
        })

    return people


def parse_data(path):
    df = pd.read_csv(path)

    papers      = []
    author_info = defaultdict(lambda: {"paper_count": 0})
    coauth      = defaultdict(int)
    topics      = set()

    for _, row in df.iterrows():
        title    = str(row.get("title",  "")).strip()
        doi      = str(row.get("DOI",    "")).strip()
        year     = row.get("year", None)
        tops     = [t.strip() for t in str(row.get("topics", "")).split(";") if t.strip()]

        # ── NC State people only ──────────────────────────────────────────────
        nc_people = parse_processed_nc_people(row)
        if not nc_people:
            continue

        nc_names = [person["name"] for person in nc_people]

        papers.append({
            "title":   title,
            "doi":     doi,
            "year":    int(year) if pd.notna(year) else None,
            "authors": nc_names,
            "topics":  tops,
        })

        for person in nc_people:
            info = author_info[person["name"]]
            info["paper_count"] += 1

        for t in tops:
            topics.add(t)

        for a, b in combinations(sorted(set(nc_names)), 2):
            coauth[(a, b)] += 1

    return papers, author_info, coauth, topics


def summarize_author_identities(df, author_info):
    unique_nc_author_names = set()
    for _, row in df.iterrows():
        for name in split_semicolon_values(row.get("nc_authors", "")):
            canonical_name = normalize_name(name)
            if canonical_name:
                unique_nc_author_names.add(canonical_name)

    return {
        "unique_nc_author_names": len(unique_nc_author_names),
        "unique_loader_identities": len(author_info),
    }


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def load_to_neo4j(papers, author_info, coauth, topics):
    settings = get_neo4j_settings()
    driver = get_driver()

    with driver.session(database=settings["database"]) as session:
        try:
            if CLEAR_DB_ON_START:
                print("Clearing existing graph data …")
                session.run("MATCH (n) DETACH DELETE n")

            # ── Indexes for faster lookups ─────────────────────────────────────────
            print("Creating indexes …")
            session.run("CREATE INDEX author_name IF NOT EXISTS FOR (a:Author) ON (a.name)")
            session.run("CREATE INDEX paper_doi IF NOT EXISTS FOR (p:Paper) ON (p.doi)")
            session.run("CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)")

            # ── Author nodes ──────────────────────────────────────────────────────
            print(f"Loading {len(author_info):,} NC State author nodes …")
            author_rows = [
                {
                    "name": name,
                    "paper_count": info["paper_count"],
                }
                for name, info in author_info.items()
            ]
            for batch in chunks(author_rows, BATCH_SIZE):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (a:Author {name: row.name})
                    SET   a.paper_count = row.paper_count,
                          a.nc_state    = true
                    """,
                    rows=batch,
                )

            # ── Topic nodes ───────────────────────────────────────────────────────
            print(f"Loading {len(topics):,} topic nodes …")
            topic_rows = [{"name": t} for t in topics]
            for batch in chunks(topic_rows, BATCH_SIZE):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (t:Topic {name: row.name})
                    """,
                    rows=batch,
                )

            # ── Paper nodes only ──────────────────────────────────────────────────
            print(f"Loading {len(papers):,} paper nodes …")
            for batch in chunks(papers, BATCH_SIZE):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (p:Paper {doi: row.doi})
                    SET   p.title = row.title,
                          p.year  = row.year
                    """,
                    rows=batch,
                )

            # ── AUTHORED relationships ─────────────────────────────────────────────
            print("Loading AUTHORED relationships …")
            authored_rows = [
                {"doi": p["doi"], "author": a}
                for p in papers
                for a in p["authors"]
            ]
            for batch in chunks(authored_rows, BATCH_SIZE):
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (a:Author {name: row.author})
                    MATCH (p:Paper  {doi:  row.doi})
                    MERGE (a)-[:AUTHORED]->(p)
                    """,
                    rows=batch,
                )

            # ── HAS_TOPIC relationships ────────────────────────────────────────────
            print("Loading HAS_TOPIC relationships …")
            topic_rows2 = [
                {"doi": p["doi"], "topic": t}
                for p in papers
                for t in p["topics"]
            ]
            for batch in chunks(topic_rows2, BATCH_SIZE):
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (p:Paper {doi:  row.doi})
                    MATCH (t:Topic {name: row.topic})
                    MERGE (p)-[:HAS_TOPIC]->(t)
                    """,
                    rows=batch,
                )

            # ── CO_AUTHORED relationships ──────────────────────────────────────────
            print(f"Loading {len(coauth):,} CO_AUTHORED edges …")
            edge_rows = [{"a": a, "b": b, "weight": w} for (a, b), w in coauth.items()]
            for i, batch in enumerate(chunks(edge_rows, BATCH_SIZE)):
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (a:Author {name: row.a})
                    MATCH (b:Author {name: row.b})
                    MERGE (a)-[r:CO_AUTHORED]-(b)
                    SET   r.weight = row.weight
                    """,
                    rows=batch,
                )
                if i % 20 == 0:
                    print(f"  … {min((i+1)*BATCH_SIZE, len(edge_rows)):,} / {len(edge_rows):,}")
        finally:
            driver.close()

    print("Done ✓")


if __name__ == "__main__":

    # ── Debug ──────────────────────────────────────────────────────────────────
    print("Current directory:", os.getcwd())
    print("File exists:", os.path.exists(EXCEL_FILE))

    df = pd.read_csv(EXCEL_FILE)
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    print(df.head(2))
    # ──────────────────────────────────────────────────────────────────────────

    print("Parsing CSV …")
    papers, author_info, coauth, topics = parse_data(EXCEL_FILE)
    author_summary = summarize_author_identities(df, author_info)
    print(f"  {len(papers):,} papers with NC State authors")
    print(f"  {author_summary['unique_nc_author_names']:,} unique names in nc_authors")
    print(f"  {author_summary['unique_loader_identities']:,} unique NC State authors loaded")
    print(f"  {len(topics):,} unique topics")
    print(f"  {len(coauth):,} NC State co-author pairs")

    load_to_neo4j(papers, author_info, coauth, topics)
