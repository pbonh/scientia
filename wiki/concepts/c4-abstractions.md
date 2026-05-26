---
title: "C4 Abstractions"
type: concept
tags: [concept, architecture, diagramming, documentation]
created: 2026-05-26
updated: 2026-05-26
sources: ["raw/c4model-com-home.md"]
confidence: high
---

## Definition

The **C4 abstractions** are the small, hierarchical vocabulary the
[[concepts/c4-model|C4 model]] uses to describe the static structure of a
software system *before* any diagram is drawn or any notation is chosen. There
are five: **Person**, **Software System**, **Container**, **Component**, and
**Code element**. They nest: a software system is made up of one or more
containers, each container holds one or more components, and each component is
implemented by one or more code elements; people sit outside the system and use
it. This is what the C4 model means by being **"abstraction-first"** — the
abstractions reflect how architects and developers actually think about and
build software, and the four C4 diagram levels are simply views over them.

## How It Works

| Abstraction | What it is | Deployable? | Examples |
|-------------|-----------|-------------|----------|
| **Person** | An actor, role, persona, or named individual who uses the system | n/a | End user, administrator, external partner |
| **Software System** | The highest level; something that delivers value to its users (human or not) | n/a | The product in scope; a third-party system |
| **Container** | An application or a data store — something that must be *running* for the system to work | Yes — separately runnable/deployable | Server-side web app, SPA, desktop/mobile app, database schema, file system, message bus |
| **Component** | A grouping of related functionality behind a well-defined interface, living inside one container | No — runs inside a container | A controller, a service, a repository, a module |
| **Code element** | The implementation of a component | No | Classes, interfaces, objects, functions, DB tables |

The single most misread abstraction is the **container**: in C4 it is *not* a
Docker/OS container. It is any separately runnable or deployable unit that
executes code or stores data. A **component**, by contrast, is never separately
deployable — it is a logical grouping inside exactly one container. Keeping
these straight is what lets the diagram levels stay honest (see
[[concepts/c4-model]]'s "treating modules as containers" pitfall).

## Key Parameters

- **Nesting depth**: system → container → component → code. You name and reason
  about elements at the depth that answers the current question, not all of them.
- **Person placement**: people are always external to the software system in
  scope; they appear on diagrams as actors, not as containers or components.
- **Container = runnable/deployable**; **component = in-process grouping**.
  The deployability test is the quickest way to classify an element.

## When To Use

- When establishing the **ubiquitous vocabulary** for an architecture before
  drawing anything — agreeing what counts as a system vs. container vs.
  component prevents level-mixing later.
- When onboarding a contributor: explaining the five abstractions gives them
  the mental model to read any C4 diagram.
- When deciding **which diagram level to draw** — the abstraction you want to
  talk about dictates the level (containers → container diagram, etc.).

## Risks & Pitfalls

- **Calling a Docker/OS container a C4 Container** — a C4 container is a
  runnable/deployable application or data store, not a packaging artifact.
- **Promoting a module to a container** — modules are almost always
  *components*; conflating the two breaks the level hierarchy.
- **Modelling people as systems** — actors are `Person`, external dependencies
  are `Software System`; mixing them obscures scope.
- **Over-decomposing** — naming code elements when a component-level view would
  suffice produces noise nobody maintains.

## Related Concepts

- [[concepts/c4-model]] — the diagramming approach whose four levels are views over these abstractions
- [[concepts/abstraction]] — C4 abstractions are a worked example of layered abstraction
- [[concepts/decomposition]] — the nesting is a disciplined decomposition of a system
- [[concepts/separation-of-concerns]] — container and component boundaries express separated concerns
- [[concepts/loose-coupling]] — the relationships between abstractions expose coupling

## Sources

- [c4model.com — Abstractions](https://c4model.com/abstractions) and the home page (`raw/c4model-com-home.md`), by [[entities/simon-brown|Simon Brown]]
