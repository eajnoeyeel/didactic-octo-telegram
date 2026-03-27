# Architecture — Mermaid Diagrams

> 최종 업데이트: 2026-03-22
> 결정 사항/기술 스택: `./architecture.md`

---

## 1. 양면 플랫폼 구조

```mermaid
graph LR
    subgraph LLM["LLM/Agent 고객 경로 (Bridge)"]
        Q[Query] --> FBT["find_best_tool()<br/>(MCP Tool / REST)"]
        FBT --> RES[Best Tool + Schema 반환]
        RES --> ET["execute_tool(tool_id, params)<br/>(프록시 실행)"]
        ET --> PROV_MCP["Provider MCP A/B/C..."]
        PROV_MCP --> RESULT[실행 결과 반환]
    end

    subgraph Provider["Provider 고객 경로"]
        P[Provider] --> DASH[Analytics Dashboard<br/>REST API]
        LOG[로그 집계 + GEO Score<br/>Confusion Matrix<br/>A/B Test 결과] --> DASH
    end

    subgraph Core["Core Pipeline (공유)"]
        PIPE[Embedding → Search → Rerank → Score]
    end

    FBT --> PIPE
    PIPE --> RES
    ET --> LOG
    PIPE --> LOG
```

---

## 2. Core Pipeline — 2-Stage Retrieval

```mermaid
flowchart TD
    Q["find_best_tool(query)"] --> EMB["Embedding<br/>(BGE-M3 or OpenAI)"]
    EMB --> SI["Layer 1<br/>Server Index<br/>(Qdrant)"]
    EMB --> TI["Layer 1<br/>Tool Index<br/>(Qdrant)"]

    SI -->|Top-K servers| L2["Layer 2<br/>Tool Search<br/>(filtered)"]
    TI -->|Top-N tools| RRF["RRF<br/>Score Fusion"]

    L2 --> MERGE((병합))
    RRF --> MERGE

    MERGE --> RR["Reranker<br/>Cohere Rerank 3<br/>(or LLM fallback)"]
    RR --> CB{"Confidence<br/>Branching<br/>gap > 0.15?"}

    CB -->|Yes| TOP1["Top-1 반환"]
    CB -->|No| TOP3["Top-3 + Hint 반환"]
```

---

## 3. Strategy Pattern — 3가지 검색 전략

```mermaid
classDiagram
    class PipelineStrategy {
        <<ABC>>
        +search(query) List~SearchResult~
        +name str
    }
    class Sequential {
        Server Index → filter → Tool Search
        장점: 직관적, 서버 분석 가능
        단점: Layer 1 누락 시 복구 불가
    }
    class Parallel {
        Server + Tool 병렬 → RRF Fusion
        장점: Layer 1 실패에 강건
        단점: 검색 범위 넓음, Latency↑
    }
    class TaxonomyGated {
        Intent Classifier → Category Sub-Index
        장점: 검색 범위 축소, 정밀도↑
        단점: 분류 오류 시 전체 실패
    }

    PipelineStrategy <|-- Sequential : Strategy A
    PipelineStrategy <|-- Parallel : Strategy B
    PipelineStrategy <|-- TaxonomyGated : Strategy C
```

---

## 4. 데이터 흐름

```mermaid
flowchart TD
    SM["Smithery Registry<br/>(crawl)"] --> RAW["data/raw/servers.jsonl<br/>원본 MCP 서버/Tool 메타데이터"]
    MCP["Direct MCP<br/>tools/list<br/>(connect)"] --> RAW

    RAW -->|"indexer.py<br/>(batch embed + upsert)"| QD["Qdrant Cloud"]

    subgraph QD["Qdrant Cloud"]
        SIdx["Server Index<br/>(server_id, description, vector)"]
        TIdx["Tool Index<br/>(tool_id, description, vector, server_id)"]
    end

    subgraph GT["Ground Truth"]
        SEED["seed_set.jsonl<br/>(80 수동)"]
        SYN["synthetic.jsonl<br/>(LLM 생성)"]
    end

    QD --> HARNESS["Evaluation Harness<br/>evaluate(strategy, queries, gt)"]
    GT --> HARNESS

    HARNESS --> METRICS["Metrics<br/>Precision@1, Recall@K,<br/>Confusion Rate, ECE,<br/>Latency p50/95/99, Spearman r"]

    METRICS --> TRACK["Experiment Tracking"]
    subgraph TRACK
        WB["W&B (runs)"]
        CSV["data/experiments/<br/>(CSV/JSON)"]
    end
```

---

## 5. Provider Analytics 파이프라인

```mermaid
flowchart TD
    FBT["find_best_tool() 호출"] --> RET["결과 반환<br/>(LLM 고객)"]
    FBT --> LOG["Query Log<br/>(JSONL)"]

    LOG --> AGG["Aggregator<br/>per-tool 집계"]

    AGG --> SF["Selection<br/>Frequency"]
    AGG --> GEO["GEO<br/>Score"]
    AGG --> CM["Confusion<br/>Matrix"]
    AGG --> SH["Similarity<br/>Heatmap"]

    SF --> API["Provider Analytics API<br/>(REST endpoints)"]
    GEO --> API
    CM --> API
    SH --> API
```

---

## 6. 모듈 의존관계

```mermaid
graph LR
    CONFIG["config.py"] -.-> ALL((all))
    MODELS["models.py"] -.-> ALL
    subgraph pipeline
        STRAT["strategy.py"] --> SEQ["sequential.py"] & PAR["parallel.py"] & TAX["taxonomy_gated.py"]
        CONF["confidence.py"] --> SEQ & PAR & TAX
    end
    subgraph embedding
        EBASE["base.py"] --> BGE["bge_m3.py"] & OAI["openai_embedder.py"]
    end
    subgraph retrieval
        QDRANT["qdrant_store.py"]
        HYBRID["hybrid.py"] --> PAR
    end
    subgraph reranking
        RBASE["base.py"] --> COHERE["cohere_reranker.py"] & LLM["llm_fallback.py"]
    end
    subgraph evaluation
        HARNESS["harness.py"] --> EVAL["evaluator.py"] --> METR["metrics/*"]
        HARNESS --> STRAT
        EXP["experiment.py"] --> HARNESS
    end
    subgraph analytics
        AGGR["aggregator.py"] --> LOGGER["logger.py"]
        ABTEST["ab_test.py"] --> HARNESS & AGGR
        CMTX["confusion_matrix.py"] --> AGGR
    end
    subgraph api
        MAIN["main.py"] --> ROUTES["routes/*"]
        RSEARCH["routes/search.py"] --> STRAT & LOGGER
        RPROV["routes/provider.py"] --> AGGR & CMTX
    end
    QDRANT --> SEQ & PAR
    QDRANT -.-> IDX["data/indexer.py"]
```

---

## 7. Evidence Triangulation (핵심 테제 검증)

- **테제**: "Description 품질이 높을수록 Tool 선택률이 높아진다"

```mermaid
flowchart LR
    E8a["8a. A/B Lift > 30%<br/>McNemar p < 0.05"] --> JUDGE{"2/3 이상 통과?"}
    E8b["8b. Spearman r > 0.6<br/>p < 0.05"] --> JUDGE
    E8c["8c. OLS R² > 0.4<br/>요소별 기여도 분해"] --> JUDGE
    JUDGE -->|Yes| SUPPORT["테제 지지"]
    JUDGE -->|No| REJECT["테제 기각/재설계"]
```
