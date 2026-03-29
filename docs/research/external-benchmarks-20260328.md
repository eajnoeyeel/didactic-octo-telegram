# 외부 벤치마크·데이터셋 조사 및 실험 활용 방안

> 작성: 2026-03-28 | 목적: Notion 정리 + 팀 공유용

---

## TL;DR

자체 Synthetic GT 검증하다 삽질이 길어져서 외부 자원을 조사했다. 결론:

- **데이터(pool, GT)는 바퀴를 재발명하지 말자** — MCP-Zero(308 servers), MCP-Atlas(500 human GT)를 가져다 쓰면 됨
- **우리 차별점은 E4(Description 품질 → 선택률)** — 여기에 시간을 집중
- 선행 연구(Description Smells)가 인과 관계를 이미 부분 검증해줌 → external validation으로 인용 가능

---

## 왜 조사했나

자체 Synthetic GT(838개, gpt-4o-mini) 수동 검증 중 3가지 구조적 문제 발견:

1. **Ambiguity 과소평가** — 생성 프롬프트가 tool 하나만 보여줘서 LLM이 다른 서버 존재를 모름
2. **Difficulty 기준 모호** — BM25/embedding/reranker 단계 구분 없이 감으로 판단
3. **크로스-서버 대안 미반영** — `alternative_tools`가 같은 서버 내부만 참조

→ 더 좋은 데이터가 이미 있는지 찾아봄

---

## 발견한 외부 자원 한눈에 보기

| 자원 | 규모 | 핵심 특징 | 우리에게 쓸모 | 검증 상태 |
|------|------|----------|-------------|----------|
| **MCP-Zero** | 308 servers, 2,797 tools | 2-stage routing + text-embedding-3-large (3072d) 벡터 포함 (단일 JSON) | Pool 확장 (E0, E2, E5) | ✅ GitHub에서 전체 스키마 확인 |
| **MCP-Atlas** | 500 tasks, 36 servers, 307 tools | Scale AI human-authored. TRAJECTORY에 tool call 시퀀스 포함 | GT 대체 (E1) | ✅ 논문+코드 교차 확인 (parquet 다운로드 후 최종 확인 필요) |
| **MCPAgentBench** | 200+ tasks (180 curated) | 정답 + distractor 혼합. 실행 기반 벤치마크 | 개념 참고 (E6) | ✅ tasks.json 스키마 확인 |
| **Description Smells** | 10,831 servers 분석 | **Description → 선택률 인과 검증** (p < 0.001) | E4 선행 연구 / E7 | ✅ 수치 확인 (논문 2편 확인) |
| **BFCL** | 2,000 QA pairs | 업계 표준 function calling. Irrelevance Detection | 방법론 참고 | - |
| **MCP-Bench** | 28 servers | Docker E2E 실행 평가 (Apache 2.0) | Bridge proxy 참고 | - |

---

## 실험별 활용 방법 (구체적으로)

### E0: 1-Layer vs 2-Layer

**문제**: 서버 8개면 1-Layer랑 2-Layer 차이가 안 남. 전수조사해도 되니까.

**해결**: MCP-Zero 308개 서버 pool을 가져와서 테스트. 서버가 많아야 "서버부터 거른다"는 2-Layer의 의미가 생김. MCP-Zero가 같은 구조(2-stage hierarchical routing)라서 **그들 결과를 baseline으로 직접 비교** 가능.

> 참고: MCP-Zero에서 서버 8→308 확장 시 정확도 97.6% → 69.2% 하락 확인됨

---

### E1: 검색 전략 비교 (Sequential / Parallel / Taxonomy)

**문제**: GT 품질이 낮으면 전략 비교 결과를 못 믿음.

**해결**: **MCP-Atlas 500개 human GT**를 가져다 씀. 사람이 쓴 자연어라 tool 이름이 쿼리에 안 들어감(= Medium/Hard 난이도). parquet 필드는 `TASK`, `PROMPT`, `ENABLED_TOOLS`, `TRAJECTORY`, `GTFA_CLAIMS`.

**핵심 발견 (parquet 분석 완료)**: MCP-Atlas는 multi-step 벤치마크. 평균 4.8 tool calls/task (min 3, max 17). TRAJECTORY는 대화 메시지 + tool_calls 내장 JSON array. 보일러플레이트 초기화 호출(`filesystem_list_allowed_directories` 36회 등)도 포함.

**GT 변환 전략**: per-step single-tool 분해 (ADR-0012). 상세 → `docs/adr/0012-per-step-ground-truth-decomposition.md`

---

### E2: 임베딩 모델 비교

**문제**: BGE-M3 vs text-embedding-3-small 두 개만 비교하려 했음.

**해결**: MCP-Zero에 **text-embedding-3-large (3072차원) 벡터가 이미 계산되어 포함**돼 있음 (server-level: `description_embedding` + `summary_embedding`, tool-level: `description_embedding`). re-embed 필요 없이 baseline 공짜로 확보. 비교 대상이 2개 → 3개로 풍부해짐.

---

### E3: Reranker 비교

외부 데이터셋 중 reranker를 다루는 게 없어서 **변경 없음**. 단, pool이 커지면 reranker 중요성 증가하므로 MCP-Zero pool에서 재측정 권장.

---

### E4: Description 품질 → 선택률 ⭐ 핵심

**문제**: "description 잘 쓰면 선택률 오른다"가 우리 핵심 테제. 처음부터 증명하려면 공이 큼.

**해결**: Description Smells 논문이 **이미 인과 관계를 검증**해놨음:

- Functionality smell 수정 → 선택 확률 **+11.6%** (p < 0.001)
- 경쟁 환경(동일 기능 서버 5개)에서 양질 description → **72% 선택** (baseline 20%)

**단, 그 논문은 "나쁜 거 고치면 좋아진다"까지만 보여줌.** 우리 차별점은 **GEO 기법으로 "어떻게 좋게 만드는가"를 체계적으로 제시**하는 것. narrative:

> "선행 연구에서 인과 관계 확인됨(+11.6%). 우리는 GEO 기법 적용으로 추가 +X% 달성."

---

### E5: Pool 스케일

**문제**: 5/20/50/100 서버 데이터 모으기 힘듦.

**해결**: MCP-Zero 308개에서 **서브샘플링** → 5 / 20 / 50 / 100 / 200 / 308 단계. 기존 계획(100까지)보다 3배 큰 규모까지 가능.

---

### E6: Pool 유사도

**문제**: 비슷한 tool 세트를 직접 구성하기 어려움.

**해결**: MCPAgentBench의 **distractor 개념**을 참고하되, 구현은 자체 설계. MCPAgentBench는 실행 기반 벤치마크라 정적 데이터 추출이 어려울 수 있음. MCP-Zero 308개 서버에서 도메인 유사도 기준으로 직접 서브셋 구성:

- High similarity = 같은 도메인 서버 밀집 → 혼동 잘 되는 환경
- Low similarity = 완전 다른 도메인만 → 혼동 안 되는 환경

---

### E7: GEO 점수 방식 비교

**해결**: Description Smells의 **4차원(Accuracy / Functionality / Completeness / Conciseness)** 18카테고리를 우리 GEO Score 6차원과 비교. Spearman 상관으로 어느 루브릭이 selection_rate와 더 관련 높은지 측정.

> 참고: Description Smells 관련 논문이 2편 존재:
> - `2602.18914`: "From Docs to Descriptions" — 10,831 servers, 4차원 18카테고리 smell 분류
> - `2602.14878`: "Tool Descriptions Are Smelly!" — 856 tools / 103 servers, 6-component scoring rubric

---

## 전략 변경 요약

| 영역 | AS-IS (지금) | TO-BE (변경 후) |
|------|-------------|----------------|
| Tool Pool | 8 servers, ~80 tools | MCP-Zero 308 servers, 2,797 tools (✅ 바로 사용 가능) |
| Ground Truth | gpt-4o-mini 838개 + 수동 검증 168개 | MCP-Atlas 500개 (human, 36 servers, 307 tools) + 자체 seed 80개 (✅ 구조 대부분 확인, parquet 최종 확인만 남음) |
| Distractor | 없음 | MCPAgentBench 개념 참고 + 자체 설계 |
| Description 평가 | GEO Score 6차원 | GEO Score + Description Smells 4차원 비교 (✅ 수치 검증됨) |

---

## 액션 아이템

### 이번 주 (High)

1. **MCP-Atlas parquet 다운로드 + TRAJECTORY 구조 확인** → `data/external/mcp-atlas/`
   - HuggingFace parquet 다운로드 후 TRAJECTORY 필드를 열어서 내부 구조 파악
   - tool call 추출 가능 여부 판단 → 변환 스크립트 설계
2. **MCP-Zero 데이터셋 다운로드** → `data/external/mcp-zero/`
   - GitHub README의 Google Drive에서 `mcp_tools_with_embedding.json` (단일 파일). repo-local canonical filename은 `data/external/mcp-zero/servers.json`
   - `tool_id` 없으므로 `"{server_name}::{tool_name}"` 조합 확인
3. **Description Smells 논문 정독**
   - 4차원 18카테고리 전체 목록 정리 (Table 3), 우리 GEO Score와 매핑 테이블 작성

### 다음 주 (Medium)

4. 자체 Synthetic GT 중 MCP-Atlas와 겹치는 서버 GT는 대체, 나머지만 유지
5. E4 A/B Description 작성 시 GEO + Smell 기준 병행
6. E5 Pool 설계를 MCP-Zero 308 기준으로 재설계

### 실험 단계에서 (Low)

7. MCPAgentBench distractor 방식 E6에 적용
8. BFCL Irrelevance Detection을 confidence branching 평가에 참고

---

## 우리 프로젝트의 차별화 포인트

기존 연구들은 전부 **"어떤 LLM이 tool을 잘 고르나"** (수요 측).
우리는 **"Provider가 description을 어떻게 쓰면 더 많이 선택되나"** (공급 측 최적화).

| 선행 연구 | 그들이 한 것 | 우리가 추가로 하는 것 |
|----------|------------|------------------|
| MCP-Zero | Tool routing 정확도 측정 | Description 품질이 routing에 미치는 영향 (E4) |
| Description Smells | "Smell 유무"의 영향 측정 | **GEO 기법으로 체계적 품질 향상 방법론** |
| MCPAgentBench | Task completion 기반 평가 | Provider 관점 analytics (왜 선택되었는가) |
| MCP-Atlas | Human-authored task 벤치마크 | Description 품질의 인과적 효과 측정 |

---

## 링크 모음

| 자원 | 링크 |
|------|------|
| MCP-Zero 논문 | https://arxiv.org/abs/2506.01056 |
| MCP-Zero GitHub | https://github.com/xfey/MCP-Zero |
| MCP-Atlas 논문 | https://arxiv.org/abs/2602.00933 |
| MCP-Atlas GitHub | https://github.com/scaleapi/mcp-atlas |
| MCP-Atlas HuggingFace | https://huggingface.co/datasets/ScaleAI/MCP-Atlas |
| MCP-Atlas Leaderboard | https://labs.scale.com/leaderboard/mcp_atlas |
| MCPAgentBench 논문 | https://arxiv.org/abs/2512.24565 |
| MCPAgentBench GitHub | https://github.com/zixianglhhh/MCPAgentBench |
| Description Smells 논문 (1) | https://arxiv.org/abs/2602.18914 (From Docs to Descriptions, 10,831 servers) |
| Description Smells 논문 (2) | https://arxiv.org/abs/2602.14878 (Tool Descriptions Are Smelly!, 103 servers) |
| BFCL V4 | https://gorilla.cs.berkeley.edu/leaderboard.html |
| MCP-Bench GitHub | https://github.com/Accenture/mcp-bench |
