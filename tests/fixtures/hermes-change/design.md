---
change-id: 2026-05-28-rag-replacement
created: 2026-05-28
---

# Design: RAG replacement

## Overview

Replace the stateless RAG path with the stateful wiki + confidence model.

## Container Diagram (C4 L2)

```mermaid
C4Container
    title Containers — RAG replacement
    Person(operator, "Operator")
    Container(pkg, "scientia", "Python", "Deterministic core")
    ContainerDb(store, "Filesystem stores", "markdown", "wiki/ and proposals/")
    Rel(operator, pkg, "drives")
    Rel(pkg, store, "reads / writes")
```

## Component Map
- confidence: src/scientia/confidence.py, tests/modules/test_confidence.py
- wiki: src/scientia/wiki/**, tests/modules/test_wiki.py

## Shared Contracts
- confidence.EffectiveScore — owner: confidence — ratified-by: ADR-0004
