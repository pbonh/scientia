---
change-id: 2026-05-28-rag-replacement
created: 2026-05-28
---

# Tasks

Ordered, dependency-aware checklist with 0.2 ownership markers.

<!-- traces-spec: confidence-math#effective-score -->
<!-- traces-adr: ADR-0004 -->
<!-- component: confidence -->
<!-- touches: src/scientia/confidence.py -->
<!-- produces-contract: confidence.EffectiveScore -->
- [ ] **1.** Define the EffectiveScore contract

<!-- traces-spec: confidence-math#multiplier-curve -->
<!-- traces-adr: ADR-0004 -->
<!-- component: confidence -->
<!-- touches: src/scientia/confidence.py -->
<!-- uses-contract: confidence.EffectiveScore -->
- [ ] **2.** Add the source-count multiplier (depends on #1)

<!-- traces-spec: confidence-math#contradiction-floor -->
<!-- component: confidence -->
<!-- touches: src/scientia/confidence.py -->
<!-- uses-contract: confidence.EffectiveScore -->
- [ ] **3.** Add the contradiction floor and effective recompute (depends on #2)

<!-- traces-spec: kg-wiki-model#dump -->
<!-- component: wiki -->
<!-- touches: src/scientia/wiki/__init__.py -->
- [ ] **4.** Roll the new score into the wiki dump (depends on #1, #3)
