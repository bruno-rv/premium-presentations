# RAG VECTOR GRAPH — Slide Generation Spec

> Read BEFORE generating `rag-vector-graph-slides.html`.

---

## Lesson Metadata

| Field | Value |
|-------|-------|
| **Code** | RAG VECTOR GRAPH |
| **Title** | RAG, Vector & Graph Databases |
| **Title (Split)** | Line 1: "RAG, Vector" / Line 2: "Graph Databases" (shimmer on line 2) |
| **Subtitle** | AI Engineering · graphify corpus |
| **Module** | 01 — Retrieval systems |
| **Duration** | 15 min |
| **Layer** | 2 — Applied AI engineering |
| **Hook** | "RAG is the #3 god node in the corpus" |
| **Closing** | Vectors for similarity, graphs for relationships, RAG to tie both |

---

## Teaching Objective

Learner understands what RAG is, how vector databases power semantic retrieval, how graph databases model relational knowledge, and when to use each — grounded in graphify communities C4 (Foundation Models & RAG) and C13 (Vector Search Infrastructure).

---

## Evidence Data

| Fact | Source |
|------|--------|
| RAG hub: 10 edges in graphify god nodes | GRAPH_REPORT.md |
| Communities: Foundation Models & RAG (32 nodes), Vector Search (16 nodes) | graphify |
| Retriever → term-based (BM25, Elasticsearch) + embedding-based (vector DB) | AI Engineering Ch.6 |
| ANN: FAISS, HNSW, PQ, LSH | AI Engineering Ch.6 |
| Qdrant in LLM Engineer Handbook stack | graphify |
| Advanced RAG: hybrid, RRF, reranking, contextual retrieval | AI Engineering + LLM Handbook |
| Eval: Ragas, ARES, context precision/recall | graphify community 19 |
| Graph KR: Knowledge Representation, Ontology, Bayesian networks (AIMA) | graphify |

---

## Slide Map

| # | Type | Title | Key Content | Visual Pattern |
|---|------|-------|-------------|----------------|
| 1 | Title | RAG, Vector & Graph Databases | graphify corpus subtitle | slide--title |
| 2 | Hook Quote | Hook | RAG as #3 god node | slide--quote |
| 3 | Content | What is RAG | Vanilla loop, community C4 | STG stage-card + split |
| 4 | Divider | Act 1 | How RAG works | DIV+ |
| 5 | Content | Parametric vs retrieval | Weights vs store, bullet lists | slide--split panels |
| 6 | Content | RAG pipeline | Ingest→Generate | FLOW+ live-flow (4 nodes) + WHY |
| 7 | Content | Corpus map | C4, C13, 10 edges | STAT + WHY |
| 8 | Divider | Act 2 | Vector databases | DIV+ |
| 9 | Content | Retrieval evolution | TF-IDF→hybrid | TL timeline |
| 10 | Content | Vector internals | Embed→ANN→filter | PIPE |
| 11 | Diagram | Vector vs graph | Mermaid flowchart | slide--diagram |
| 12 | Divider | Act 3 | Graph knowledge | DIV+ |
| 13 | Content | Compare & choose | Tech table | P9 + content-grid + table |
| 14 | Closing Quote | Closing | vectors + graphs + RAG | slide--quote |

---

*Spec format: premium-presentations compatible*
