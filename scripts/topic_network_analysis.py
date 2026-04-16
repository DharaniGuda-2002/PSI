from __future__ import annotations

from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import Path

import pandas as pd


def split_semicolon_values(raw: str | None) -> list[str]:
    if pd.isna(raw) or str(raw).strip().lower() in ("", "nan"):
        return []
    return [item.strip() for item in str(raw).split(";") if item.strip()]


def normalize_topic_name(topic: str | None) -> str:
    return " ".join(str(topic or "").split()).strip().lower()


def load_filtered_papers(data_path: str | Path = "../data/papers_filtered.csv") -> pd.DataFrame:
    df = pd.read_csv(data_path)
    df["topic_list"] = df["topics"].apply(split_semicolon_values)
    df["author_list"] = df["authors"].apply(split_semicolon_values)
    df["nc_author_list"] = df["nc_authors"].apply(split_semicolon_values)
    return df


def available_topics(df: pd.DataFrame) -> list[str]:
    topics = (
        df["topic_list"]
        .explode()
        .dropna()
        .astype(str)
        .str.strip()
    )
    topics = topics[topics.ne("")]
    return sorted(topics.unique().tolist(), key=str.lower)


def filter_papers_for_topic(df: pd.DataFrame, selected_topic: str) -> pd.DataFrame:
    selected_key = normalize_topic_name(selected_topic)

    def contains_topic(topic_list: list[str]) -> bool:
        return any(normalize_topic_name(topic) == selected_key for topic in topic_list)

    topic_df = df[df["topic_list"].apply(contains_topic)].copy()
    topic_df["selected_topic"] = selected_topic
    return topic_df


def build_topic_network(topic_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    author_stats: dict[str, dict] = defaultdict(
        lambda: {
            "topic_paper_count": 0,
            "nc_state": False,
        }
    )
    edge_weights: dict[tuple[str, str], int] = defaultdict(int)

    for _, row in topic_df.iterrows():
        authors = [author for author in row["author_list"] if author]
        nc_authors = set(row["nc_author_list"])

        for author in set(authors):
            author_stats[author]["topic_paper_count"] += 1
            if author in nc_authors:
                author_stats[author]["nc_state"] = True

        for left, right in combinations(sorted(set(authors)), 2):
            edge_weights[(left, right)] += 1

    author_rows = [
        {
            "author": author,
            "topic_paper_count": stats["topic_paper_count"],
            "nc_state": stats["nc_state"],
        }
        for author, stats in author_stats.items()
    ]
    edge_rows = [
        {
            "source": left,
            "target": right,
            "weight": weight,
        }
        for (left, right), weight in edge_weights.items()
    ]

    return pd.DataFrame(author_rows), pd.DataFrame(edge_rows)


def compute_author_network_metrics(authors_df: pd.DataFrame, edges_df: pd.DataFrame) -> pd.DataFrame:
    if authors_df.empty:
        return authors_df.copy()

    adjacency: dict[str, set[str]] = {author: set() for author in authors_df["author"]}
    weighted_degree: Counter = Counter()
    edge_lookup: dict[tuple[str, str], int] = {}

    for _, row in edges_df.iterrows():
        source = row["source"]
        target = row["target"]
        weight = int(row["weight"])
        adjacency[source].add(target)
        adjacency[target].add(source)
        weighted_degree[source] += weight
        weighted_degree[target] += weight
        edge_lookup[tuple(sorted((source, target)))] = weight

    nc_lookup = dict(zip(authors_df["author"], authors_df["nc_state"]))

    rows = []
    for author in authors_df["author"]:
        neighbors = adjacency.get(author, set())
        degree = len(neighbors)

        neighbor_pairs = 0
        connected_neighbor_pairs = 0
        neighbor_list = sorted(neighbors)
        for left, right in combinations(neighbor_list, 2):
            neighbor_pairs += 1
            if tuple(sorted((left, right))) in edge_lookup:
                connected_neighbor_pairs += 1

        local_clustering = (
            connected_neighbor_pairs / neighbor_pairs if neighbor_pairs else 0.0
        )

        external_neighbors = sum(1 for neighbor in neighbors if not nc_lookup.get(neighbor, False))
        nc_neighbors = sum(1 for neighbor in neighbors if nc_lookup.get(neighbor, False))

        rows.append(
            {
                "author": author,
                "topic_degree": degree,
                "topic_weighted_degree": weighted_degree[author],
                "nc_neighbors": nc_neighbors,
                "external_neighbors": external_neighbors,
                "external_neighbor_share": external_neighbors / degree if degree else 0.0,
                "local_clustering": local_clustering,
            }
        )

    metrics_df = authors_df.merge(pd.DataFrame(rows), on="author", how="left")
    metrics_df = metrics_df.sort_values(
        ["topic_paper_count", "topic_weighted_degree", "topic_degree", "author"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    return metrics_df


def compute_component_sizes(authors_df: pd.DataFrame, edges_df: pd.DataFrame) -> list[int]:
    nodes = set(authors_df["author"].tolist())
    adjacency = {node: set() for node in nodes}

    for _, row in edges_df.iterrows():
        source = row["source"]
        target = row["target"]
        adjacency[source].add(target)
        adjacency[target].add(source)

    seen = set()
    sizes = []

    for node in nodes:
        if node in seen:
            continue

        queue = deque([node])
        seen.add(node)
        size = 0

        while queue:
            current = queue.popleft()
            size += 1
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)

        sizes.append(size)

    return sorted(sizes, reverse=True)


def classify_topic_pattern(summary: dict) -> str:
    density = summary["density"]
    clustering = summary["average_local_clustering"]
    external_edge_share = summary["cross_nc_external_edge_share"]
    component_share = summary["largest_component_share"]

    if density >= 0.35 and clustering >= 0.55:
        return "Clique-like / tightly knit"
    if external_edge_share >= 0.30:
        return "External-facing / cross-boundary collaboration"
    if component_share >= 0.80:
        return "Core connected network"
    return "Mixed / distributed collaboration pattern"


def summarize_topic_network(
    topic_df: pd.DataFrame,
    authors_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    author_metrics_df: pd.DataFrame,
) -> dict:
    node_count = len(authors_df)
    edge_count = len(edges_df)
    nc_count = int(authors_df["nc_state"].sum()) if node_count else 0
    external_count = node_count - nc_count
    possible_edges = node_count * (node_count - 1) / 2
    density = (edge_count / possible_edges) if possible_edges else 0.0
    component_sizes = compute_component_sizes(authors_df, edges_df) if node_count else []
    largest_component = component_sizes[0] if component_sizes else 0
    largest_component_share = (largest_component / node_count) if node_count else 0.0
    average_local_clustering = (
        float(author_metrics_df["local_clustering"].mean()) if not author_metrics_df.empty else 0.0
    )

    nc_lookup = dict(zip(authors_df["author"], authors_df["nc_state"])) if node_count else {}
    edge_type_counts = Counter({"nc_nc": 0, "nc_external": 0, "external_external": 0})

    for _, row in edges_df.iterrows():
        left_nc = nc_lookup.get(row["source"], False)
        right_nc = nc_lookup.get(row["target"], False)
        if left_nc and right_nc:
            edge_type_counts["nc_nc"] += 1
        elif left_nc or right_nc:
            edge_type_counts["nc_external"] += 1
        else:
            edge_type_counts["external_external"] += 1

    cross_nc_external_edge_share = (
        edge_type_counts["nc_external"] / edge_count if edge_count else 0.0
    )

    summary = {
        "papers_in_topic": len(topic_df),
        "authors_in_topic_network": node_count,
        "nc_authors_in_topic_network": nc_count,
        "external_authors_in_topic_network": external_count,
        "coauthor_edges": edge_count,
        "density": density,
        "components": len(component_sizes),
        "largest_component_size": largest_component,
        "largest_component_share": largest_component_share,
        "average_local_clustering": average_local_clustering,
        "nc_nc_edges": edge_type_counts["nc_nc"],
        "nc_external_edges": edge_type_counts["nc_external"],
        "external_external_edges": edge_type_counts["external_external"],
        "cross_nc_external_edge_share": cross_nc_external_edge_share,
    }
    summary["pattern_label"] = classify_topic_pattern(summary)
    return summary


def build_topic_report(
    selected_topic: str,
    data_path: str | Path = "../data/papers_filtered.csv",
) -> dict:
    papers_df = load_filtered_papers(data_path)
    topic_df = filter_papers_for_topic(papers_df, selected_topic)
    authors_df, edges_df = build_topic_network(topic_df)
    author_metrics_df = compute_author_network_metrics(authors_df, edges_df)
    summary = summarize_topic_network(topic_df, authors_df, edges_df, author_metrics_df)

    top_authors = author_metrics_df.head(20).copy()
    top_connectors = (
        author_metrics_df.sort_values(
            ["topic_weighted_degree", "topic_degree", "external_neighbor_share", "author"],
            ascending=[False, False, False, True],
        )
        .head(20)
        .copy()
    )
    top_external_bridges = (
        author_metrics_df[author_metrics_df["external_neighbors"] > 0]
        .sort_values(
            ["external_neighbor_share", "external_neighbors", "topic_weighted_degree", "author"],
            ascending=[False, False, False, True],
        )
        .head(20)
        .copy()
    )
    strongest_pairs = edges_df.sort_values(["weight", "source", "target"], ascending=[False, True, True]).head(20).copy()

    return {
        "selected_topic": selected_topic,
        "summary": summary,
        "topic_papers_df": topic_df,
        "topic_authors_df": author_metrics_df,
        "topic_edges_df": edges_df,
        "top_authors_df": top_authors,
        "top_connectors_df": top_connectors,
        "top_external_bridges_df": top_external_bridges,
        "strongest_pairs_df": strongest_pairs,
        "available_topics": available_topics(papers_df),
    }


def summary_to_series(summary: dict) -> pd.Series:
    ordered_keys = [
        "papers_in_topic",
        "authors_in_topic_network",
        "nc_authors_in_topic_network",
        "external_authors_in_topic_network",
        "coauthor_edges",
        "density",
        "components",
        "largest_component_size",
        "largest_component_share",
        "average_local_clustering",
        "nc_nc_edges",
        "nc_external_edges",
        "external_external_edges",
        "cross_nc_external_edge_share",
        "pattern_label",
    ]
    return pd.Series({key: summary[key] for key in ordered_keys})
