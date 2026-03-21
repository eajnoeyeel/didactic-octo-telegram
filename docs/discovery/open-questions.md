# Open Questions & TODOs
> 설계/구현 단계에서 해결해야 할 미결 사항들
> 최종 업데이트: 2026-03-20

---

## OQ-1. SEO 점수 산정 방식 — 논문 리서치 필요

**현재 상태**: `seo_score.py` (구현 예정, `src/analytics/seo_score.py`) 설계 방향이 정규식 휴리스틱 기반
- 특정 단어(`e.g.`, `NOT`, `parameter`)가 있으면 점수 가산
- description 길이가 길면 specificity 점수 가산
- **설계 리스크**: 이 점수가 실제 선택률과 상관관계가 낮으면 Evidence Triangulation (8b Spearman, 8c Regression R²) 자체가 무의미해짐

**리서치 방향**:
- [ ] API/Tool description 품질 평가 관련 논문 탐색
  - 후보 키워드: "API documentation quality", "tool description quality", "function description clarity"
  - 연관 분야: code search, API recommendation, documentation generation
- [ ] LLM-based scoring 대안 검토
  - 예: GPT-4o-mini에게 1-5점 척도로 점수 매기게 하기
  - 장점: 문맥 이해, 유연함 / 단점: 비용, evaluator bias, 재현성 낮음
- [ ] 두 방식(정규식 vs LLM-based) 비교 실험 설계
  - 동일한 description set에 두 방식 적용 → 사람이 직접 레이블링한 품질 점수와 비교
  - 어떤 방식이 실제 사람의 품질 판단과 더 상관관계가 높은지 측정

**결정 전 필요한 것**: 논문 리서치 + 소규모 파일럿 실험 (20~30개 description 수동 레이블링 후 두 방식 비교)

**CTO 멘토링 연계**: 3/25 세션에서 방향 확인 가능

---

## OQ-2. Smithery 크롤링 계획 + Tool Pool 구성

**현재 상태**: "Smithery 크롤링 + 직접 연결 하이브리드"로만 정해져 있음. 구체성 없음.

### 2-1. Smithery 크롤링 계획

- [ ] Smithery API rate limit 확인 (공식 문서 또는 실험적으로 측정)
- [ ] 크롤링 범위 결정: 카테고리별 균형 있게 수집할지, 인기순으로 수집할지
  - 카테고리 예: Search, Code, Database, Communication, Productivity, Science, Finance
  - 인기순이면 bias 발생 (유명 서버만 → 실험 다양성 낮음)
  - **권장**: 카테고리별 최소 5~10개씩 균형 수집
- [ ] `tools/list` 직접 연결 가능한 서버 vs 크롤링만 가능한 서버 분류
  - Smithery에 올라온 서버가 모두 실제로 접근 가능한 건 아님
  - 접근 가능한 서버 목록을 직접 확인해야 함

### 2-2. Tool Pool 구성 전략

실험의 통제 변인(변인 1)에 맞게 Pool을 **의도적으로 설계**해야 함.

| Pool 유형 | 목적 | 구성 방법 |
|-----------|------|-----------|
| **기본 Pool** (50개 서버, ~200 Tool) | 전체 파이프라인 검증 | 카테고리 균형 + Similarity Density 중간 |
| **High Similarity Pool** | Confusion Rate 측정 | 유사한 Tool 많이 포함 (search 계열 여러 개) |
| **Low Similarity Pool** | 베이스라인 측정 | 도메인 전혀 다른 서버들 |
| **Description Quality 실험용 Pool** | 핵심 테제 검증 | 동일 기능 Tool의 description 품질 고의로 다르게 설정 |

- [ ] 각 Pool 유형에 어떤 MCP 서버를 넣을지 목록 작성 (수동)
- [ ] 직접 만드는 MCP 서버 (OQ-3 참고)를 Description Quality 실험용 Pool에 포함
- [ ] Pool 크기별 실험 (5 / 20 / 50 / 100) — `build_index.py` 실행 시 `--pool-size` 파라미터로 조절
- [ ] Pool 정의 파일 위치: `data/tool_pools/`

### 2-3. Ground Truth Generation 계획

- [ ] **수동 seed set 80개 작성** (상세: `docs/evaluation/ground-truth-design.md`)
  - 형식: `GroundTruthEntry` Pydantic 모델 (query_id, query, correct_server_id, correct_tool_id, difficulty, category, ambiguity, ...)
  - 난이도 기준: Easy(명시적 키워드 매칭), Medium(의미적 유사), Hard(모호/다의적)
  - 8개 카테고리 × 10개 = 80개
- [ ] LLM synthetic 생성 품질 기준점 확립
  - seed set 80개 중 20개를 LLM에게도 생성시켜 비교
  - 겹치는 비율, 품질 차이 수동 평가
- [ ] 자동 생성된 쿼리 검증 기준 정의 (예: "너무 obvious한 쿼리"란 정확히 무엇인가)
- [ ] 파일 위치: `data/ground_truth/seed_set.jsonl`, `data/ground_truth/synthetic.jsonl`

---

## OQ-3. Provider 실증을 위한 자체 MCP 서버 구축

**배경**: Provider Analytics의 피드백 루프(description 수정 → 선택률 변화)를 실제로 보여주려면 실제 Provider가 있어야 함. 직접 MCP 서버 몇 개를 만들어 등록하고, description을 고의로 잘 쓴 버전 / 못 쓴 버전으로 A/B 테스트.

**왜 필요한가**:
- Smithery 크롤링 데이터는 description을 수정할 수 없음 (우리가 Provider가 아니므로)
- A/B 테스트, 피드백 루프, Analytics 대시보드 검증은 모두 우리가 통제 가능한 서버 필요
- CTO 평가 시 "실제 로그 기반 성능 측정" 데모 가능

**구축 후보 MCP 서버 (아이디어)**:

| 서버 이름 | 기능 | 선택 이유 |
|-----------|------|-----------|
| `mcp-arxiv` | arXiv 논문 검색 | Search 카테고리, Semantic Scholar과 혼동 실험 가능 |
| `mcp-calculator` | 수식 계산, 단위 변환 | 완전히 다른 도메인 → distractor로도 활용 |
| `mcp-korean-news` | 한국 뉴스 검색 | 언어/도메인 특수성 실험 |

- [ ] 각 서버를 **description 품질이 다른 버전으로 2개씩** 등록
  - Version A: 모호한 description ("A search tool")
  - Version B: 구체적 + disambiguation + negative instruction 포함
- [ ] 실제 `tools/list` 연결 가능하도록 MCP 서버 실제 구동
- [ ] 이 서버들로 생성된 쿼리 로그를 Provider Analytics 대시보드로 확인
- [ ] 서버 메타데이터 위치: `data/server_metadata/self_built/`

**규모**: 최소 3개 서버 × 2~3 Tool = 6~9개 Tool. description 품질 실험에 충분.

---

## OQ-4. 구현 전략 — 모든 선택지를 직접 정량 비교

**원칙**: 어떤 방법이 더 낫다고 가정하지 말고, 같은 조건에서 직접 실험해서 수치로 확인.

**비교해야 할 선택지들**:

| 결정 | 옵션 A | 옵션 B | 옵션 C | 측정 지표 |
|------|--------|--------|--------|-----------|
| 검색 전략 | Sequential 2-Layer | Parallel (RRF) | Taxonomy-gated | Precision@1, Recall@10, Latency |
| 임베딩 모델 | BGE-M3 | OpenAI text-embedding-3-small | Voyage voyage-3 | Recall@10, 비용, cold start |
| Reranker | Cohere Rerank 3 단독 | Cohere + LLM fallback | LLM-as-Judge 단독 | Precision@1 향상폭, 비용 |
| SEO 점수 방식 | 정규식 휴리스틱 | LLM-based | (논문에서 나오면 추가) | Spearman(score, selection_rate) |

**Sequential 2-Layer 설계 주의점** (논의 2026-03-19):
- `sequential.py` (구현 예정, `src/pipeline/sequential.py`) 구현 시 반드시 서버 인덱스를 먼저 거쳐야 함
- 올바른 2-Layer: 서버 인덱스 → Top-K 서버 → 서버 필터링된 툴 검색 → 후보 합산 → Reranker
- **리스크**: 서버 분류 오류 시 정답 툴이 후보에서 완전히 빠질 수 있음
- **대안**: Parallel 전략(B)이 이 리스크 없음 — 서버/툴 동시 검색 후 RRF 합산
- **결론**: 두 방식 모두 구현해서 실험으로 비교. Sequential에서 서버 필터 오류율을 별도 측정(Server Classification Error Rate).

**실험 자동화 요건** (상세: `docs/evaluation/experiment-design.md`):
- `run_experiments.py --strategy sequential` vs `--strategy parallel` 등 CLI 파라미터
- 실험 결과는 W&B에 자동 기록 (수동 비교 불필요)
- 동일한 ground truth set, 동일한 Pool로 모든 전략 비교 (통제 변인 엄격 유지)
