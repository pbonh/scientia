---
title: "The C4 Model for Visualising Software Architecture (c4model.com)"
type: summary
tags: [summary, architecture, diagramming, documentation]
created: 2026-05-26
updated: 2026-05-26
sources: ["raw/c4model-com-home.md"]
confidence: high
---

## Overview

c4model.com is the official website for the **C4 model**, an "easy to learn,
developer friendly approach to software architecture diagramming" written and
maintained by its creator, [[entities/simon-brown|Simon Brown]]. The site
positions the model as an **abstraction-first** way of describing software
architecture: rather than starting from a notation, you start from a small set
of abstractions that mirror how architects and developers actually think about
and build software, and only then draw diagrams of them.

The model has two halves. First, a hierarchical set of **abstractions** —
person, software system, container, component, and code element — that nest
inside one another (a system is made of containers, which contain components,
which are implemented by code elements). Second, a hierarchical set of **static
structure diagrams** named after the model's four C's — (system) **C**ontext,
**C**ontainer, **C**omponent, and **C**ode — each of which zooms one level
deeper than the last. The guiding metaphor is that these diagrams are *maps of
your code* at different levels of detail, like zooming in and out of an online
map.

Crucially, the site stresses that you do **not** need all four diagram levels;
you draw only the ones that add value, and for most teams the system context
and container diagrams are sufficient. Three supplementary diagram types —
system landscape, dynamic, and deployment — cover the enterprise picture,
runtime collaboration, and infrastructure mapping respectively.

The C4 model is explicitly **notation independent** (not tied to UML,
ArchiMate, etc.) and **tooling independent** (usable on whiteboards, sticky
notes, or diagramming-as-code tools alike). The website and its example
diagrams are licensed CC BY 4.0.

## Key Claims

- C4 is an **abstraction-first** approach: the [[concepts/c4-abstractions|five
  abstractions]] (person, software system, container, component, code element)
  come before any diagram or notation.
- A **container** in C4 is a separately runnable/deployable unit — an
  application or a data store — and is explicitly *not* a Docker container; a
  **component** lives inside a single container and is not independently
  deployable. See [[concepts/c4-abstractions]].
- The four core [[concepts/c4-model|C4 diagram levels]] (context → container →
  component → code) are zoomable "maps of your code"; you draw only the levels
  that add value, and context + container suffice for most teams.
- Three supplementary diagrams — **system landscape**, **dynamic**, and
  **deployment** — extend the core hierarchy for enterprise scope, runtime
  behaviour, and infrastructure placement.
- The model is deliberately **notation independent** and **tooling
  independent**, complementing rather than replacing
  [[concepts/separation-of-concerns]] and [[concepts/abstraction]].

## Source Metadata

- **Type**: Website / official reference (home, `/abstractions`, `/diagrams`)
- **Owner / Author**: [[entities/simon-brown|Simon Brown]] (creator of the C4 model)
- **URL**: https://c4model.com/
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Ingested on**: 2026-05-26

## Relevant Concepts

- [[concepts/c4-model]] — the diagramming approach and its four zoomable
  diagram levels (extended by this ingest with the authoritative source)
- [[concepts/c4-abstractions]] — the person/system/container/component/code
  abstraction hierarchy that the diagrams are drawn from (new)

## Relevant Entities

- [[entities/simon-brown]] — creator of the C4 model and author of c4model.com (new)
