# TREC-8 Question Answering Track (Voorhees, 1999)

> 출처: TREC-8, Voorhees (1999)
> 한 줄 요약: 질의응답(QA) 시스템 평가를 위한 MRR(Mean Reciprocal Rank) 지표의 원류가 된 정보 검색 평가 트랙.

---

## 해결하려는 문제

대규모 문서 컬렉션에서 자연어 질문에 대한 정확한 답변을 찾는 QA(Question Answering) 시스템의 성능을 어떻게 체계적으로 평가할 것인가. 특히 시스템이 반환한 답변의 "순위"를 반영하는 평가 지표가 필요했다.

## 핵심 아이디어

- TREC(Text REtrieval Conference)의 QA Track에서 정답이 결과 목록의 몇 번째에 위치하는지를 반영하는 **MRR(Mean Reciprocal Rank)** 지표를 정립한다.
- MRR = (1/|Q|) x sum(1/rank_i): 각 쿼리에 대해 첫 번째 정답의 순위 역수를 평균
- 단순히 "정답이 있느냐 없느냐"(Recall)를 넘어 "정답이 얼마나 앞에 있느냐"를 반영

## 방법론

- TREC-8 QA Track에서 다수의 QA 시스템이 제출한 결과를 대상으로 MRR을 산출
- 정답 위치가 상위일수록 높은 점수를 부여하는 순위 기반 평가 체계 구축
- 이후 정보 검색(IR) 분야 전반의 표준 평가 지표로 자리잡음

## 주요 결과

- MRR이 QA 시스템 평가의 사실상 표준 지표로 정착
- ToolBench, API-Bank 등 이후 모든 tool retrieval 논문이 MRR 또는 NDCG를 보고 지표로 사용
- Recall이 "있냐 없냐"만 보는 반면, MRR은 "얼마나 앞에 있느냐"를 반영하여 사용자 경험과 더 밀접

## 장점

- 직관적이고 계산이 간단한 순위 기반 지표
- 정보 검색, QA, 도구 추천 등 다양한 도메인에 범용 적용 가능
- 25년 이상 사용되어 온 검증된 지표

## 한계

- 첫 번째 정답 위치만 반영하므로, 여러 정답이 있는 경우 나머지 정답의 순위를 무시
- NDCG와 달리 부분적 관련도(graded relevance)를 반영하지 못함

## 프로젝트 시사점

MCP Discovery Platform의 Layer 1 서버 추천 품질을 평가하는 MRR (Metric #11)의 직접적인 원류이다. Recall@K가 "정답 서버가 Top-K에 있는가"를 측정한다면, MRR은 "정답 서버가 몇 번째인가"를 측정하여 Sequential 전략에서 상위 서버부터 Tool 검색하는 구조의 실제 성능을 더 정확히 반영한다.

evaluation-metrics.md에서 "Voorhees (TREC-8 QA Track, 1999)"를 MRR의 논문 근거로 직접 인용하고 있으며, metrics-rubric.md에서 MRR >= 0.80 목표를 설정하고 있다.

## 적용 포인트

- **MRR (Metric #11)**: Layer 1 서버 추천에서 정답 서버의 순위 품질 측정. 목표 >= 0.80
- **Server Recall@K와의 보완**: Recall@K(있냐 없냐) + MRR(얼마나 앞에 있냐)을 함께 보고하여 Layer 1 성능을 다각도로 평가
- **Strategy 비교**: Sequential(A) vs Parallel(B) 전략 비교 시 MRR 차이가 핵심 판단 기준
- **Dashboard**: MRR 전략별 Bar chart로 시각화

## 관련 research 문서

- [evaluation-metrics.md](../research/evaluation-metrics.md) — MRR 정의 및 Voorhees 인용
