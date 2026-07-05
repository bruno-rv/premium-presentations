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
| 1 | Title | Opening | graphify corpus subtitle | slide--title |
| 2 | Hook Quote | Hook | RAG as #3 god node | slide--quote |
| 3 | Content | The problem | Vanilla loop, community C4 | STAT + WHY |
| 4 | Divider | Act 1 — RAG | How RAG works | DIV+ |
| 5 | Content | Open book AI | Parametric vs retrieval, bullet lists | slide--split panels |
| 6 | Content | How it works | 4-step query loop (ask→search→read→answer) | PIPE pipeline-vertical |
| 7 | Content | Getting ready to search | Ingestion pipeline: chunk→embed→index | FLOW+ live-flow (4 nodes) |
| 8 | Content | What changes | Accurate / fresh / traceable | STAT + WHY |
| 9 | Divider | Act 2 — Vector | Vector databases | DIV+ |
| 10 | Content | Search evolution | Keyword→meaning→hybrid | TL timeline |
| 11 | Content | Vector databases | Embeddings as coordinates + Spotify example | slide--split + stage-card |
| 12 | Content | Vector jargon, decoded | Embedding, cosine similarity, HNSW, ANN | GLOSS term-links |
| 13 | Content | Retrieval in code | Qdrant client search snippet | GL glass-code-window |
| 14 | Content | Query from the terminal | curl → Qdrant HTTP search | TERM terminal-window |
| 15 | Content | Retrieval benchmark | Keyword vs vector vs hybrid recall@10 | BAR bar-chart |
| 16 | Diagram | Similarity vs connection | Vector vs graph Mermaid flowchart | slide--diagram |
| 17 | Divider | Act 3 — Graph | Graph knowledge | DIV+ |
| 18 | Content | Vector vs Graph | Compare & choose, tech table | P9 compare-split + why-panel |
| 19 | Content | Choosing the right store | Vector-or-graph decision checklist | CHK checklist grid |
| 20 | Closing Quote | Closing | vectors + graphs + RAG | slide--quote |

---

*Spec format: premium-presentations compatible*
