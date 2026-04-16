# Neo4j Workflow

This document explains how the processed PSI publication data is loaded into Neo4j and how the graph is modeled.

## Input

The Neo4j loader uses:

- `papers_filtered.csv`
- `neo4j_connector.py`

## Current Scope

The current graph build loads the full publication graph from `papers_filtered.csv`.

That means:

- `Author` nodes are created for every parsed name in `authors`.
- `Author.nc_state` is set to `true` when that author also appears in `nc_authors`; otherwise it is `false`.
- `CO_AUTHORED` relationships are built across the full author list on each paper.
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

`Author` nodes include:

- `name`
- `paper_count`
- `nc_state` (`true` for NC State authors, `false` for external collaborators)

`Author` nodes also receive one additional label for visualization support in Neo4j Browser:

- `NCStateAuthor`
- `ExternalAuthor`

### Relationships

- `(:Author)-[:AUTHORED]->(:Paper)`
- `(:Paper)-[:HAS_TOPIC]->(:Topic)`
- `(:Author)-[:CO_AUTHORED {weight}]-(:Author)`

## Relationship Semantics

- `AUTHORED` links authors to papers in the processed dataset.
- `HAS_TOPIC` links papers to their topic labels.
- `CO_AUTHORED.weight` stores the number of shared papers between two authors.

## What The Loader Does

The current script:

1. reads `papers_filtered.csv`,
2. parses all authors from `authors`,
3. canonicalizes author names against `nc_authors` so NC State authors are preserved even when publication strings use initials or name variants,
4. creates `Author`, `Paper`, and `Topic` nodes,
5. creates `AUTHORED` and `HAS_TOPIC` relationships,
6. aggregates co-authorship counts across the full author list,
7. writes weighted `CO_AUTHORED` edges.

## Implementation Notes

- The script creates indexes for author name, paper DOI, and topic name.
- If `CLEAR_DB_ON_START=true`, existing graph data in the target database is deleted before reload.
- The current implementation batches writes to Neo4j for efficiency.

## Output For Metrics

The co-authorship network loaded through this workflow is the basis for the metrics exported to `centrality.csv`.

For GDS projection patterns, including the mixed co-author plus topic projection, see [docs/GDS_PROJECTIONS.md](/Users/dharani/Desktop/PSI/docs/GDS_PROJECTIONS.md).

## Node Coloring In Neo4j

Yes, the same people remain `Author` nodes, and the loader now also adds `NCStateAuthor` or `ExternalAuthor` labels to make Browser styling easier.

- In Neo4j Browser, style `NCStateAuthor` and `ExternalAuthor` with different colors.
- All of those nodes still keep the `Author` label, so `MATCH (a:Author)` continues to return everyone together.
- In Bloom, this is typically done with perspective styling or rule-based coloring using the same `nc_state` property.
