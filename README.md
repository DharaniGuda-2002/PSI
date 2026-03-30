# PSI Research Collaboration Mapping

This repository supports a proof-of-concept analysis of interdisciplinary research activity connected to the N.C. Plant Sciences Institute (PSI).

The broader goal is to understand how PSI-affiliated NCSU researchers collaborate across topics, where interdisciplinary strength already exists, and which areas may represent future opportunities for growth. In the current repo, that work is represented through publication preprocessing, Neo4j graph loading, and network metric analysis built from PSI-related publication data.

## Project Focus

This repo currently helps us:

- clean and standardize PSI publication records,
- identify NC State-affiliated researchers from publication metadata,
- load the publication network into Neo4j,
- build an NC State co-authorship graph,
- and analyze collaboration structure using graph metrics.

## Repository Workflow

1. Start with the raw publication export in `Papers.csv`.
2. Run `pre_processing.ipynb` to clean the data and produce `papers_filtered.csv`.
3. Run `neo4j_connector.py` to load the processed data into Neo4j.
4. Use the exported network metrics in `centrality.csv` and explore them in `nc_metrics.ipynb`.

## Documentation

- [Data Definitions](/Users/dharani/Desktop/PSI/DATA_DEFINITIONS.md)
- [Neo4j Workflow](/Users/dharani/Desktop/PSI/NEO4J_GUIDE.md)
- [Metrics Results](/Users/dharani/Desktop/PSI/METRICS_GUIDE.md)

## Main Files

- `Papers.csv`: raw publication dataset.
- `papers_filtered.csv`: cleaned dataset used downstream.
- `pre_processing.ipynb`: preprocessing and validation notebook.
- `neo4j_connector.py`: Neo4j loading script.
- `centrality.csv`: exported graph metrics for NC State authors.
- `nc_metrics.ipynb`: notebook for metric exploration and plotting.

## Notes

- The current graph loading workflow uses NC State people parsed from `nc_state_people`.
- The current `centrality.csv` output reflects NC State authors in the co-authorship network.
- Future work may expand the analysis to compare NC and non-NC collaborators, temporal slices, topic diversity, and broader interdisciplinarity measures.
