# Quality Matters: Risks of Synthetic Ground Truth Quality

> 출처: arxiv:2409.16341
> 한 줄 요약: LLM으로 생성한 synthetic ground truth 데이터의 품질 리스크를 분석하고, 합성 데이터에만 의존할 경우 평가 결과가 왜곡될 수 있음을 경고하는 연구.

---

## 해결하려는 문제

LLM을 사용하여 평가용 ground truth 데이터를 합성(synthetic)으로 생성하는 방식이 점점 보편화되고 있지만, 이렇게 만들어진 데이터의 품질이 실제 평가에 어떤 리스크를 초래하는지에 대한 체계적 분석이 부족하다. 특히 합성 데이터의 편향(bias), 노이즈(noise), 분포 왜곡(distribution shift)이 벤치마크 결과를 오도할 수 있는 문제를 다룬다.

## 핵심 아이디어

- Synthetic ground truth는 생성 모델의 편향을 반영하므로, 이를 평가 기준으로 사용하면 순환 논리(circular reasoning)에 빠질 위험이 있다. (이 개념이 논문에서 명시적으로 "circular reasoning"이라는 용어로 다뤄지는지는 본문 확인 필요 — abstract에서는 직접 확인되지 않음)
- 합성 데이터의 품질을 인간 평가(human annotation)와 비교하여 그 한계를 정량적으로 측정한다.
- 합성 데이터 사용 시 필요한 품질 보증(quality assurance) 프로세스를 제안한다.

## 방법론

상세 분석 추가 예정

## 주요 결과

상세 분석 추가 예정

## 장점

- Synthetic ground truth의 리스크를 체계적으로 경고한 시의적절한 연구
- 실무적으로 합성 데이터를 사용할 때의 가이드라인 제공

## 한계

상세 분석 추가 예정

## 프로젝트 시사점

MCP Discovery Platform의 Ground Truth 생성 전략에 직접적인 영향을 미친다. 우리 시스템은 Ground Truth를 두 가지 소스로 구축한다:

1. **seed_set.jsonl** — 80개 수동 레이블 (인간 검증)
2. **synthetic.jsonl** — LLM 생성 (합성)

Quality Matters 논문은 synthetic.jsonl의 품질 리스크를 경고하며, 다음 원칙을 적용해야 함을 시사한다:
- 합성 데이터에만 의존하지 않고 반드시 수동 seed set과 병행 사용
- 합성 데이터의 분포가 수동 데이터와 일관되는지 검증
- Ground Truth 레이블에 `manually_verified` 필드를 두어 seed set과 합성 데이터를 구분

architecture.md에서 이 논문을 "GT 생성 주의점"으로 직접 인용하고 있다.

## 적용 포인트

- **Ground Truth 설계**: seed set(수동) + synthetic(합성) 하이브리드 전략에서 합성 데이터의 품질 검증 프로세스 설계
- **`manually_verified` 필드**: metrics-rubric.md의 Ground Truth 레이블 필드에 seed set 구분 용도로 포함
- **실험 결과 해석**: synthetic 데이터 기반 실험 결과를 seed set 기반 결과와 비교하여 편향 검출
- **합성 데이터 생성 파이프라인**: LLM 생성 쿼리의 품질 필터링 기준 수립

## 관련 research 문서

- [evaluation-metrics.md](../research/evaluation-metrics.md) — Ground Truth 구조 요구사항
