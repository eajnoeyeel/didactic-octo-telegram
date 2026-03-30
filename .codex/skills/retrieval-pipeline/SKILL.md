---
name: retrieval-pipeline
description: Work on the main retrieval pipeline, embeddings, and Qdrant integration. Use when editing `src/pipeline/`, `src/embedding/`, `src/retrieval/`, `src/data/indexer.py`, or related indexing/search scripts. Do not use for `proxy_verification/` work or docs-only tasks.
---

# Retrieval Pipeline

1. Inspect the current implementation first. Today the real pipeline surface is `flat`, `sequential`, `confidence`, `QdrantStore`, and the OpenAI embedder.
2. Treat docs about rerankers, FastAPI routes, `parallel`, `taxonomy_gated`, or experiment runners as planned work unless you are explicitly implementing them.
3. Preserve these main-project invariants:
   - tool IDs use `::`
   - config comes from `Settings`
   - I/O stays async
   - `QdrantStore` owns payload/text conversion rules
4. When changing search or indexing logic, check nearby unit tests and add focused cases for score ordering, filtering, payload reconstruction, or validator behavior.
5. Verify with the smallest relevant pipeline test slice before broadening.
