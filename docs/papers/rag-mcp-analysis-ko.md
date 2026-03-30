# RAG-MCP 심층 분석서

> RAG 기반 MCP 검색으로 prompt bloat를 줄이고 도구 선택 정확도를 높이는 3단계 파이프라인(indexing → retrieval → focused selection)을 제안한 논문이자, 본 프로젝트의 1차 baseline 저장소 분석.

## 기본 정보

- 논문: [RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation](https://arxiv.org/abs/2505.03275)
- 저자: Tiantian Gan, Qiyao Sun 외
- 대상 저장소: `/root/rag-mcp`
- 목적: `MCP 추천 최적화` 프로젝트의 baseline 후보로서 현재 `RAG-MCP` 구현의 연구적 가치와 재사용 가능성을 평가

## 핵심 기여

- **문제 정의**: 다수 MCP를 프롬프트에 넣으면 prompt bloat, selection complexity, performance degradation 발생
- **해결 방법**: MCP discovery를 생성 밖으로 분리 — 외부 인덱스에서 관련 MCP만 먼저 검색
- **3단계 파이프라인**: indexing → retrieval(top-k 의미 검색) → focused selection/invocation
- **validation 단계**: 검색 MCP에 synthetic example 또는 sanity check 수행 후 최종 실행 후보로 활용

## 방법론 핵심

### 논문 파이프라인 vs 저장소 구현

| 논문 단계 | 저장소 구현 | 차이 |
| --- | --- | --- |
| indexing | MCP tool → Bedrock tool spec → JSONL → S3 → KB ingestion | 대응 |
| retrieval | 대화 문맥 → `BedrockKB.query(top_k=2)` | top-2를 그대로 모델에 제공 |
| focused selection | Bedrock Converse toolConfig에 선택 도구만 주입 | validation 단계 거의 없음 |
| full baseline | `queryall()` — broad semantic query(max=100) | 진짜 full prompt baseline 아님 |

- 논문은 `MCP server retrieval`을 다루지만 저장소는 `tool schema retrieval`에 가까움
- AWS Bedrock KB, S3, Bedrock Converse에 강하게 의존

## 실험 결과 (Top-3)

1. **정확도 차이**: RAG-MCP 43.13% vs baseline 13.62% — retrieval 분리가 유효
2. **토큰 절감**: 평균 prompt token 1084 vs 2133.84 — prompt bloat 완화 확인
3. **스케일 한계**: 수천 개 이상에서 retrieval precision 저하 — hierarchical/adaptive retrieval 필요

## 한계점

- **논문 재현도 낮음**: validation 단계 미구현, baseline 정의가 엄밀하지 않음 (`queryall()`은 진짜 full prompt가 아님)
- **인프라 의존성**: pluggable retriever abstraction 없이 AWS에 강하게 묶임
- **테스트 체계 부족**: offline benchmark/online feedback loop 미분리, 재현성 낮음 (하드코딩된 경로, 특정 KB ID)

## 프로젝트 적용 포인트

### 차용 가능한 요소
- retrieval을 통한 prompt 축소 아이디어 (핵심 아키텍처 패턴)
- 세션-질의-검색-도구실행 루프 구조
- token/latency/accuracy 비교 실험 harness

### 재설계 필요 사항
- **추천 대상 정의**: tool vs MCP server vs package vs version
- **평가 지표**: retrieval quality (MRR, nDCG) + execution success + UX quality
- **metadata schema**: 기능, 비용, 보안, 권한, latency, 호환성, 실패율
- **offline/online 피드백 루프**: 사용 로그 수집 → retriever/reranker 개선
- **운영 자동화**: MCP registry, 버전관리, 호환성 검증, 품질 게이트

### 최종 판단

- **권고**: `부분 차용`
- retrieval 기반 prompt 축소와 tool selection 비교 harness는 재사용 가치 있음
- retriever abstraction, metadata model, ranking/validation, logging/ops는 새로 설계 필요

## 관련 research 문서

- [Tool Selection & Retrieval 조사](../research/tool-selection-retrieval.md)
