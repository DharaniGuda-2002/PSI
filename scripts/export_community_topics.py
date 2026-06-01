import csv
import os
from pathlib import Path

from neo4j_utils import get_driver, get_neo4j_settings

OUTPUT_CSV = Path(
    os.getenv("PSI_COMMUNITY_TOPICS_OUT", "../data/community_topics.csv")
)


def fetch_community_topic_rows(session):
    print("Fetching community topic counts from Neo4j ...")
    result = session.run(
        """
        MATCH (a:Author)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(t:Topic)
        WHERE a.community IS NOT NULL
          AND t.name IS NOT NULL
          AND trim(toString(t.name)) <> ""
          AND toLower(trim(toString(t.name))) <> "nan"
        WITH a.community AS community, t.name AS topic, count(*) AS topic_count
        ORDER BY community, topic_count DESC, topic ASC
        WITH community, collect({
          topic: topic,
          topic_count: topic_count
        }) AS topics
        UNWIND topics AS topic_row
        RETURN
          community,
          size(topics) AS number_of_topics,
          topic_row.topic AS topic,
          topic_row.topic_count AS topic_count
        ORDER BY community, topic_count DESC, topic ASC
        """
    )
    return [record.data() for record in result]


def write_csv(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
        print(f"Deleted existing output file: {output_path}")

    fieldnames = [
        "community",
        "number_of_topics",
        "topic",
        "topic_count",
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
            rows = fetch_community_topic_rows(session)
            write_csv(rows, OUTPUT_CSV)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
