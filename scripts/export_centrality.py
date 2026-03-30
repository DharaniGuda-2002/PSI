import csv
import os
from pathlib import Path

from neo4j_utils import get_driver, get_neo4j_settings

GRAPH_NAME = os.getenv("PSI_GDS_GRAPH", "co_author_with")
OUTPUT_CSV = Path(os.getenv("PSI_CENTRALITY_OUT", "../data/centrality.csv"))


def run_query(session, query, **params):
    return list(session.run(query, **params))


def ensure_weight_property(session):
    counts = run_query(
        session,
        """
        MATCH ()-[r:CO_AUTHORED]-()
        RETURN count(r) AS total, count(r.weight) AS withWeight
        """,
    )[0]

    total = counts["total"]
    with_weight = counts["withWeight"]

    print(f"CO_AUTHORED relationships: {total:,}")
    print(f"CO_AUTHORED relationships with weight: {with_weight:,}")

    if total != with_weight:
        print("Initializing missing CO_AUTHORED.weight values to 1.0 …")
        session.run(
            """
            MATCH ()-[r:CO_AUTHORED]-()
            WHERE r.weight IS NULL
            SET r.weight = 1.0
            """
        )


def drop_graph_if_exists(session, graph_name):
    exists_result = run_query(
        session,
        """
        CALL gds.graph.exists($graph_name)
        YIELD exists
        RETURN exists
        """,
        graph_name=graph_name,
    )[0]

    if exists_result["exists"]:
        print(f"Dropping existing in-memory graph '{graph_name}' …")
        session.run("CALL gds.graph.drop($graph_name)", graph_name=graph_name)


def project_graph(session, graph_name):
    print(f"Projecting in-memory graph '{graph_name}' …")
    session.run(
        """
        CALL gds.graph.project(
          $graph_name,
          'Author',
          {
            CO_AUTHORED: {
              orientation: 'UNDIRECTED',
              properties: 'weight'
            }
          }
        )
        """,
        graph_name=graph_name,
    )


def run_metrics(session, graph_name):
    print("Running degree centrality …")
    session.run(
        """
        CALL gds.degree.write($graph_name, {
          writeProperty: 'degree'
        })
        """,
        graph_name=graph_name,
    )

    print("Running weighted degree centrality …")
    session.run(
        """
        CALL gds.degree.write($graph_name, {
          relationshipWeightProperty: 'weight',
          writeProperty: 'weightedDegree'
        })
        """,
        graph_name=graph_name,
    )

    print("Running betweenness centrality …")
    session.run(
        """
        CALL gds.betweenness.write($graph_name, {
          writeProperty: 'betweenness'
        })
        """,
        graph_name=graph_name,
    )

    print("Running closeness centrality …")
    session.run(
        """
        CALL gds.closeness.write($graph_name, {
          writeProperty: 'closeness'
        })
        """,
        graph_name=graph_name,
    )

    print("Running eigenvector centrality …")
    session.run(
        """
        CALL gds.eigenvector.write($graph_name, {
          writeProperty: 'eigenvector'
        })
        """,
        graph_name=graph_name,
    )

    print("Running Louvain community detection …")
    session.run(
        """
        CALL gds.louvain.write($graph_name, {
          writeProperty: 'community'
        })
        """,
        graph_name=graph_name,
    )


def fetch_centrality_rows(session):
    print("Fetching metric results from Neo4j …")
    result = session.run(
        """
        MATCH (a:Author)
        RETURN
          a.name AS Name,
          a.degree AS degree,
          a.weightedDegree AS weightedDegree,
          a.betweenness AS betweenness,
          a.closeness AS closeness,
          a.eigenvector AS eigenvector,
          a.community AS community
        ORDER BY weightedDegree DESC, Name ASC
        """
    )
    return [record.data() for record in result]


def write_csv(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Name",
        "degree",
        "weightedDegree",
        "betweenness",
        "closeness",
        "eigenvector",
        "community",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows):,} rows to {output_path}")


def main():
    settings = get_neo4j_settings()
    driver = get_driver()

    try:
        with driver.session(database=settings["database"]) as session:
            ensure_weight_property(session)
            drop_graph_if_exists(session, GRAPH_NAME)
            project_graph(session, GRAPH_NAME)
            run_metrics(session, GRAPH_NAME)
            rows = fetch_centrality_rows(session)
            write_csv(rows, OUTPUT_CSV)
            drop_graph_if_exists(session, GRAPH_NAME)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
