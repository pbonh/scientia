# Per-profile Hermes model configuration — schema reference

The `hermes.profiles` block in `development/config.yaml` gives the user
fine-grained, per-profile control over which model each scientia agent
profile uses. The schema mirrors Hermes' own per-profile `config.yaml`
keys 1:1, so examples from
[Hermes' configuring-models guide](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models)
copy across without translation.

This page documents what scientia accepts. For the meaning of any
individual key — what `compression` does, what `provider: auto` resolves
to, which providers are supported — consult Hermes' docs.

## Where the block lives

`development/config.yaml`:

```yaml
hermes:
  # ... existing keys (max_concurrent_children, profile_names, ...) ...
  profiles:
    <role>:
      model: { ... }
      auxiliary:
        <task>: { ... }
      model_aliases:
        <alias>: { ... }
```

`<role>` is the **scientia logical role** — `implementer`, `reviewer`,
`integrator`, or `aggregator` — not the Hermes profile name. The
role-to-name lookup happens via `hermes.profile_names` in the same
config. (Default: `scientia-<role>`.)

## How it's applied

`scientia-kanban-init` step 3b walks every declared role, reads each
profile's current effective config via
`hermes -p <resolved-name> config show --json`, and runs
`hermes -p <resolved-name> config set <dotted-key> <value>` for every
leaf where the declared and effective values differ. Keys already at
their declared values are no-ops.

`scientia-kanban-emit` runs the same comparison as a preflight and
**refuses to emit on drift**. Hand-edits to
`~/.hermes/profiles/<name>/config.yaml` that disagree with
`hermes.profiles` are surfaced as drift; the user re-runs
`scientia-kanban-init` (which is authoritative) to converge.

## Hands-off default

When `hermes.profiles` is absent, scientia touches no model config and
the drift check is a no-op. Every profile inherits whatever the Hermes
host-level `~/.hermes/config.yaml` provides. Existing repos upgrading
to a scientia build that ships this feature see no behavior change
unless they explicitly add the block.

## Accepted keys

### `hermes.profiles.<role>`

| Key            | Type                 | Required | Notes |
|----------------|----------------------|----------|-------|
| `model`        | mapping              | no       | Main-model block (see below). |
| `auxiliary`    | mapping              | no       | Per-task overrides (see below). |
| `model_aliases`| mapping              | no       | Named shortcuts (see below). |

Anything else under `<role>` is rejected at load time.

### `hermes.profiles.<role>.model`

The main model used for the profile's agent loop.

| Key         | Type   | Required | Notes |
|-------------|--------|----------|-------|
| `provider`  | string | no       | e.g. `anthropic`, `openrouter`, `x-ai`. |
| `default`   | string | no       | Model identifier, e.g. `claude-opus-4.7` or `anthropic/claude-opus-4.7`. |
| `base_url`  | string | no       | Custom base URL; empty string = provider default. |
| `api_mode`  | string | no       | e.g. `chat_completions`. |

### `hermes.profiles.<role>.auxiliary.<task>`

Per-task overrides for Hermes' specialized auxiliary models. `<task>`
must be one of:

- `compression`
- `vision`
- `web_summary`
- `approval_scoring`
- `mcp_routing`
- `session_titles`
- `skill_search`

Each task block accepts:

| Key                 | Type   | Notes |
|---------------------|--------|-------|
| `provider`          | string | `auto` (use main model) or a provider name. |
| `model`             | string | Empty string = use main when `provider: auto`. |
| `base_url`          | string | Provider URL override. |
| `api_key`           | string | Per-task key; usually preferred over `.env` for non-secret routing. |
| `timeout`           | int    | Seconds. |
| `extra_body`        | mapping or bool | Provider-specific extras. |
| `download_timeout`  | int    | Seconds. Used by vision/web-summary. |

`provider: auto` and `provider: ''` are treated as equivalent for
drift-check purposes (both mean "let Hermes pick").

### `hermes.profiles.<role>.model_aliases.<alias>`

Named shortcuts for use inside the profile's agent. Both keys are
required:

| Key       | Type   | Required | Notes |
|-----------|--------|----------|-------|
| `model`   | string | yes      | The model the alias resolves to. |
| `provider`| string | yes      | The provider it resolves on. |

## Validation rules

- Role names must be one of `implementer`, `reviewer`, `integrator`,
  `aggregator`. Any other key under `hermes.profiles` is rejected.
- Top-level keys under a role must be one of `model`, `auxiliary`,
  `model_aliases`. Anything else is rejected.
- Keys under `model` must be one of `provider`, `default`, `base_url`,
  `api_mode`.
- Tasks under `auxiliary` must be one of the seven listed above.
- Keys under each task must be one of `provider`, `model`, `base_url`,
  `api_key`, `timeout`, `extra_body`, `download_timeout`.
- Each `model_aliases.<alias>` must have exactly `model` and `provider`
  keys — no more, no less.
- scientia does **not** validate that model strings exist on the chosen
  provider. That's Hermes' job at `config set` time (which validates
  what it can), and ultimately the provider's call at first use.

## Worked example

```yaml
hermes:
  max_concurrent_children: 3
  profile_names:
    implementer: scientia-implementer
    reviewer:    scientia-reviewer
    integrator:  scientia-integrator
    aggregator:  scientia-aggregator
  profiles:
    # Premium main model for the role that writes code.
    implementer:
      model:
        provider: anthropic
        default: claude-opus-4.7
      auxiliary:
        vision:
          provider: openrouter
          model: google/gemini-2.5-flash

    # Mid-tier for review.
    reviewer:
      model:
        provider: anthropic
        default: claude-sonnet-4.6

    # Cheap model for the aggregator (just summarizes finished children).
    aggregator:
      model:
        provider: anthropic
        default: claude-haiku-4.5

    # integrator omitted -> inherits Hermes host default.
```

A user changing `claude-sonnet-4.6` to `claude-haiku-4.5` for reviewer
and re-running `scientia-kanban-init` sees one
`hermes -p scientia-reviewer config set model.default claude-haiku-4.5`
call and a log line `model-config-applied — profile=reviewer(scientia-reviewer)
applied=1 unchanged=0`. The next `scientia-kanban-emit` proceeds normally.

If between init and emit a user hand-edits
`~/.hermes/profiles/scientia-reviewer/config.yaml` to set `default:
claude-opus-4.7`, the next emit refuses with:

```
profile model config drift on scientia-reviewer (role=reviewer):
  model.default: scientia='claude-haiku-4.5' hermes='claude-opus-4.7'.
Fix: re-run scientia-kanban-init to converge, or update development/config.yaml
hermes.profiles to match the intended state.
```

## What's out of scope

- **Per-tenant overrides.** `hermes.profiles` is global to the repo. If
  per-tenant model selection is needed, it would layer
  `tenants.<name>.hermes.profiles` on top of this — but that's a
  separate change.
- **Provider credentials.** `.env` files under
  `~/.hermes/profiles/<name>/` are the user's domain. scientia stays
  out of secret material.
- **Recommended defaults.** No models are picked for the user. An
  absent block means "inherit Hermes' host defaults," which is what
  existing repos already get.
