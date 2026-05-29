# The LLM Wiki Pattern (note)

Retrieval-augmented generation (RAG) rediscovers the same knowledge on every
query: it re-retrieves and re-synthesizes context each time, doing the
integration work over and over.

A better pattern is an LLM-maintained wiki. The agent maintains a persistent
markdown knowledge base, compounding knowledge across sessions. Integration work
is done once, at ingest time; queries then read from pre-synthesized pages.

An open question remains: when does such a wiki drift out of sync with its
sources, and how often should it be linted?
