# Required Handoff schema

Every kanban task body inlines this section verbatim. Workers fill it
in as part of their completion comment. The structured-handoff
discipline closes the round-trip into the wiki: `scientia-ingest-evidence`
parses these blocks to write `## Implementation Evidence`.

```markdown
## Required Handoff

You must fill in every field below as part of your completion comment.
Empty allowed only where noted.

- **summary** — Short prose, what you did.
- **verification** — The exact command(s) you ran to verify, plus the
  outcome. Example: `pytest -k refunds` → green (12 passed, 0 failed).
- **changed_files** — A YAML list of paths (relative to repo root):
    ```yaml
    changed_files:
      - src/refunds/service.py
      - tests/refunds/test_service.py
    ```
- **dependencies** — Runtime or build dependencies introduced or
  modified (or "none"):
    ```yaml
    dependencies:
      - "added: pydantic>=2.0"
      - "removed: marshmallow"
    ```
- **blocked_reason** — Only populated when you mark the task `blocked`,
  not `done`. Empty string otherwise.
- **retry_notes** — Only populated when this task transitions back to
  `ready` after `blocked` (the previous attempt's notes for the next
  attempt). Empty string otherwise.
- **residual_risk** — Honest list of known unknowns the next reader
  should be aware of. Use "none known" only when you mean it.
- **branch_head** — The commit SHA of your worker branch at completion.
  Load-bearing for the `git:worker-branch-merged` preflight gate the
  integrator runs.
- **wiki_spec** — The `@wiki-spec` tag value from this task's title or
  metadata.
- **wiki_adr_ids** — A YAML list of ADR ids cited by the originating
  spec.
```

Notes:

- All fields are required; "none" / "none known" / empty-string are
  the canonical sentinels for absence.
- The handoff is parsed by `scientia-ingest-evidence`'s
  `handoff_extract.py` script. Drift between this schema and that
  script's parser must be fixed in the same change.
