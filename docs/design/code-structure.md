# 코드 구조 (계획)

> 상세: `docs/superpowers/plans/2026-03-18-mcp-discovery-platform.md`

```
mcp-discovery/
├── src/
│   ├── models.py              # MCPServerSummary, MCPTool, MCPServer, SearchResult, FindBestToolRequest/Response, GroundTruthEntry
│   ├── config.py              # pydantic-settings, 환경변수 기반
│   ├── pipeline/
│   │   ├── strategy.py        # PipelineStrategy ABC + StrategyRegistry
│   │   ├── sequential.py      # Strategy A: 서버 인덱스 → 서버 내 Tool 검색 → Reranker
│   │   ├── parallel.py        # Strategy B: 서버/Tool 병렬 검색 → RRF 합산 → Reranker
│   │   ├── taxonomy_gated.py  # Strategy C: 인텐트 분류 → 카테고리 내 검색 (CTO 확인 후)
│   │   └── confidence.py      # Gap-based confidence 분기 (threshold 0.15)
│   ├── embedding/
│   │   ├── base.py            # Embedder ABC
│   │   ├── bge_m3.py          # BGE-M3 (Dense + Sparse 통합)
│   │   └── openai_embedder.py # OpenAI text-embedding-3-small
│   ├── retrieval/
│   │   ├── qdrant_store.py    # Qdrant Cloud wrapper (upsert, search, delete)
│   │   └── hybrid.py          # RRF fusion (bm25_rank + dense_rank)
│   ├── reranking/
│   │   ├── base.py            # Reranker ABC
│   │   ├── cohere_reranker.py # Cohere Rerank 3
│   │   └── llm_fallback.py    # LLM reranker (low-confidence fallback)
│   ├── data/
│   │   ├── smithery_client.py # Smithery API HTTP 클라이언트 (async context manager)
│   │   ├── server_selector.py # 필터링 (deployed), 정렬 (popularity), 큐레이션
│   │   ├── crawler.py         # SmitheryCrawler 오케스트레이터 (save/load JSONL)
│   │   ├── mcp_connector.py   # Direct tools/list MCP 연결 (Phase 4+에서 활성화)
│   │   ├── ground_truth.py    # Synthetic GT 생성 + Quality Gate 검증
│   │   └── indexer.py         # Batch embed + Qdrant upsert
│   ├── evaluation/
│   │   ├── harness.py         # evaluate(strategy, queries, gt) → Metrics
│   │   ├── evaluator.py       # Evaluator ABC
│   │   ├── experiment.py      # ExperimentRunner, ExperimentConfig
│   │   └── metrics/
│   │       ├── precision.py          # Precision@1
│   │       ├── recall.py             # Recall@K (Server/Tool)
│   │       ├── latency.py            # p50/p95/p99
│   │       ├── confusion_rate.py     # Confusion Rate
│   │       ├── calibration.py        # ECE
│   │       └── description_correlation.py  # Spearman(quality ↔ selection) — 핵심 테제
│   ├── analytics/
│   │   ├── logger.py          # Query 로그 (JSONL)
│   │   ├── aggregator.py      # 로그 집계 → ToolStats
│   │   ├── geo_score.py       # Description GEO Score (6차원: Clarity, Disambiguation, Parameter Coverage, Boundary, Stats, Precision)
│   │   ├── ab_test.py         # A/B 테스트 실행기
│   │   ├── similarity_heatmap.py   # Tool 간 코사인 유사도
│   │   └── confusion_matrix.py     # Per-tool confusion matrix
│   ├── bridge/
│   │   ├── mcp_bridge.py      # Bridge MCP Server — find_best_tool + execute_tool 노출 (Week 3)
│   │   ├── proxy.py           # execute_tool → Provider MCP 프록시 (MetaMCP 기반)
│   │   └── registry.py        # Provider MCP 연결 정보 캐시 (tool_id → endpoint)
│   └── api/
│       ├── main.py            # FastAPI app
│       └── routes/
│           ├── search.py      # POST /search → find_best_tool
│           └── provider.py    # Provider analytics endpoints
├── data/
│   ├── raw/                   # Smithery 크롤링 결과 (servers.jsonl)
│   ├── ground_truth/          # seed_set.jsonl, synthetic.jsonl
│   └── experiments/           # 실험 결과 (CSV/JSON)
├── scripts/
│   ├── collect_data.py        # 크롤러 + 직접 연결 실행
│   ├── build_index.py         # 임베딩 + Qdrant upsert (--pool-size 옵션)
│   ├── generate_ground_truth.py  # GT 생성 + 검증
│   └── run_experiments.py     # 실험 실행 CLI
├── tests/
│   ├── unit/                  # 모듈별 단위 테스트
│   ├── integration/           # Qdrant + Cohere 실제 연동 (API key 없으면 skip)
│   └── evaluation/            # E2E 평가 하네스 테스트
├── pyproject.toml
├── .env.example
└── CLAUDE.md
```
