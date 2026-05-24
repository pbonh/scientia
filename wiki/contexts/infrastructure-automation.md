---
title: "Infrastructure Automation"
type: context
tags: [context, bounded-context, generic]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Ansible as a declarative configuration-management and orchestration
tool: playbooks and roles, inventory, variables and facts, conditionals,
delegation, async tasks, check mode, collections, vault, and
error-handling control flow. Owns the *declarative-automation*
vocabulary.

## Subdomain Classification

**Generic.** Configuration management is commodity infrastructure
tooling (Ansible/Salt/Puppet are substitutable for scientia's needs).
Reference knowledge in the wiki, not a scientia differentiator.

## In-Scope Concepts

- [[concepts/ansible-async-tasks]]
- [[concepts/ansible-check-mode]]
- [[concepts/ansible-collections]]
- [[concepts/ansible-conditionals]]
- [[concepts/ansible-delegation]]
- [[concepts/ansible-error-handling]]
- [[concepts/ansible-facts]]
- [[concepts/ansible-inventory]]
- [[concepts/ansible-playbook]]
- [[concepts/ansible-roles]]
- [[concepts/ansible-variables]]
- [[concepts/ansible-vault]]

## In-Scope Entities

- [[entities/ansible]]
- [[entities/ansible-core]]
- [[entities/ansible-galaxy]]

## Ubiquitous Language (Glossary)

- **Playbook** — a YAML file describing plays (ordered task sets)
  against hosts.
- **Role** — a reusable, structured bundle of tasks/vars/handlers.
- **Inventory** — the declared set of managed hosts and their grouping.
- **Fact** — a discovered property of a managed host, gathered at run.
- **Variable** — templated (Jinja2) configuration value.
- **Conditional** — a `when:` clause gating task execution.
- **Delegation** — running a task on a host other than the current
  target (`delegate_to`).
- **Check mode** — a dry run that reports changes without applying them.
- **Vault** — encrypted storage for secrets within playbooks.
- **Collection** — a packaged distribution of roles/modules/plugins.

## False Cognates with Adjacent Contexts

- **"delegation"** here (`ansible-delegation`, run a task elsewhere) is a
  false cognate of `hermes-subagent-delegation`
  ([[contexts/autonomous-agent-orchestration]]) and `pi-subagent`
  delegation ([[contexts/coding-agent-platform]]) — Ansible delegates a
  *task to a host*, agents delegate *work to a child agent*.
- **"error handling"** (`ansible-error-handling`, block/rescue/ignore)
  is a false cognate of Rust `Result`-based error handling
  ([[contexts/rust-systems-programming]]).
- **"collection"** (a packaged distribution) is unrelated to any
  data-structure "collection".
- **"template" (Jinja2 variables)** collides with the templating systems
  in [[contexts/fuzzy-finder]] and
  [[contexts/coding-agent-platform]] — see
  [[context-maps/terminal-tooling]].

## Sources

- [[summaries/ansible-user-guide]]
