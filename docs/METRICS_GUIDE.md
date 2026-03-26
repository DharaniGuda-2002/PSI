# Metrics Guide (Neo4j GDS)

This document explains:

- what metrics were computed,
- what algorithms Neo4j GDS uses,
- the core formula behind each metric,
- why each metric matters for this project,
- and how the current `centrality.csv` output should be interpreted.

Notebook reference: `notebooks/nc_metrics.ipynb`

## 1) Data And Graph Model

The analysis uses a co-authorship graph:

- Node label: `Author`
- Relationship type: `CO_AUTHORED`
- Relationship property: `weight` = number of shared papers

Typical projection:

```cypher
CALL gds.graph.project(
  'co_author_with',
  'Author',
  {
    CO_AUTHORED: {
      orientation: 'UNDIRECTED',
      properties: 'weight'
    }
  }
);
```

## 2) Metrics Computed

Computed node properties in `data/centrality.csv`:

- `degree`
- `weightedDegree`
- `betweenness`
- `closeness`
- `eigenvector`
- `community`

## 3) Algorithms And Formulas

### Degree

- Neo4j GDS algorithm: `gds.degree.write`
- Algorithm family: Degree centrality
- Meaning: number of unique co-authors connected to an author
- Formula:

```text
C_D(v) = deg(v)
```

For an undirected graph, this is the number of adjacent neighbors of node `v`.

- Weighted variant used for `weightedDegree`:

```text
C_W(v) = Σ w(v, u), for all neighbors u of v
```

Neo4j GDS computes weighted degree as the sum of positive adjacent relationship weights.

- Why it matters here:
  - `degree` captures collaboration breadth.
  - `weightedDegree` captures collaboration intensity from repeated co-authorship.

### Betweenness

- Neo4j GDS algorithm: `gds.betweenness.write`
- Algorithm basis in GDS:
  - Brandes' approximate algorithm for unweighted graphs
  - multiple concurrent Dijkstra searches for weighted graphs
- Meaning: how often an author lies on shortest paths between other authors
- Formula:

```text
C_B(v) = Σ (σ(s, t | v) / σ(s, t))
```

where:

- `σ(s, t)` is the number of shortest paths from node `s` to node `t`
- `σ(s, t | v)` is the number of those shortest paths that pass through node `v`

- Why it matters here:
  - high-betweenness authors can act as bridges between collaboration groups or disciplinary clusters

### Closeness

- Neo4j GDS algorithm: `gds.closeness.write`
- Algorithm basis in GDS:
  - shortest-path computation across the graph
  - BFS-style traversal for unweighted shortest paths
  - weighted shortest paths when a relationship weight property is used
- Meaning: how close an author is, on average, to other reachable authors
- Raw formula:

```text
C_raw(u) = 1 / Σ d(u, v)
```

- Normalized formula:

```text
C(u) = (N - 1) / Σ d(u, v)
```

where:

- `d(u, v)` is the shortest-path distance from `u` to `v`
- `N` is the number of nodes in the graph

Neo4j GDS also supports the Wasserman-Faust correction for disconnected graphs, but that option is separate from the default computation.

- Why it matters here:
  - high-closeness authors are positioned to reach other authors quickly within their connected component

### Eigenvector Centrality

- Neo4j GDS algorithm: `gds.eigenvector.write`
- Algorithm basis in GDS: Power iteration with L2 normalization after each iteration
- Meaning: an author is important if they are connected to other important authors
- Formula:

```text
x_v = (1 / λ) Σ A_uv x_u
```

or in matrix form:

```text
Ax = λx
```

where:

- `A` is the adjacency matrix
- `x` is the eigenvector centrality score vector
- `λ` is the dominant eigenvalue

Neo4j GDS computes the eigenvector associated with the largest absolute eigenvalue.

- Why it matters here:
  - high-eigenvector authors sit in influential parts of the collaboration core, not just high-degree positions

### Community Detection

- Neo4j GDS algorithm: `gds.louvain.write`
- Algorithm name: Louvain method
- Objective: maximize graph modularity
- Modularity formula:

```text
Q = (1 / 2m) Σ [A_ij - (k_i k_j / 2m)] δ(c_i, c_j)
```

where:

- `A_ij` is the edge weight between nodes `i` and `j`
- `k_i` and `k_j` are node degrees or weighted degrees
- `m` is the total number of edges or total edge weight
- `δ(c_i, c_j)` is `1` if nodes `i` and `j` are in the same community, otherwise `0`

The Louvain algorithm is hierarchical: it repeatedly improves modularity locally, then compresses each community into a super-node and repeats the process.

- Why it matters here:
  - it identifies collaboration sub-networks that may correspond to research groups, topical clusters, or repeated collaboration communities

## 4) Result Summary (Current `centrality.csv`)

- Authors scored: **1708**
- Distinct communities: **33**
- Largest community: **ID 185** with **213 authors**
- Isolates (`degree = 0`): **4**
- Authors with `weightedDegree > degree`: **880**

Top leaders by metric:

- Degree: Michael Daniele (**131**)
- Weighted Degree: David Jordan (**433**)
- Betweenness: Edgar Lobaton (**173769.0632**)
- Eigenvector: Cranos Williams (**0.247258**)

Important interpretation note:

- Very high `closeness` values can appear in very small connected components, so they should be interpreted with component context.

## 5) Reproducible GDS Workflow

### A) Project graph

```cypher
CALL gds.graph.project(
  'co_author_with',
  'Author',
  {
    CO_AUTHORED: {
      orientation: 'UNDIRECTED',
      properties: 'weight'
    }
  }
);
```

### B) Degree and weighted degree

```cypher
CALL gds.degree.write('co_author_with', {
  writeProperty: 'degree'
});

CALL gds.degree.write('co_author_with', {
  relationshipWeightProperty: 'weight',
  writeProperty: 'weightedDegree'
});
```

### C) Other centralities

```cypher
CALL gds.betweenness.write('co_author_with', {
  writeProperty: 'betweenness'
});

CALL gds.closeness.write('co_author_with', {
  writeProperty: 'closeness'
});

CALL gds.eigenvector.write('co_author_with', {
  writeProperty: 'eigenvector'
});
```

### D) Community detection

```cypher
CALL gds.louvain.write('co_author_with', {
  writeProperty: 'community'
});
```

### E) Export results

This repository can export the results directly with the Python script:

```bash
python3 scripts/export_centrality.py
```

That script connects to Neo4j, runs the metric workflow, and writes `data/centrality.csv`.

## 6) Quality Checks Before Running Weighted Metrics

Use this check to confirm that `CO_AUTHORED.weight` exists before weighted metrics run:

```cypher
MATCH ()-[r:CO_AUTHORED]-()
RETURN count(r) AS total, count(r.weight) AS withWeight;
```

If any weights are missing:

```cypher
MATCH ()-[r:CO_AUTHORED]-()
WHERE r.weight IS NULL
SET r.weight = 1.0;
```

Then drop and re-project the in-memory GDS graph before rerunning the metrics.
