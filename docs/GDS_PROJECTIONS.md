# GDS Projections

This document describes the common Neo4j Graph Data Science projections used in this repository.

## Author Co-authorship Projection

The main graph for metric analysis is a co-authorship network projected from `Author` nodes and `CO_AUTHORED` relationships.

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

This projection preserves the `weight` property on `CO_AUTHORED` relationships, where `weight` represents the number of shared papers between two authors.

## Topic-Aware Projections

A second, more advanced projection can combine authors and topics to support bipartite or metadata-aware analysis.

For example, use the `Paper` and `Topic` structure to build a topic-linked projection:

```cypher
CALL gds.graph.project(
  'author_topic',
  ['Author','Topic'],
  {
    AUTHORED: {
      orientation: 'UNDIRECTED'
    },
    HAS_TOPIC: {
      orientation: 'UNDIRECTED'
    }
  }
);
```

This projection is useful when you want to measure author influence through shared topical context rather than direct co-authorship alone.

## Metrics from Projections

The `co_author_with` projection is used for standard author centrality metrics.

The `author_topic` projection can be used for:

- topic-driven connectivity analysis,
- hybrid community detection across authors and topics,
- exploration of how topic nodes bridge otherwise disconnected authors.

## Best Practices

- Clear and rebuild the projection when the underlying graph changes.
- Use `writeProperty` in `gds.*.write` calls to persist scores back to the `Author` nodes.
- If a projection is no longer needed, drop it:

```cypher
CALL gds.graph.drop('co_author_with');
CALL gds.graph.drop('author_topic');
```

## Example Metric Writes

```cypher
CALL gds.degree.write('co_author_with', {
  writeProperty: 'degree'
});

CALL gds.eigenvector.write('co_author_with', {
  writeProperty: 'eigenvector'
});

CALL gds.louvain.write('co_author_with', {
  writeProperty: 'community'
});
```
