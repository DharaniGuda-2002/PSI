# PSI Graph Metrics

This repository currently documents the graph metrics computed for the NC State co-authorship network.

## Scope (Important)

- Data sent to Neo4j includes **only NC State people** (from `nc_state_people` after parsing/cleaning).
- `Author` nodes and `CO_AUTHORED` edges are created only for those NC State authors.
- All metrics in `centrality.csv` are therefore computed **only for NC State authors**, not for all authors in the raw source.

## How To Run Neo4j Connector

Script: `neo4j_connector.py`

### 1) Set Neo4j connection variables

```bash
export NEO4J_URI='bolt://localhost:7687'
export NEO4J_USER='neo4j'
export NEO4J_PASS='your-neo4j-password'
export NEO4J_DB='psi'
export CLEAR_DB_ON_START='true'
```

Password note:
- Do not hardcode credentials in code.
- Keep password in `NEO4J_PASS` environment variable (or local `.env` that is gitignored).

### 2) Run the connector

```bash
python3 neo4j_connector.py
```

What it does:
- Reads `papers_filtered.csv`
- Parses only NC State authors from `nc_state_people`
- Loads `Author`, `Paper`, `Topic` nodes and relationships
- Builds weighted `CO_AUTHORED` relationships (`weight` = number of shared papers)

## Metrics Output

- Source file: `centrality.csv`
- Rows (authors): **1708**
- Columns:
  - `Name`
  - `degree`
  - `weightedDegree`
  - `betweenness`
  - `closeness`
  - `eigenvector`
  - `community`

## Network Snapshot

- Distinct communities: **33**
- Largest community (`community = 185`): **213 authors**
- Isolated authors (`degree = 0`): **4**
- Authors with repeated collaborations (`weightedDegree > degree`): **880**

## Top Authors by Metric

### Degree
1. Michael Daniele — 131
2. Jacob Jones — 108
3. David Jordan — 108
4. Alper Bozkurt — 106
5. Edgar Lobaton — 93

### Weighted Degree
1. David Jordan — 433
2. Michael Daniele — 340
3. Alper Bozkurt — 332
4. Jacob Jones — 321
5. Katherine Jennings — 220

### Betweenness
1. Edgar Lobaton — 173769.0632
2. Michael Kudenov — 146615.4560
3. Jacob Jones — 144676.0562
4. Michael Daniele — 124807.3613
5. Cranos Williams — 118729.8107

### Eigenvector
1. Cranos Williams — 0.247258
2. Jack Wang — 0.230940
3. Vincent L Chiang — 0.224446
4. Ron Sederoff — 0.215104
5. Chenmin Yang — 0.203376

## Notes

- `weightedDegree` uses `CO_AUTHORED.weight` (number of joint papers) when projected correctly in GDS.
- Some `closeness = 1.0` values can happen in very small components; compare closeness within similar component sizes.

## Detailed Documentation

See `METRICS_GUIDE.md` for:
- what each metric means,
- how to run these metrics in Neo4j GDS,
- why each metric is useful,
- and which algorithm family each GDS metric is based on.
