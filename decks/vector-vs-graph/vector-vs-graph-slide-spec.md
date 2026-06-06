# VECTOR VS GRAPH — Slide Generation Spec

> Read BEFORE generating `vector-vs-graph-slides.html`.

---

## Lesson Metadata

| Field | Value |
|-------|-------|
| **Code** | VVG |
| **Title** | Vector vs Graph Databases — when to use both |
| **Title (Split)** | Line 1: "Vector vs Graph" / Line 2: "— when to use both" (shimmer on line 2) |
| **Subtitle** | Decision-making for retrieval architectures |
| **Module** | 04 — Retrieval & Knowledge |
| **Duration** | 15 min |
| **Instructor** | Bruno Veloso |
| **Layer** | 3 — Decision & Comparison |
| **Mode** | Self-Paced |
| **Hook** | "Retrieval is more than one trick. Pick the primitive the problem actually needs." |
| **Closing** | "Vectors find meaning. Graphs find structure. Use both when the answer lives in the path." |

---

## Teaching Objective

Learner walks away able to *decide* between a vector DB, a graph DB, or a hybrid for a new retrieval problem — without falling for "just add embeddings" or "just add a knowledge graph" reflexes. Pacing: ~60s per content slide, ~30s on dividers/quotes. Tone: comparative, decisive, evidence-led.

---

## Overlap Avoidance

| Already covered | Where | This lesson differs |
|-----------------|-------|---------------------|
| What a vector DB is, ANN, hybrid BM25+vector | VECTOR-DATABASES deck | We assume it. This deck asks *when* — not *what*. |
| What a graph DB is, Cypher, property graphs | GRAPH-DATABASES deck | Same. We use graph + vector as primitives, not teach them. |
| RAG architectures, GraphRAG as a concept | RAG-VECTOR-GRAPH deck | We *cite* GraphRAG as a hybrid pattern, not re-derive it. |

**Key rule:** Decision frame, not tutorial. Every slide answers "given X, what do I pick?" — never "how do I build X?"

---

## Slide Map

| # | Type | Title | Key Content | Visual Pattern | Why Panel |
|---|------|-------|-------------|----------------|----------|
| 1 | Title | Vector vs Graph | Subtitle: "when to use both" | slide--title | — |
| 2 | Hook Quote | Hook | "Retrieval is more than one trick" | slide--quote | — |
| 3 | Content | The mental model | vectors=similarity, graphs=relationship, content-grid + aside | content-grid / aside-card | "Same query, two complementary lenses" |
| 4 | Divider 01 | Two primitives | Act break 01 | slide--divider (ghost "01") | — |
| 5 | Content | Where vectors win | semantic search, recs, dedup, image/audio | stats-row (4 cards) | "Pick vectors when 'find similar X' is the question" |
| 6 | Content | Where graphs win | connected queries, lineage, fraud, knowledge | stats-row (4 cards) | "Pick graphs when 'follow the path' is the question" |
| 7 | Divider 02 | Where they fall short | Act break 02 | slide--divider (ghost "02") | — |
| 8 | Content | Limits of vector-only | multi-hop blind, no explainability, context-blind | compare-split or 3 panels | "High recall, low reasoning" |
| 9 | Content | Limits of graph-only | no fuzzy similarity, no semantic vibe | compare-split mirror | "Perfect recall, narrow lens" |
| 10 | Divider 03 | Hybrid | Act break 03 | slide--divider (ghost "03") | — |
| 11 | Content | The hybrid pattern | vectors AS graph properties; ANN + traversal | compare-split + code-window | "One query, two storage shapes, one answer" |
| 12 | Content | GraphRAG | Microsoft 2024: community detection + summarization | compare-split or setup-flow | "Global summarization QA needs the graph scaffold" |
| 13 | Content | Decision matrix | problem → pick (table) | data-table inside table-scroll | "When in doubt, walk the matrix" |
| 14 | Closing Quote | Closing | "Vectors find meaning, graphs find structure" | slide--quote | — |

---

## Evidence Data

**Vendor / system facts (use in deck):**

- **Microsoft GraphRAG (2024)** — community detection + LLM summarization on a knowledge graph; improves *global* summarization QA over flat RAG.
- **Neo4j + vector indexes** — embedding stored as a node property; query: "find similar X within 2 hops" in a single traversal.
- **Weaviate hybrid search** — `alpha = 0.5` (BM25 + vector) is the recommended default for mixed corpora.
- **Vector indexes shipped 2023-2024** by Memgraph, NebulaGraph, TigerGraph — graph DBs all caught up.
- **Hybrid search defaults:** Pinecone sparse-dense, Qdrant hybrid, Elasticsearch ELSER — vector+BM25 became the new baseline, not a special mode.

**Worked examples (use as concrete anecdotes):**

- **Drug discovery** — protein-protein interaction graphs; vectors alone miss binding context.
- **Semantic doc search** — legal/medical corpora; vectors win on "passages like this."
- **Fraud ring detection** — shared device + phone + card graph; multi-hop traversal surfaces rings.
- **Duplicate question detection** — Stack Overflow / support tickets; vector cosine finds near-duplicates that exact match misses.
- **Recommendation** — Amazon / Spotify hybrid: vector recall + graph constraints (already purchased, in stock, in genre).

**Latency / scale (cite in hybrid slide):**

- Vector ANN: ~10 ms p50 at million-scale with HNSW.
- Graph traversal: ms (1-2 hops, indexed) to seconds (3+ hops, deep).
- Hybrid often bounded by the slower of the two — budget the traversal.

**Latency comparison (for decision matrix):**

| Operation | Typical latency | Index needed |
|---|---|---|
| Vector ANN top-k (HNSW) | ~10 ms | HNSW/IVF |
| Graph 1-2 hop | < 50 ms | adjacency |
| Graph 3+ hop | 100 ms – seconds | often none |
| Hybrid (vector + 2-hop filter) | ~30-80 ms | both |

---

## Design Directives

### Palette

Default `warm` (Alegreya + Alegreya Sans) theme for editorial readability. Vector = blue (`--blue`), Graph = violet (`--violet`), Hybrid = gold + accent. The `compare-panel--vector` / `compare-panel--graph` modifiers already encode this.

### Signature visual (HERO slide)

`journey-path` SVG on slide 3 (mental model) — two parallel tracks merging into a hybrid node. Mirrors the lesson arc.

### Tone

Comparative, decisive. Avoid hedging. Each content slide ends with a one-line imperative ("Pick X when Y") — the matrix is the synthesis.

### Vocabulary

Use **primitive**, not **database** when speaking conceptually. Use **vector DB / graph DB** for system choices. Use **hybrid** for the composed pattern.

---

## Quality Gates (auto-checks)

- 14 slides total (1 title + 1 hook + 1 mental model + 3 dividers + 7 content + 1 closing).
- Slide 13 is a `<table class="data-table">` inside `<div class="table-scroll">`.
- Slide 12 uses `setup-flow` or `compare-split` (not raw cards).
- Slide 11 must reference Neo4j / Memgraph / vector-as-property pattern.

---

*Spec format: premium-presentations compatible*
