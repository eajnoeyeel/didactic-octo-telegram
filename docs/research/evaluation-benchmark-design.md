# 평가 하네스 및 벤치마크 설계 조사

> 최종 업데이트: 2026-03-22
> 조사 목적: 평가 하네스 및 벤치마크 설계 (DP9)

---

## 해결하려는 기능/문제

11개 지표 커스텀 평가 하네스 + Ground Truth 구조 설계. 핵심 질문: "2-Layer 파이프라인의 각 단계를 독립적으로 평가하면서, Provider Analytics까지 커버하는 평가 시스템을 어떻게 만드는가?"

## 검토한 논문/자료 목록

| 논문 | 파일 | 핵심 기여 |
|------|------|-----------|
| StableToolBench | [stabletoolbench-analysis-ko.md](../papers/stabletoolbench-analysis-ko.md) | Virtual API server로 벤치마크 안정성 확보. 재현 가능한 평가 환경 설계의 핵심 참고 |
| API-Bank | [api-bank-analysis-ko.md](../papers/api-bank-analysis-ko.md) | Planning / Retrieval / Calling 3축 분해 평가. Layer별 독립 평가 설계의 직접 근거 |
| τ-bench | [tau-bench-analysis-ko.md](../papers/tau-bench-analysis-ko.md) | Tool-Agent-User 상호작용 벤치마크. pass^k 메트릭으로 반복 실행 신뢰성 측정 |
| AgentBoard | [agentboard-analysis-ko.md](../papers/agentboard-analysis-ko.md) | 다단계 agent 분석. Progress rate, subgoal completion 등 과정 지표 도입 |
| MCP-Bench | [mcp-bench-analysis-ko.md](../papers/mcp-bench-analysis-ko.md) | MCP 특화 벤치마크. MCP 프로토콜 기반 Tool 선택/실행 평가 |
| Quality Matters | [quality-matters-analysis-ko.md](../papers/quality-matters-analysis-ko.md) | Synthetic Ground Truth 생성 시 리스크와 편향 분석 |

## 각 자료에서 가져온 핵심 포인트

- **StableToolBench**: 실 API 상태 변화가 벤치마크를 불안정하게 만든다는 문제를 virtual API server + caching으로 해결. "Solvable Pass Rate" 개념 도입 — API 문제로 풀 수 없는 태스크를 분모에서 제외하여 공정성 확보. 우리 프로젝트에서 MCP 서버 가용성 변동에 대비한 안정적 오프라인 평가 환경 설계의 직접 참고.
- **API-Bank**: 도구 사용 능력을 planning / retrieval / calling으로 분리 평가. 73개 API, 753개 API call 규모의 수작업 Ground Truth. 우리 프로젝트의 Layer 1(서버 검색) / Layer 2(Tool 검색) / E2E(실행 성공) 3단계 독립 평가 구조의 직접 근거.
- **τ-bench**: 단발 성공률이 아닌 pass^k 메트릭 도입 — 동일 쿼리를 k번 실행하여 일관성 측정. "최고 모델도 50% 미만 태스크 성공, 반복 일관성 낮음"이라는 결과. 우리 Confidence Branching(DP6)의 신뢰성 검증에 참고 — ECE 지표와 연결.
- **AgentBoard**: 최종 성공률 외에 progress rate, subgoal completion, trajectory quality 등 과정 지표 도입. 실패 분석 시 "어디에서 틀렸는가"를 추적하는 분석 보드 제공. 우리 per-query breakdown(난이도별, 카테고리별) 결과 구조와 Confusion Rate(혼동 실패 vs 완전 미스 분리)의 설계 참고.
- **MCP-Bench**: MCP 프로토콜에 특화된 최초의 벤치마크. Tool 선택 + 실행까지 MCP 생태계 맥락에서 평가. Recall@K를 MCP Tool 레벨에서 측정하는 방법론 직접 참고.
- **Quality Matters**: LLM으로 생성한 synthetic Ground Truth가 특정 패턴에 편향될 수 있다는 리스크 분석. 우리 프로젝트에서 seed_set(80개 수동) + synthetic(LLM 생성) 하이브리드 전략의 근거 — synthetic만으로는 편향 리스크, 수동만으로는 규모 부족.

## 후보 접근 방식 비교

| 전략 | 방법 | 장점 | 단점 | 논문 근거 |
|------|------|------|------|-----------|
| **A: RAGAS 프레임워크** | 기존 RAG 평가 프레임워크 활용 (faithfulness, relevancy 등) | 즉시 사용 가능, 커뮤니티 검증 | 2-Layer 구조 미지원, Confusion Matrix/Provider Analytics 커버 불가, 단일 레이어 RAG 전제 | RAG 평가 표준이나 Tool Selection에 부적합 |
| **B: 기존 벤치마크** | ToolBench, MCP-Bench 데이터셋 직접 활용 | 대규모 데이터, 비교 가능 | 우리 Pool 구성과 불일치, 2-Layer 독립 평가 불가, Provider Analytics 지표 없음 | StableToolBench, MCP-Bench 참고하되 직접 적용은 부적합 |
| **C: 커스텀 하네스** | Evaluator ABC 플러그인 방식, 11개 지표 모듈화 | 2-Layer 독립 평가, Confusion Matrix, Provider Analytics 완전 커버 | 구축 비용, 외부 비교 어려움 | API-Bank의 3축 분해 + StableToolBench의 안정성 + τ-bench의 pass^k 종합 |

## 채택안 / 제외안

**채택**: Strategy C — 커스텀 하네스 + 11개 지표 (ABC plugin 방식)

기존 프레임워크(RAGAS, ToolBench)는 다음을 커버하지 못한다:
1. **2-Layer 독립 평가**: Layer 1(서버 Recall@K, MRR, Server Error Rate)과 Layer 2(Precision@1, Tool Recall@10, NDCG@5, Confusion Rate)를 분리 측정
2. **Confusion Matrix**: 오답을 "혼동 실패"와 "완전 미스"로 분류하는 ToolScan 기반 분석
3. **Provider Analytics 지표**: Spearman(quality, selection), ECE, Description Quality Score 연동
4. **실험 자동화**: Strategy Pattern과 직접 연동하여 E0-E7 실험 매트릭스 자동 실행

**제외**:
- RAGAS: 단일 레이어 RAG 평가 전제. retrieval + generation 축이 우리 2-Layer + Reranker + Confidence Branching 구조와 불일치
- ToolBench/MCP-Bench 직접 활용: 벤치마크 데이터셋은 참고하되, 우리 Pool(50-100 큐레이션 서버)과 평가 요구사항이 다름

## 판단 근거

1. **API-Bank의 3축 분해**: planning / retrieval / calling 독립 평가가 우리 Layer 1 / Layer 2 / E2E 독립 평가 구조의 직접 근거. 단일 accuracy로 묶으면 "어디서 실패했는가" 진단 불가.
2. **StableToolBench의 virtual API server**: MCP 서버 가용성 변동에 대비하여, Ground Truth 기반 오프라인 평가를 primary로, 실제 MCP 실행 평가를 secondary로 분리. 자체 MCP 서버(mcp-arxiv 등)에 대해서만 Pass Rate 측정.
3. **τ-bench의 pass^k**: 단발 Precision@1만으로는 시스템 신뢰성 판단 불가. 동일 쿼리 반복 실행 시 일관성(ECE 지표)이 실 운영 품질의 핵심. Confidence Branching(DP6)의 gap threshold 0.15가 실제 정확도와 정렬되는지 ECE로 검증.
4. **Quality Matters의 synthetic GT 리스크**: LLM 생성 쿼리만으로 Ground Truth를 구성하면, LLM이 잘 처리하는 패턴으로 편향 → 실제 사용자 쿼리와 괴리. seed_set(80개 수동) + synthetic 하이브리드가 필수.
5. **AgentBoard의 과정 분석**: per-query breakdown(난이도별, 카테고리별)과 Confusion Rate의 혼동/미스 분리가 실패 원인 진단에 필수. 최종 성공률만으로는 개선 방향을 알 수 없다.

## 프로젝트 반영 방식

- `src/evaluation/harness.py`: 평가 하네스 — `evaluate(strategy, queries, gt)` 진입점. 실험 설정(ExperimentConfig)을 받아 전체 파이프라인 실행 + 지표 수집
- `src/evaluation/evaluator.py`: Evaluator ABC — 모든 지표 평가자의 공통 인터페이스. 플러그인 방식으로 지표 추가 가능
- `src/evaluation/metrics/`: 6개 모듈
  - `retrieval.py`: Recall@K (서버/Tool), MRR, NDCG@K, Server Error Rate
  - `precision.py`: Precision@1, Confusion Rate (혼동 vs 미스 분류)
  - `calibration.py`: ECE (Expected Calibration Error)
  - `latency.py`: Latency p50/p95/p99 (Layer별 + 전체)
  - `correlation.py`: Spearman(quality, selection), Regression R²
  - `pass_rate.py`: Pass Rate (자체 MCP 서버 한정, StableToolBench의 Solvable Pass Rate 개념 적용)
- `data/ground-truth/`: Pydantic schema 기반 Ground Truth
  - `seed_set.jsonl`: 80개 수동 작성 (Quality Matters 리스크 대응)
  - `synthetic.jsonl`: LLM 생성 (seed_set 패턴 편향 보완)
  - `schema.py`: GroundTruthEntry Pydantic 모델 — query, expected_server, expected_tool, alternative_tools, difficulty, category, domain

## 관련 papers

- [StableToolBench](../papers/stabletoolbench-analysis-ko.md)
- [API-Bank](../papers/api-bank-analysis-ko.md)
- [τ-bench](../papers/tau-bench-analysis-ko.md)
- [AgentBoard](../papers/agentboard-analysis-ko.md)
- [MCP-Bench](../papers/mcp-bench-analysis-ko.md)
- [Quality Matters](../papers/quality-matters-analysis-ko.md)
