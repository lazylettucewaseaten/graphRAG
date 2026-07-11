#!/usr/bin/env python3
"""
Usage:
    python3 load_to_neo4j.py <repo_analysis.json>
"""
import json
import sys
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 load_to_neo4j.py <repo_analysis.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    with open(json_path, 'r') as f:
        data = json.load(f)

    nodes = data["nodes"]
    relations = data["relations"]

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session(database=database) as session:
        session.run("MATCH (n:CodeNode) DETACH DELETE n")

        # Create index for fast lookups
        session.run("CREATE INDEX IF NOT EXISTS FOR (n:CodeNode) ON (n.id)")
        session.run("CREATE FULLTEXT INDEX bm25_index IF NOT EXISTS FOR (n:CodeNode) ON EACH [n.text]")

        # Batch insert all nodes
        BATCH_SIZE = 500
        for i in range(0, len(nodes), BATCH_SIZE):
            batch = nodes[i:i + BATCH_SIZE]
            session.run(
                """
                UNWIND $nodes AS n
                CREATE (node:CodeNode {id: n.id, type: n.type, name: n.name, file: n.file, text: n.text})
                """,
                nodes=batch
            )

        #  insert relationships grouped by type
        rel_types = set(r["type"] for r in relations)
        for rel_type in rel_types:
            batch = [r for r in relations if r["type"] == rel_type]
            for i in range(0, len(batch), BATCH_SIZE):
                chunk = batch[i:i + BATCH_SIZE]
                session.run(
                    f"""
                    UNWIND $rels AS r
                    MATCH (a:CodeNode {{id: r.source}})
                    MATCH (b:CodeNode {{id: r.target}})
                    CREATE (a)-[:{rel_type}]->(b)
                    """,
                    rels=chunk
                )
            print(f"Created {len(batch)} {rel_type} relationships")

    driver.close()
    print(" Done loading into Neo4j")


if __name__ == '__main__':
    main()
