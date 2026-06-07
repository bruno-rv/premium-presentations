# GRAPH DATABASES — Slide Generation Spec

> Read BEFORE generating `graph-databases-slides.html`.

---

## Lesson Metadata

| Field | Value |
|-------|-------|
| **Code** | GRAPH DATABASES |
| **Title** | Graph Databases |
| **Title (Split)** | Line 1: "Graph" / Line 2: "Databases" (shimmer-gold) |
| **Subtitle** | Foundations — Connected Data |
| **Module** | 02 — Graph Databases |
| **Duration** | ~14 min |
| **Layer** | 1 — Foundations |
| **Mode** | Self-Paced |
| **Hook** | "A relational database asks how many. A graph database asks how — and shows you the path." |
| **Closing** | "Connections are not the data. They are the question — and the answer." |

---

## Teaching Objective

Learner walks away with a working mental model: property graph (nodes + edges + properties) → Cypher/GQL (the query language) → traversal complexity (O(k) vs O(N log N) joins) → knowledge graph use cases → landscape. Trailer-grade, 14 minutes, 14 slides, ~60s per slide. Confident, fast, one point per slide.

---

## Overlap Avoidance

| Already covered | Where | This lesson differs |
|-----------------|-------|---------------------|
| Vector similarity search | vector-databases | This lesson is on relationship traversal, not nearest-neighbor geometry |
| Hybrid RAG / graph + vector | rag-vector-graph | This lesson zooms into the pure graph primitive; RAG is one downstream consumer |
| Vector vs graph trade-off | vector-vs-graph | This lesson teaches the graph model deeply; the comparison deck is a side-by-side |

**Key rule:** Trailer for the graph DB stack. No GQL deep dive, no benchmarks — those come in the traversal-patterns lesson. This is "what is a graph DB and why now."

---

## Slide Map

| # | Type | Title | Key Content | Visual Pattern | Why Panel |
|---|------|-------|-------------|----------------|----------|
| 1 | Title | Graph Databases | Subtitle + one-line deck promise | slide--title + shimmer-gold | N/A |
| 2 | Hook Quote | Connections are the question | Opening quote on relationships | slide--quote | N/A |
| 3 | Content | Why a relational database breaks | JOIN explosion, friends-of-friends + KPIs | kpi-row | "RDBMS joins get exponentially worse the moment you go 3+ hops deep" |
| 4 | Divider | Act 1 — The Model | Property graph foundation | slide--divider (01) | N/A |
| 5 | Content | Nodes, edges, properties | Property graph model + real example aside | content-grid + aside-card | "Edges are not a hack — they are first-class, typed, indexed" |
| 6 | Content | Cypher speaks in shapes | ASCII-art query pattern + comparison aside | code-window + aside-card | "Read the diagram, not the joins" |
| 7 | Divider | Act 2 — The Engine | Why traversal wins at depth | slide--divider (02) | N/A |
| 8 | Content | Index-free adjacency in action | 3-hop traversal journey-stage with flowing dot | journey-stage (9s) | "O(k) hops regardless of graph size — no JOIN, no scan" |
| 9 | Content | Knowledge graphs in the wild | 4 famous knowledge graphs in stats row | stats-row | "Knowledge graphs turn messy data into queryable structure" |
| 10 | Divider | Act 3 — Production | Use cases + landscape + the rest | slide--divider (03) | N/A |
| 11 | Content | Where graph DBs win | 5 use cases in checklist + LinkedIn/PayPal aside | checklist-grid + aside-card | "Pick the workload where relationships ARE the answer" |
| 12 | Content | The landscape | 4 flavors in stats row with decision rules | stats-row | "Same property graph, different trade-offs" |
| 13 | Content | Beyond simple CRUD | 3 things graph DBs are not — a setup-flow of misconceptions | setup-flow | "It's not NoSQL with edges — it's a first-class traversal engine" |
| 14 | Closing Quote | Connections are the question | Closing quote + next-lesson tag | slide--quote | N/A |

---

## Evidence Data

- Property graph: nodes (entities) + edges (relationships) + properties (key-value on both)
- Famous adopters: LinkedIn (1B+ member graph), PayPal (fraud rings), NASA (knowledge graphs), Google Knowledge Graph (500B+ facts)
- Query languages: Cypher (Neo4j, 2011) is de facto; ISO GQL standardized it in 2024
- Traversal complexity: O(k) hops for k-deep traversal vs O(N log N) for SQL self-joins
- Use cases: knowledge graphs, fraud detection (PayPal), social networks (LinkedIn), IT/lineage, recommendation engines
- Landscape: Neo4j (leader) · Memgraph (in-memory perf) · ArangoDB (multi-model) · TigerGraph (enterprise) · Amazon Neptune (managed) · Kùzu (embedded/research) · NebulaGraph (distributed)
- Misconception: "graph DB = NoSQL with edges" — wrong. They are first-class traversal engines with native storage and query optimization
- Performance anecdote: Neo4j 1M-node friends-of-friends query runs in milliseconds; equivalent MySQL JOIN takes minutes

---

## Design Directives

### Palette

Default Warm Signal theme. No overrides.

### Signature visual (HERO slide)

- **Slide 8** — Traversal journey-stage with 5 nodes (User → 1-hop friends → 2-hop friends → 3-hop friends → Mutual interest), gold→violet gradient, 9s flow, traveling dot animation. Index-free adjacency made visible.

### Tone

Trailer-grade. Confident, fast-paced. Each slide makes one point and gets out. Drop the misconception (graph DB ≠ NoSQL-with-edges) clearly and early.

---

*Spec format: premium-presentations compatible*
