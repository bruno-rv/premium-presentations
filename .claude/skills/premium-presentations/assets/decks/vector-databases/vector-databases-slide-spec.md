# VECTOR DATABASES — Slide Generation Spec

> Read BEFORE generating `vector-databases-slides.html`.

---

## Lesson Metadata

| Field | Value |
|-------|-------|
| **Code** | VECTOR DATABASES |
| **Title** | Vector Databases |
| **Title (Split)** | Line 1: "Vector" / Line 2: "Databases" (shimmer-gold) |
| **Subtitle** | Foundations — Data Infrastructure |
| **Module** | 01 — Vector Databases |
| **Duration** | ~15 min |
| **Layer** | 1 — Foundations |
| **Mode** | Self-Paced |
| **Hook** | "A vector database doesn't store data. It stores meaning — and the geometry between them." |
| **Closing** | "The best retrieval is the one that makes the model forget it ever needed to look." |

---

## Teaching Objective

Learner walks away with a working mental model: embeddings → vector spaces → similarity metrics → ANN indexes (HNSW, IVF, PQ) → production CRUD/metadata → landscape. Trailer-grade, 15 minutes, 14 slides, ~60s per slide.

---

## Overlap Avoidance

| Already covered | Where | This lesson differs |
|-----------------|-------|---------------------|
| RAG end-to-end | rag-vector-graph | This lesson zooms into the vector DB primitive; RAG is one application |
| Embeddings deep-dive | embeddings-foundation | This lesson treats embeddings as input, not the topic |

**Key rule:** Trailer for the vector DB stack. No deep code, no benchmarks — those come in the index-tuning lesson.

---

## Slide Map

| # | Type | Title | Key Content | Visual Pattern | Why Panel |
|---|------|-------|-------------|----------------|----------|
| 1 | Title | Vector Databases | Subtitle + one-line deck promise | slide--title + shimmer-gold | N/A |
| 2 | Hook Quote | Geometry beats grep | Opening quote on meaning | slide--quote | N/A |
| 3 | Content | Why a new kind of DB? | Semantic search motivation + 3 KPIs (cosine sim scores, scale) | kpi-row | "Without vector search, every AI feature degrades to keyword matching" |
| 4 | Divider | Act 1 — Foundations | Numbered act break | slide--divider (01) | N/A |
| 5 | Content | From text to a point in space | Embeddings explanation + real example aside | content-grid + aside-card | "Not the document — just the vector + pointer" |
| 6 | Content | Three ways to measure closeness | Cosine / L2 / Dot Product bar chart | bar-chart | "Pick the right metric — wrong choice = garbage NN" |
| 7 | Divider | Act 2 — Search | Brute force vs approximate | slide--divider (02) | N/A |
| 8 | Content | Multi-layer graph of meaning | HNSW visualization with flowing path | journey-stage (9s) | "Logarithmic complexity: O(log N) hops" |
| 9 | Content | IVF and PQ | Compare split with callouts | compare-split | "IVF narrows, PQ compresses" |
| 10 | Divider | Act 3 — Production | CRUD + metadata + landscape | slide--divider (03) | N/A |
| 11 | Content | More than vectors | CRUD checklist + pre/post filter aside | checklist-grid + aside-card | "Metadata filtering shrinks the candidate set" |
| 12 | Content | Choosing a vector database | Self-hosted / Managed / Embedded stats row | stats-row | "Decision rules" |
| 13 | Content | The canonical pattern | RAG setup flow 4 steps + beyond-RAG | setup-flow | "Same primitive powers search, recs, dedup, memory" |
| 14 | Closing Quote | Forget it needed to look | Closing quote + next-lesson tag | slide--quote | N/A |

---

## Evidence Data

- Cosine similarity: "happy" ↔ "joyful" ≈ 0.97, "happy" ↔ "table" ≈ 0.31
- ANN scale: 10⁹ vectors queried in < 50 ms
- Common embedding dimensions: 384 / 768 / 1024 / 3072
- Models: OpenAI text-embedding-3, Cohere embed-v3, Sentence-Transformers/all-MiniLM
- HNSW complexity: O(log N) hops
- IVF trade-off knob: nprobe (1 = fast/blind, 64 ≈ exact)
- PQ typical compression: 32× (lossy)
- Hybrid indexes: HNSW coarse + IVF-PQ fine (FAISS, ScaNN)
- Pre/post/hybrid filtering: Qdrant, Weaviate, Milvus 2.4+
- Landscape: Qdrant · Milvus · Weaviate · pgvector · Pinecone · Vertex AI · Turbopuffer · Chroma · LanceDB · DuckDB VSS

---

## Design Directives

### Palette

Default Warm Signal theme. No overrides.

### Signature visual (HERO slide)

- **Slide 8** — HNSW journey-stage with 5 nodes (Query → Top layer → Mid layer → Greedy walk → k-NN), gradient stroke, 9s flow, traveling dot.

### Tone

Trailer-grade. Confident, fast-paced. Each slide makes one point and gets out.

---

*Spec format: premium-presentations compatible*
