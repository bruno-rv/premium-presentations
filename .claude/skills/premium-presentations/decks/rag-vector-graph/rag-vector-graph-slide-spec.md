# RAG-VECTOR-GRAPH — Slide Generation Spec

> Read BEFORE generating `rag-vector-graph-slides.html`.

---

## Lesson Metadata

| Field | Value |
|-------|-------|
| **Code** | RAG-VECTOR-GRAPH |
| **Title** | RAG, Vector Databases and Graph Databases |
| **Title (Split)** | Line 1: "RAG, Vector & Graph" / Line 2: "Databases" (shimmer on line 2) |
| **Subtitle** | How retrieval, similarity search, and relationships compose modern AI systems |
| **Module** | Data & AI Architecture |
| **Duration** | ~25 min (16 slides) |
| **Language** | en |
| **Hook** | "Models memorize patterns — they do not know your data. RAG grounds answers; vectors find meaning; graphs preserve structure." |
| **Closing** | "Start with vectors for semantic search. Add graphs when relationships are the product. Measure retrieval before you tune the model." |

---

## Teaching Objective

Audience leaves knowing: (1) what RAG is and its offline/online pipeline, (2) why vector DBs exist and how embedding + ANN search works, (3) what graph DBs add for multi-hop and entity-centric queries, (4) when to combine them (GraphRAG, hybrid retrieval). Tone: technical but clear; one idea per slide.

---

## Slide Map

| # | Type | Title | Key Content | Visual Pattern |
|---|------|-------|-------------|----------------|
| 1 | Title | RAG, Vector & Graph | Tags, subtitle, shimmer title | slide--title + glow + geo |
| 2 | Hook Quote | Grounding beats guessing | Hook quote | slide--quote + glow |
| 3 | Roadmap | Three lenses | RAG → Vector → Graph → Hybrid | **P14** journey-path |
| 4 | Divider | Act 1 — RAG | Ghost 01, shimmer | **DIV+** divider-act |
| 5 | Content | What is RAG? | Definition; core loop | slide--content + why-panel |
| 6 | Diagram | RAG pipeline | Offline/online flow | Mermaid flowchart |
| 7 | Stats | Where RAG fails | Bad chunks, stale index, weak recall | **STAT** stats-row |
| 8 | Divider | Act 2 — Vectors | Ghost 02 | **DIV+** divider-act |
| 9 | Split | Embeddings | Geometry + similarity | **GL** glass-code-window |
| 10 | Table | Vector DB landscape | pgvector … Chroma | data-table |
| 11 | Diagram | ANN retrieval | HNSW → top-k → rerank | Mermaid |
| 12 | Divider | Act 3 — Graphs | Ghost 03 | **DIV+** divider-act |
| 13 | Stage | Graph relationships | Nodes/edges + 3-hop example | **STG** stage-card + SVG |
| 14 | Compare | Vector vs graph | When to use each | **P9** compare-split |
| 15 | Diagram | Hybrid retrieval | Vector + graph + rerank | Mermaid |
| 16 | Closing | Measure retrieval first | Quote | slide--quote + glow |

---

## Design Directives

- Framework: **Warm Signal** (`data-theme="warm"`), `premium-components.css` linked.
- Generic branding only — no course chrome unless requested.
- English copy throughout.
- `data-nav-title` on each `<section>` for dot labels.

---

*Rebuilt with Premium Presentations component library — bundle via `./scripts/bundle-deck.sh`.*
