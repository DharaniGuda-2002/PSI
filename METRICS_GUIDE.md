# Metrics Guide (Neo4j GDS)

This document explains:
- what metrics were computed,
- what the results say,
- how they were computed,
- why they matter,
- and what algorithms Neo4j GDS uses for each.

Notebook reference: `nc_metrics.ipynb`

## 1) Data and Graph Model

The analysis uses a co-authorship graph:

- Node label: `Author`
- Relationship type: `CO_AUTHORED`
- Relationship property: `weight` (number of shared papers)

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

Computed node properties in `centrality.csv`:

- `degree`
- `weightedDegree`
- `betweenness`
- `closeness`
- `eigenvector`
- `community`

## 3) What Each Metric Means and Why It Matters

### Degree
- Meaning: Number of unique co-authors.
- Why: Quick measure of collaboration breadth.
- GDS method: Direct neighborhood count on projected graph.

### Weighted Degree
- Meaning: Sum of edge weights (`CO_AUTHORED.weight`) across neighbors.
- Why: Captures collaboration intensity, not just breadth.
- GDS method: Weighted neighborhood sum.

### Betweenness
- Meaning: How often an author lies on shortest paths between other authors.
- Why: Identifies bridge people connecting subgroups.
- GDS method: Brandes-style shortest-path dependency accumulation.

### Closeness
- Meaning: Inverse of shortest-path distance to reachable authors.
- Why: Identifies authors that can reach others quickly within their component.
- GDS method: Repeated shortest-path computations (BFS for unweighted, Dijkstra-style when weighted shortest paths are used).

### Eigenvector Centrality
- Meaning: High score if connected to other high-scoring authors.
- Why: Captures influence in the collaboration core.
- GDS method: Power-iteration over adjacency structure.

### Community
- Meaning: Cluster membership ID.
- Why: Finds collaboration sub-networks for topic/team analysis.
- GDS method: Depends on the community procedure used during write (`gds.louvain.write`, `gds.leiden.write`, or `gds.labelPropagation.write`).
- In this project output, IDs are numeric partitions; keep using the same procedure for comparability across runs.

## 4) Result Summary (Current `centrality.csv`)

- Authors scored: **1708**
- Distinct communities: **33**
- Largest community: **ID 185** with **213 authors**
- Isolates (`degree = 0`): **4**
- Repeated-collaboration dominance (`weightedDegree > degree`): **880 authors**

Top leaders by metric:

- Degree: Michael Daniele (**131**)
- Weighted Degree: David Jordan (**433**)
- Betweenness: Edgar Lobaton (**173769.0632**)
- Eigenvector: Cranos Williams (**0.247258**)

Important interpretation note:

- Very high `closeness` (including `1.0`) often appears in very small connected components. Compare closeness with component/community context, not alone.

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

### D) Community detection (example: Louvain)

```cypher
CALL gds.louvain.write('co_author_with', {
  writeProperty: 'community'
});
```

### E) Export results

```cypher
MATCH (a:Author)
RETURN
  a.name AS Name,
  a.degree AS degree,
  a.weightedDegree AS weightedDegree,
  a.betweenness AS betweenness,
  a.closeness AS closeness,
  a.eigenvector AS eigenvector,
  a.community AS community
ORDER BY weightedDegree DESC;
```

## 6) Quality Checks Before Running Weighted Metrics

Use this check to prevent the common GDS error about missing weight property:

```cypher
MATCH ()-[r:CO_AUTHORED]-()
RETURN count(r) AS total, count(r.weight) AS withWeight;
```

If missing, initialize weight:

```cypher
MATCH ()-[r:CO_AUTHORED]-()
SET r.weight = 1.0;
```

Then drop/reproject the in-memory graph and rerun metrics.
