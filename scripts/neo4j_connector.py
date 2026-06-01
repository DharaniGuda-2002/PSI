import os
import pandas as pd
import re
import unicodedata
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
    cleaned = " ".join(str(name or "").split()).strip()
    return cleaned.rstrip(",;")


def fold_to_ascii(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def clean_name_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold_to_ascii(value).lower())


def parse_name_parts(name: str | None) -> dict | None:
    canonical_name = normalize_name(name)
    if not canonical_name:
        return None

    if "," in canonical_name:
        last_name, given_names = canonical_name.split(",", 1)
        given_tokens = [
            clean_name_token(token)
            for token in given_names.strip().split()
            if clean_name_token(token)
        ]
        last_name_token = clean_name_token(last_name)
    else:
        tokens = [
            clean_name_token(token)
            for token in canonical_name.split()
            if clean_name_token(token)
        ]
        if not tokens:
            return None
        last_name_token = tokens[-1]
        given_tokens = tokens[:-1]

    if not last_name_token:
        return None

    return {
        "last": last_name_token,
        "given": given_tokens,
        "given_initials": [token[0] for token in given_tokens if token],
    }


def names_match_score(left_name: str, right_name: str) -> int:
    left = parse_name_parts(left_name)
    right = parse_name_parts(right_name)
    if not left or not right:
        return 0

    if normalize_name(left_name) == normalize_name(right_name):
        return 4

    last_names_equal = left["last"] == right["last"]
    last_names_overlap = (
        left["last"] in right["last"] or right["last"] in left["last"]
    )
    if not (last_names_equal or last_names_overlap):
        return 0

    if not left["given"] or not right["given"]:
        return 0

    left_first = left["given"][0]
    right_first = right["given"][0]
    first_names_compatible = (
        left_first == right_first
        or left_first.startswith(right_first)
        or right_first.startswith(left_first)
    )
    if first_names_compatible:
        return 3 if last_names_equal else 2

    left_initial = left_first[0]
    right_initials = set(right["given_initials"])
    if left_initial in right_initials:
        return 1 if last_names_equal else 0

    return 0


def resolve_authors_for_paper(all_authors: list[str], nc_names: set[str]) -> list[str]:
    raw_authors = [normalize_name(name) for name in all_authors if normalize_name(name)]
    resolved_by_raw_name = {}

    for nc_name in sorted(nc_names):
        scored_candidates = []
        for raw_author in raw_authors:
            score = names_match_score(nc_name, raw_author)
            if score > 0:
                scored_candidates.append((score, raw_author))

        if not scored_candidates:
            continue

        scored_candidates.sort(key=lambda item: (-item[0], item[1]))
        best_score = scored_candidates[0][0]
        best_candidates = [name for score, name in scored_candidates if score == best_score]
        if len(best_candidates) == 1:
            resolved_by_raw_name[best_candidates[0]] = nc_name

    resolved_authors = []
    for raw_author in raw_authors:
        resolved_authors.append(resolved_by_raw_name.get(raw_author, raw_author))

    for nc_name in sorted(nc_names):
        if nc_name not in resolved_authors:
            resolved_authors.append(nc_name)

    deduped_authors = []
    seen = set()
    for author_name in resolved_authors:
        if author_name not in seen:
            deduped_authors.append(author_name)
            seen.add(author_name)

    return deduped_authors


def parse_all_authors(raw: str) -> list[str]:
    return [
        canonical_name
        for entry in split_semicolon_values(raw)
        if (canonical_name := normalize_name(entry))
    ]


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
    author_info = defaultdict(lambda: {"paper_count": 0, "nc_state": False})
    coauth      = defaultdict(int)
    topics      = set()

    for _, row in df.iterrows():
        title    = str(row.get("title",  "")).strip()
        doi      = str(row.get("DOI",    "")).strip()
        year     = row.get("year", None)
        tops     = split_semicolon_values(row.get("topics", ""))

        nc_people = parse_processed_nc_people(row)
        nc_names = {person["name"] for person in nc_people}

        all_authors = parse_all_authors(row.get("authors", ""))
        if not all_authors:
            all_authors = sorted(nc_names)

        resolved_authors = resolve_authors_for_paper(all_authors, nc_names)
        if not resolved_authors:
            continue

        papers.append({
            "title":   title,
            "doi":     doi,
            "year":    int(year) if pd.notna(year) else None,
            "authors": resolved_authors,
            "topics":  tops,
        })

        for author_name in set(resolved_authors):
            info = author_info[author_name]
            info["paper_count"] += 1
            if author_name in nc_names:
                info["nc_state"] = True

        for t in tops:
            topics.add(t)

        for a, b in combinations(sorted(set(resolved_authors)), 2):
            coauth[(a, b)] += 1

    return papers, author_info, coauth, topics


def summarize_author_identities(df, author_info):
    unique_nc_author_names = set()
    unique_all_author_names = set()

    for _, row in df.iterrows():
        for name in split_semicolon_values(row.get("nc_authors", "")):
            canonical_name = normalize_name(name)
            if canonical_name:
                unique_nc_author_names.add(canonical_name)

        for name in parse_all_authors(row.get("authors", "")):
            unique_all_author_names.add(name)

    return {
        "unique_all_author_names": len(unique_all_author_names),
        "unique_nc_author_names": len(unique_nc_author_names),
        "unique_loader_identities": len(author_info),
        "loader_nc_state_authors": sum(1 for info in author_info.values() if info["nc_state"]),
        "loader_external_authors": sum(1 for info in author_info.values() if not info["nc_state"]),
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
            nc_count = sum(1 for info in author_info.values() if info["nc_state"])
            ext_count = len(author_info) - nc_count
            print(f"Loading {len(author_info):,} author nodes …")
            print(f"  → {nc_count:,} NC State  |  {ext_count:,} external")
            author_rows = [
                {
                    "name": name,
                    "paper_count": info["paper_count"],
                    "nc_state": info["nc_state"],
                    "author_label": "NCStateAuthor" if info["nc_state"] else "ExternalAuthor",
                }
                for name, info in author_info.items()
            ]
            for batch in chunks(author_rows, BATCH_SIZE):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (a:Author {name: row.name})
                    SET   a.paper_count = row.paper_count,
                          a.nc_state    = row.nc_state
                    FOREACH (_ IN CASE WHEN row.author_label = 'NCStateAuthor' THEN [1] ELSE [] END |
                        SET a:NCStateAuthor
                        REMOVE a:ExternalAuthor
                    )
                    FOREACH (_ IN CASE WHEN row.author_label = 'ExternalAuthor' THEN [1] ELSE [] END |
                        SET a:ExternalAuthor
                        REMOVE a:NCStateAuthor
                    )
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
    print(f"  {len(papers):,} papers loaded")
    print(f"  {author_summary['unique_all_author_names']:,} unique names in authors")
    print(f"  {author_summary['unique_nc_author_names']:,} unique names in nc_authors")
    print(f"  {author_summary['unique_loader_identities']:,} unique authors loaded")
    print(f"  {author_summary['loader_nc_state_authors']:,} NC State authors loaded")
    print(f"  {author_summary['loader_external_authors']:,} external authors loaded")
    print(f"  {len(topics):,} unique topics")
    print(f"  {len(coauth):,} co-author pairs")

    load_to_neo4j(papers, author_info, coauth, topics)
