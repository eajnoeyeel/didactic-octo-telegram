---
name: python-performance-optimization
description: Profile and optimize slow crawling, embedding, indexing, retrieval, or proxy round-trips in this repository. Use for latency, throughput, or memory issues. Do not use for first-pass feature implementation or correctness-only debugging.
---

# Python Performance Optimization

1. Measure before changing code. Start with the smallest reproducer that exposes the slowdown.
2. Focus on current hotspots, not planned architecture:
   - Smithery detail fetch loops
   - OpenAI embedding batch size and repeated calls
   - Qdrant upsert/search throughput
   - result merging in `SequentialStrategy`
   - connect-per-call startup cost in `proxy_verification/`
3. Prefer simple wins first: batch sizing, client reuse, avoiding repeated serialization, and reducing unnecessary subprocess startups.
4. Do not optimize imagined FastAPI, reranker, or experiment code paths unless they actually exist in the repo or the user asked you to add them.
5. Keep correctness checks alongside performance changes.
