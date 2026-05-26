---
title: "C4 Model"
type: concept
tags: [concept, architecture, diagramming, documentation]
created: 2026-05-23
updated: 2026-05-26
sources: ["raw/intent-driven-template/skills.md", "raw/c4model-com-home.md"]
confidence: high
---

## Definition

The **C4 model** is an approach to diagramming software architecture as a small
set of hierarchical, zoomable views — **C**ontext, **C**ontainer, **C**omponent,
and **C**ode — supplemented by **dynamic** (sequence) and **deployment** views. Its
purpose is to communicate boundaries, responsibilities, actors, dependencies, and
data flow at the right level of abstraction, drawing only the levels that add
value rather than exhaustively documenting a system. The
[[entities/intent-driven-template]] ships a `c4-diagrams` skill that produces
C4-style diagrams in ASCII or plain Mermaid to clarify architecture before
detailed design.

Per its creator [[entities/simon-brown|Simon Brown]] (c4model.com), C4 is an
**"abstraction-first"** approach: the diagram levels are simply views over a
small set of [[concepts/c4-abstractions|C4 abstractions]] (person, software
system, container, component, code) that mirror how teams build software. The
model is deliberately **notation independent** (not tied to UML, ArchiMate,
etc.) and **tooling independent** (a whiteboard works as well as
diagramming-as-code), and frames the diagrams as *maps of your code* at varying
levels of zoom.

## How It Works

C4 organizes diagrams as a set of nested maps that progressively zoom in:

| Level | Shows | Use when | Avoid when |
|-------|-------|----------|------------|
| System Context | Users, external systems, and the system's scope | Identifying actors and scope | Scope is already obvious and local |
| Container | Deployable/runnable units, data stores, APIs, CLIs, queues | Showing runtime building blocks | You only need code-level call flow |
| Component | The internals of one container | Explaining one container's parts | The container has few meaningful parts |
| Code | Critical classes/modules (rare) | A component diagram is insufficient | A component diagram would do |
| Dynamic | A request/event/workflow sequence | Behaviour over time is the question | Static structure is the question |
| Deployment | Infrastructure, nodes, networks, placement | Runtime placement matters | Deployment is unknown or irrelevant |

A typical workflow: decide **purpose** (existing code vs. new system vs. design
review), **format** (ASCII or plain Mermaid `flowchart`/`sequenceDiagram` — *not*
C4-specific Mermaid), and **rigor** (strict C4, lightweight C4-inspired, or
hybrid); for existing code, inspect entry points, runtime boundaries,
integrations, and persistence before drawing; pick the smallest useful diagram
set, starting with system context or container; then explain the diagram in 3-6
bullets covering boundaries, responsibilities, key relationships, assumptions, and
open questions.

A key discipline is not mixing levels: **containers are runnable/deployable units;
components live inside a single container** and modules are usually components, not
containers.

## Key Parameters

- **Level selection**: draw only the levels that answer the current question;
  challenge requests to produce all four levels for small systems.
- **Format**: ASCII boxes-and-arrows or portable plain Mermaid; concrete labels
  (actor, system, container, component, database, queue, external service).
- **Assumptions & open questions**: always stated when diagramming a future or
  incomplete system, or when boundaries/ownership/data flow are uncertain.

## When To Use

- Explaining existing code architecture to a new contributor or reviewer.
- Visualizing a new system's boundaries before committing to detailed design — the
  [[concepts/intent-driven-schema|intent-driven schema's]] design stage is a
  natural place to use it.
- Mapping software boundaries during a design review, then stopping before
  line-by-line design unless the diagram is approved.

## Risks & Pitfalls

- **Drawing all four levels by default** — produces low-value diagrams nobody
  maintains; draw only what answers the question.
- **Jumping straight to detailed design** — validate context/container boundaries
  first.
- **C4-specific Mermaid syntax** — hurts portability; use plain `flowchart` /
  `sequenceDiagram`.
- **Treating modules as containers** — conflates levels and misleads readers;
  modules are almost always *components*. Likewise, a C4 **container is not a
  Docker container** — it is any separately runnable/deployable application or
  data store (see [[concepts/c4-abstractions]]).
- **Hiding uncertainty** — omitting assumptions/open questions makes a speculative
  diagram look authoritative.

## Related Concepts

- [[concepts/c4-abstractions]] — the person/system/container/component/code vocabulary the diagram levels view
- [[concepts/separation-of-concerns]] — the boundaries C4 makes visible
- [[concepts/loose-coupling]] — a property the dependency edges expose
- [[concepts/abstraction]] — C4 levels are layered abstractions of one system
- [[concepts/intent-driven-schema]] — a workflow whose design stage uses C4 diagrams
- [[concepts/architectural-decision-record]] — records the rationale behind the boundaries C4 draws

## Sources

- [c4-diagrams skill](https://github.com/intent-driven-dev/intent-driven-template/tree/main/.agents/skills/c4-diagrams) (`raw/intent-driven-template/skills.md`)
- [c4model.com](https://c4model.com/) — the official C4 model site by [[entities/simon-brown|Simon Brown]] (`raw/c4model-com-home.md`)
