# Neo4j Workflow

This document explains how the processed PSI publication data is loaded into Neo4j and how the graph is modeled.

## Input

The Neo4j loader uses:

- `papers_filtered.csv`
- `neo4j_connector.py`

## Current Scope

The current graph build is focused on NC State-affiliated people parsed from `nc_state_people`.

That means:

- `Author` nodes are created for NC State authors identified in the processed file.
- `CO_AUTHORED` relationships are built between those NC State authors.
- `Paper` and `Topic` nodes are also loaded to preserve publication and topical context.

## Environment Variables

Set these before running the loader:

```bash
export NEO4J_URI='bolt://localhost:7687'
export NEO4J_USER='neo4j'
export NEO4J_PASS='your-neo4j-password'
export NEO4J_DB='psi'
export CLEAR_DB_ON_START='true'
```

## How To Run

```bash
python3 neo4j_connector.py
```

## Graph Model

### Nodes

- `Author`
- `Paper`
- `Topic`

### Relationships

- `(:Author)-[:AUTHORED]->(:Paper)`
- `(:Paper)-[:HAS_TOPIC]->(:Topic)`
- `(:Author)-[:CO_AUTHORED {weight}]-(:Author)`

## Relationship Semantics

- `AUTHORED` links NC State authors to papers in the processed dataset.
- `HAS_TOPIC` links papers to their topic labels.
- `CO_AUTHORED.weight` stores the number of shared papers between two NC State authors.

## What The Loader Does

The current script:

1. reads `papers_filtered.csv`,
2. parses NC State people from `nc_state_people`,
3. creates `Author`, `Paper`, and `Topic` nodes,
4. creates `AUTHORED` and `HAS_TOPIC` relationships,
5. aggregates co-authorship counts,
6. and writes weighted `CO_AUTHORED` edges.

## Implementation Notes

- The script creates indexes for author name, paper DOI, and topic name.
- If `CLEAR_DB_ON_START=true`, existing graph data in the target database is deleted before reload.
- The current implementation batches writes to Neo4j for efficiency.

## Output For Metrics

The co-authorship network loaded through this workflow is the basis for the metrics exported to `centrality.csv`.
