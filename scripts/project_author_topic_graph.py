import os

from neo4j_utils import get_driver, get_neo4j_settings

GRAPH_NAME = os.getenv("PSI_TOPIC_GRAPH", "coauthor_topics")


def run_query(session, query, **params):
    return list(session.run(query, **params))


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
        print(f"Dropping existing in-memory graph '{graph_name}' ...")
        session.run("CALL gds.graph.drop($graph_name)", graph_name=graph_name)


def project_graph(session, graph_name):
    print(f"Projecting mixed Author/Topic graph '{graph_name}' ...")
    result = session.run(
        """
        CALL gds.graph.project.cypher(
          $graph_name,
          '
          MATCH (n)
          WHERE n:Author OR n:Topic
          RETURN id(n) AS id, labels(n) AS labels
          ',
          '
          MATCH (a:Author)-[r:CO_AUTHORED]-(b:Author)
          RETURN
            id(a) AS source,
            id(b) AS target,
            "CO_AUTHORED" AS type,
            r.weight AS weight

          UNION

          MATCH (a:Author)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(t:Topic)
          WITH a, t, count(*) AS weight
          RETURN
            id(a) AS source,
            id(t) AS target,
            "AUTHOR_TOPIC" AS type,
            toFloat(weight) AS weight
          ',
          {
            relationshipProperties: "weight",
            undirectedRelationshipTypes: ["CO_AUTHORED", "AUTHOR_TOPIC"]
          }
        )
        YIELD
          graphName,
          nodeCount,
          relationshipCount,
          projectMillis
        RETURN graphName, nodeCount, relationshipCount, projectMillis
        """,
        graph_name=graph_name,
    ).single()

    print(
        "Projected "
        f"{result['graphName']} with "
        f"{result['nodeCount']:,} nodes and "
        f"{result['relationshipCount']:,} relationships "
        f"in {result['projectMillis']:,} ms"
    )


def preview_top_author_topic_edges(session):
    print("Previewing strongest Author-Topic connections ...")
    result = session.run(
        """
        MATCH (a:Author)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(t:Topic)
        WITH a, t, count(*) AS weight
        RETURN
          a.name AS author,
          t.name AS topic,
          weight
        ORDER BY weight DESC, author ASC, topic ASC
        LIMIT 10
        """
    )

    for record in result:
        print(
            f"  {record['author']} -> {record['topic']} "
            f"({record['weight']} papers)"
        )


def main():
    settings = get_neo4j_settings()
    driver = get_driver()

    try:
        with driver.session(database=settings["database"]) as session:
            drop_graph_if_exists(session, GRAPH_NAME)
            project_graph(session, GRAPH_NAME)
            preview_top_author_topic_edges(session)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
