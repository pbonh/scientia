---
title: "Spec-stage manifest extension — spec-driven-development/2026-05-26-kg-seeded-intent-skills"
type: manifest-spec-extension
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
stage: spec
created: 2026-05-26
extends: core.md
---

## Slice 9 — Tradeoffs & Suggestions (spec stage)

Tradeoffs the wiki documents that these specs are authored to honor, and
that `scientia-intent-design`/`-tasks` should carry forward.

- **Gherkin discipline (mandatory).** One observable `When` per scenario;
  observable `Then` (state a user or another agent can see, not
  implementation noise); named personas; glossary terms used exactly as
  the manifest defines them. Source: [[concepts/gherkin]]. Drift here is a
  false-cognate bug at emit time.
- **Example-based over scenario-outline.** The brief's pipeline is small
  and the behaviours are discrete; specs use concrete example scenarios
  rather than parameterized outlines. Reconsider only if a capability
  shows a true parameter family (e.g. the confidence curve) at design.
- **Idempotency is a first-class outcome.** Every deterministic
  `kg_pipeline` operation is idempotent; this is asserted directly as
  scenarios (recompute, write_page) rather than left to implementation.
  Source: brief §8.
- **Quantitative vs qualitative confidence (false cognate).** The
  produced KG uses a per-claim `[0,1]` model; scientia's own wiki uses
  qualitative high/medium/low. Specs name the quantitative model only.
  Source: core.md slice 4.
- **Automated vs interactive grill (false cognate).** `grill-proposal`
  auto-generates `grill.md` from KG queries; it is not the interactive
  human interview. Specs govern the automated one. Source: core.md slice 4.
- **Provenance is observable.** Seeding and grill outputs must cite the
  wiki claims they draw from with `effective` shown inline — treated as an
  observable `Then`, not a formatting nicety. Source: brief §3.3.
- **Portability constraint (bounds design).** No external services, no
  graph DB, no embeddings; pure-Python stdlib + `pyyaml` (optional
  `networkx`); `str.format_map` templating only. Source: brief §4. ASRs
  and pitfalls (slices 5/6/8) are computed at `scientia-intent-design`.

## Capabilities specced (8)

- kg-wiki-model, kg-confidence, kg-seed-proposal, kg-grill-proposal,
  intent-artifact-generation, wiki-maintenance, pipeline-orchestration,
  pipeline-tooling.
