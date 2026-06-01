# PSI Research Collaboration Mapping

This repository supports a proof-of-concept analysis of interdisciplinary research activity connected to the N.C. Plant Sciences Institute (PSI).

The broader goal is to understand how PSI-affiliated NCSU researchers collaborate across topics, where interdisciplinary strength already exists, and which areas may represent future opportunities for growth. In this repo, the work is represented through publication preprocessing, Neo4j graph loading, and graph metric analysis built from PSI-related publication data.

## Project Focus

This repo currently helps us:

- clean and standardize PSI publication records
- identify NC State-affiliated researchers from publication metadata
- load the publication network into Neo4j
- build an author co-authorship graph with NC State authors flagged
- analyze collaboration structure using graph metrics

## Repository Workflow

1. Start with the raw publication export in `data/Papers.csv`.
2. Run `notebooks/pre_processing.ipynb` to clean the data and produce `data/papers_filtered.csv`.
3. Run `scripts/neo4j_connector.py` to load the cleaned data into Neo4j.
4. Use the exported network metrics in `data/centrality.csv` and explore them in `notebooks/nc_metrics.ipynb`.

## Documentation

- [Data Definitions](docs/DATA_DEFINITIONS.md)
- [Neo4j Workflow](docs/NEO4J_GUIDE.md)
- [Metrics Guide](docs/METRICS_GUIDE.md)
- [Graph Projections](docs/GDS_PROJECTIONS.md)
- [Change Log](docs/CHANGELOG.md)

## Main Files

- `data/Papers.csv`: raw publication dataset.
- `data/papers_filtered.csv`: cleaned dataset used downstream.
- `data/centrality.csv`: exported graph metrics for authors.
- `notebooks/pre_processing.ipynb`: preprocessing logic and validation.
- `notebooks/nc_metrics.ipynb`: metric exploration and plotting.
- `scripts/neo4j_connector.py`: Neo4j loading script.
- `scripts/idr_analysis.py`, `scripts/topic_network_analysis.py`, `scripts/project_author_topic_graph.py`: analysis scripts supporting graph and topic workflows.

## Notes

- The current Neo4j workflow loads all authors from `data/papers_filtered.csv` and marks NC State authors with `Author.nc_state = true`.
- The current `data/centrality.csv` output reflects authors in the co-authorship network.
- Documentation was synchronized to the repository state in April 2026.
