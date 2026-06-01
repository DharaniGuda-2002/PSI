import os

from neo4j import GraphDatabase


def get_neo4j_settings():
    settings = {
        "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.getenv("NEO4J_USER", "neo4j"),
        "password": os.getenv("NEO4J_PASS","Dharani@2002"),
        "database": os.getenv("NEO4J_DB", "psi-db"),
    }

    if not settings["password"]:
        raise ValueError(
            "Missing NEO4J_PASS environment variable. "
            "Set it before running (for example: export NEO4J_PASS='your-password')."
        )

    return settings


def get_driver():
    settings = get_neo4j_settings()
    return GraphDatabase.driver(
        settings["uri"],
        auth=(settings["user"], settings["password"]),
    )
