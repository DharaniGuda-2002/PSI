from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def split_semicolon_values(raw: str | None) -> list[str]:
    if pd.isna(raw) or str(raw).strip().lower() in ("", "nan"):
        return []
    return [item.strip() for item in str(raw).split(";") if item.strip()]


def load_base_frames(
    papers_path: str | Path = "./data/papers_filtered.csv",
    centrality_path: str | Path = "./data/centrality.csv",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    papers_df = pd.read_csv(papers_path)
    papers_df = papers_df.copy()
    papers_df["paper_id"] = papers_df["DOI"].fillna("").astype(str).str.strip()
    blank_paper_ids = papers_df["paper_id"].eq("")
    if blank_paper_ids.any():
        papers_df.loc[blank_paper_ids, "paper_id"] = (
            "paper_missing_doi_" + papers_df.index[blank_paper_ids].astype(str)
        )
    papers_df["topic_list"] = papers_df["topics"].apply(split_semicolon_values)
    papers_df["author_list"] = papers_df["authors"].apply(split_semicolon_values)
    papers_df["nc_author_list"] = papers_df["nc_authors"].apply(split_semicolon_values)

    centrality_df = pd.read_csv(centrality_path, usecols=["Name", "community", "nc_state"])
    centrality_df["Name"] = centrality_df["Name"].astype(str).str.strip()
    centrality_df["community"] = pd.to_numeric(centrality_df["community"], errors="coerce")
    centrality_df["nc_state"] = (
        centrality_df["nc_state"].fillna(False).astype(str).str.lower().eq("true")
    )

    return papers_df, centrality_df


def build_topic_matrix(papers_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], np.ndarray]:
    paper_topics = papers_df[["paper_id", "topic_list"]].explode("topic_list")
    paper_topics = paper_topics.rename(columns={"topic_list": "topic"})
    paper_topics["topic"] = paper_topics["topic"].fillna("").astype(str).str.strip()
    paper_topics = paper_topics[paper_topics["topic"].ne("")].copy()

    topics = sorted(paper_topics["topic"].unique().tolist(), key=str.lower)
    incidence = (
        paper_topics.assign(value=1)
        .pivot_table(index="paper_id", columns="topic", values="value", aggfunc="max", fill_value=0)
        .reindex(columns=topics, fill_value=0)
    )
    return paper_topics, topics, incidence.to_numpy(dtype=float)


def build_topic_disparity_matrix(topic_matrix: np.ndarray) -> np.ndarray:
    if topic_matrix.size == 0:
        return np.zeros((0, 0), dtype=float)

    topic_vectors = topic_matrix.T
    dot = topic_vectors @ topic_vectors.T
    norms = np.linalg.norm(topic_vectors, axis=1, keepdims=True)
    denom = norms @ norms.T
    similarity = np.divide(dot, denom, out=np.zeros_like(dot, dtype=float), where=denom != 0)
    disparity = 1.0 - similarity
    np.fill_diagonal(disparity, 0.0)
    return disparity


def compute_diversity_metrics(counts: np.ndarray, disparity_matrix: np.ndarray) -> dict[str, float]:
    counts = np.asarray(counts, dtype=float)
    total = counts.sum()
    non_zero = counts[counts > 0]
    num_topics = int((counts > 0).sum())

    if total <= 0 or num_topics == 0:
        return {
            "num_topics": 0,
            "shannon_entropy": 0.0,
            "normalized_shannon": 0.0,
            "blau_index": 0.0,
            "hhi": 0.0,
            "rao_stirling": 0.0,
        }

    proportions = counts / total
    positive = proportions[proportions > 0]
    shannon = float(-(positive * np.log(positive)).sum())
    max_shannon = np.log(num_topics) if num_topics > 1 else 0.0
    normalized_shannon = float(shannon / max_shannon) if max_shannon > 0 else 0.0
    hhi = float((proportions ** 2).sum())
    blau = float(1.0 - hhi)
    rao = float(proportions @ disparity_matrix @ proportions)

    return {
        "num_topics": num_topics,
        "shannon_entropy": shannon,
        "normalized_shannon": normalized_shannon,
        "blau_index": blau,
        "hhi": hhi,
        "rao_stirling": rao,
    }


def build_paper_idr(papers_df: pd.DataFrame, topics: list[str], disparity_matrix: np.ndarray) -> pd.DataFrame:
    topic_index = {topic: idx for idx, topic in enumerate(topics)}
    rows = []

    for _, row in papers_df.iterrows():
        counts = np.zeros(len(topics), dtype=float)
        unique_topics = sorted(set(row["topic_list"]), key=str.lower)
        for topic in unique_topics:
            counts[topic_index[topic]] = 1.0

        metrics = compute_diversity_metrics(counts, disparity_matrix)
        rows.append(
            {
                "paper_id": row["paper_id"],
                "DOI": row["DOI"],
                "title": row["title"],
                "year": row["year"],
                "team_size": len(set(row["author_list"])),
                "nc_team_size": len(set(row["nc_author_list"])),
                "external_team_size": len(set(row["author_list"])) - len(set(row["nc_author_list"])),
                "topics": "; ".join(unique_topics),
                **metrics,
            }
        )

    return pd.DataFrame(rows)


def build_people_idr(papers_df: pd.DataFrame, topics: list[str], disparity_matrix: np.ndarray) -> pd.DataFrame:
    topic_index = {topic: idx for idx, topic in enumerate(topics)}
    author_topic_counts: dict[str, np.ndarray] = {}
    author_papers: dict[str, set[str]] = {}
    author_nc_state: dict[str, bool] = {}

    for _, row in papers_df.iterrows():
        authors = sorted(set(row["author_list"]))
        nc_authors = set(row["nc_author_list"])
        unique_topics = sorted(set(row["topic_list"]), key=str.lower)

        for author in authors:
            if author not in author_topic_counts:
                author_topic_counts[author] = np.zeros(len(topics), dtype=float)
                author_papers[author] = set()
                author_nc_state[author] = False

            for topic in unique_topics:
                author_topic_counts[author][topic_index[topic]] += 1.0

            author_papers[author].add(row["paper_id"])
            if author in nc_authors:
                author_nc_state[author] = True

    rows = []
    for author, counts in author_topic_counts.items():
        metrics = compute_diversity_metrics(counts, disparity_matrix)
        rows.append(
            {
                "author": author,
                "nc_state": author_nc_state[author],
                "paper_count": len(author_papers[author]),
                "topic_assignments": int(counts.sum()),
                **metrics,
            }
        )

    people_df = pd.DataFrame(rows)
    return people_df.sort_values(
        ["rao_stirling", "normalized_shannon", "paper_count", "author"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def build_community_idr(
    papers_df: pd.DataFrame,
    centrality_df: pd.DataFrame,
    topics: list[str],
    disparity_matrix: np.ndarray,
) -> pd.DataFrame:
    topic_index = {topic: idx for idx, topic in enumerate(topics)}
    author_to_community = dict(zip(centrality_df["Name"], centrality_df["community"]))
    author_to_nc = dict(zip(centrality_df["Name"], centrality_df["nc_state"]))

    community_topic_counts: dict[int, np.ndarray] = {}
    community_authors: dict[int, set[str]] = {}
    community_nc_authors: dict[int, set[str]] = {}
    community_papers: dict[int, set[str]] = {}

    for _, row in papers_df.iterrows():
        unique_topics = sorted(set(row["topic_list"]), key=str.lower)
        authors = sorted(set(row["author_list"]))

        for author in authors:
            community = author_to_community.get(author)
            if pd.isna(community):
                continue
            community = int(community)

            if community not in community_topic_counts:
                community_topic_counts[community] = np.zeros(len(topics), dtype=float)
                community_authors[community] = set()
                community_nc_authors[community] = set()
                community_papers[community] = set()

            community_authors[community].add(author)
            community_papers[community].add(row["paper_id"])
            if author_to_nc.get(author, False):
                community_nc_authors[community].add(author)

            for topic in unique_topics:
                community_topic_counts[community][topic_index[topic]] += 1.0

    rows = []
    for community, counts in community_topic_counts.items():
        metrics = compute_diversity_metrics(counts, disparity_matrix)
        rows.append(
            {
                "community": community,
                "author_count": len(community_authors[community]),
                "nc_author_count": len(community_nc_authors[community]),
                "paper_count": len(community_papers[community]),
                "topic_assignments": int(counts.sum()),
                **metrics,
            }
        )

    community_df = pd.DataFrame(rows)
    return community_df.sort_values(
        ["rao_stirling", "normalized_shannon", "paper_count", "community"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def build_idr_outputs(
    papers_path: str | Path = "./data/papers_filtered.csv",
    centrality_path: str | Path = "./data/centrality.csv",
) -> dict[str, pd.DataFrame]:
    papers_df, centrality_df = load_base_frames(papers_path, centrality_path)
    _, topics, topic_matrix = build_topic_matrix(papers_df)
    disparity_matrix = build_topic_disparity_matrix(topic_matrix)

    paper_idr_df = build_paper_idr(papers_df, topics, disparity_matrix)
    people_idr_df = build_people_idr(papers_df, topics, disparity_matrix)
    community_idr_df = build_community_idr(papers_df, centrality_df, topics, disparity_matrix)

    return {
        "paper_idr_df": paper_idr_df,
        "people_idr_df": people_idr_df,
        "community_idr_df": community_idr_df,
    }
