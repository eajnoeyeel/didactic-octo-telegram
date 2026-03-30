# 외부 벤치마크·데이터셋 조사 및 실험 활용 방안

> 초판: 2026-03-28 | 검증 보강: 2026-03-30 (API 직접 호출 + 필드 검증)
> 목적: Notion 정리 + 팀 공유용

---

## TL;DR

자체 Synthetic GT 검증하다 삽질이 길어져서 외부 자원을 조사했다. 결론:

- **데이터(pool, GT)는 바퀴를 재발명하지 말자** — MCP-Zero(308 servers), MCP-Atlas(500 human GT)를 가져다 쓰면 됨
- **우리 차별점은 E4(Description 품질 → 선택률)** — 여기에 시간을 집중
- 선행 연구(Description Smells)가 인과 관계를 이미 부분 검증해줌 → external validation으로 인용 가능
- **(2026-03-30 추가)** MCP-Atlas 대안/보완 GT 9개 데이터셋 심층 검증 완료. MCPToolBench++만 보조 사용 가능, 나머지는 부적합 또는 제한적. **MCP-Atlas per-step 분해 + self seed 80개 전략 유지가 최선.**

---

## 왜 조사했나

자체 Synthetic GT(838개, gpt-4o-mini) 수동 검증 중 3가지 구조적 문제 발견:

1. **Ambiguity 과소평가** — 생성 프롬프트가 tool 하나만 보여줘서 LLM이 다른 서버 존재를 모름
2. **Difficulty 기준 모호** — BM25/embedding/reranker 단계 구분 없이 감으로 판단
3. **크로스-서버 대안 미반영** — `alternative_tools`가 같은 서버 내부만 참조

→ 더 좋은 데이터가 이미 있는지 찾아봄

---

## 발견한 외부 자원 한눈에 보기

| 자원 | 규모 | 핵심 특징 | 우리에게 쓸모 | 판정 | 검증 상태 |
|------|------|----------|-------------|------|----------|
| **MCP-Zero** | 308 servers, 2,797 tools | 2-stage routing + text-embedding-3-large (3072d) 벡터 포함 | Pool 확장 (E0, E2, E5) | ✅ 사용 | ✅ GitHub 스키마 확인 |
| **MCP-Atlas** | 500 tasks, 36 servers, 307 tools | Scale AI human-authored. TRAJECTORY에 tool call 시퀀스 포함 | GT 대체 (E1) — Primary | ✅ 사용 | ✅ parquet 확인 |
| **MCPToolBench++** | 1,509 instances / 87 tools / 6 categories | MCP-native single-step GT, `mcp_server` 필드 | 보조 GT (E0/E1 smoke test) | 🔧 가공 후 사용 | ✅ HF API 직접 검증 |
| **ToolRet** | 7,961 queries / 44,453 tools | ACL 2025, tool retrieval 전용 벤치마크 | Method validation용 참조 | ⚠️ 제한적 | ✅ HF API 직접 검증 |
| **MCPVerse** | 250 tasks / 65 servers / 552 tools | Real-world MCP task, L1/L2/L3 complexity | Tool registry로 pool 보강 | ⚠️ 제한적 | ✅ GitHub 구조 확인 |
| **MCPAgentBench** | 200+ tasks (180 curated) | 정답 + distractor 혼합, 실행 기반 | 개념 참고 (E6) | ⚠️ 참고만 | ✅ tasks.json 확인 |
| **Description Smells** | 10,831 servers 분석 | Description → 선택률 인과 검증 (p < 0.001) | E4 선행 연구 / E7 | ✅ 인용 | ✅ 수치 확인 |
| **BFCL** | 2,000 QA pairs | 업계 표준 function calling, Irrelevance Detection | 방법론 참고 | ⚠️ 참고만 | - |
| **MCP-Bench** | 28 servers / 250 tools | Docker E2E 실행 평가 (Apache 2.0) | Bridge proxy 참고 | ❌ 부적합 | 문서 확인 |
| **MCP-Radar** | 507 tasks / ~50 tools | 5-dimensional 평가 | Metric 설계 참고만 | ❌ 부적합 | 문서만 (anonymous repo) |
| **ToolBench/StableToolBench** | 16,464 APIs | ICLR 2024, pre-selected pool | 부적합 (retrieval 아님) | ❌ 부적합 | 문서 확인 |
| **AppSelectBench** | 100 apps / 100K+ tasks | 데스크톱 앱 선택 | 도메인 불일치 | ❌ 부적합 | - |
| **MCPBench** | Web Search 200 QA | 서버 간 성능 비교 | Tool selection GT 없음 | ❌ 부적합 | - |
| **MCPMark** | — | MCP 서버 stress-testing | Tool selection 무관 | ❌ 부적합 | - |

---

## 우리 실험에 필요한 필드 요구사항 (2026-03-30)

데이터셋 활용 가능 여부를 판단하는 기준:

| 필드 | 실험 단계 | 필수 여부 |
|------|----------|----------|
| 자연어 쿼리 (query) | 전체 (E0-E7) | **필수** |
| 정답 tool_id (single) | Precision@1, MRR, NDCG@5 | **필수** |
| 정답 server_id | Server Recall@K, 2-Layer 평가 | **필수** |
| tool description | E4 (Description 품질 실험) | **필수** |
| tool input_schema | Pool 구성, 인덱싱 | 권장 |
| difficulty / ambiguity | 난이도별 분석 | 권장 |
| category | 도메인별 분석 | 권장 |
| alternative_tools | NDCG@5 graded relevance | 선택 |
| retrieval 후보 pool | E5 (Pool 스케일) | 별도 소스 가능 (MCP-Zero) |

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

**해결**: MCP-Zero 308개에서 **서브샘플링** → 5 / 20 / 50 / 100 / 200 / 308 단계. 기존 계획(100까지)보다 3배 큰 규모까지 가능. **(2026-03-30 추가)** MCPVerse `tool_full.json` (552 tools, 65 servers)도 pool 보강에 활용 가능 — MCP-Zero와 중복 서버 확인 필요.

---

### E6: Pool 유사도

**문제**: 비슷한 tool 세트를 직접 구성하기 어려움.

**해결**: MCPAgentBench의 **distractor 개념**을 참고하되, 구현은 자체 설계. MCPAgentBench는 실행 기반 벤치마크라 정적 데이터 추출이 어려울 수 있음. MCP-Zero 308개 서버에서 도메인 유사도 기준으로 직접 서브셋 구성:

- High similarity = 같은 도메인 서버 밀집 → 혼동 잘 되는 환경
- Low similarity = 완전 다른 도메인만 → 혼동 안 되는 환경

**(2026-03-30 추가)** MCPVerse의 도메인 참조도 유사도 서브셋 구성에 활용 가능.

---

### E7: GEO 점수 방식 비교

**해결**: Description Smells의 **4차원(Accuracy / Functionality / Completeness / Conciseness)** 18카테고리를 우리 GEO Score 6차원과 비교. Spearman 상관으로 어느 루브릭이 selection_rate와 더 관련 높은지 측정.

> 참고: Description Smells 관련 논문이 2편 존재:
> - `2602.18914`: "From Docs to Descriptions" — 10,831 servers, 4차원 18카테고리 smell 분류
> - `2602.14878`: "Tool Descriptions Are Smelly!" — 856 tools / 103 servers, 6-component scoring rubric

---

## 실험 단계별 활용 가능성 종합 (2026-03-30)

| 실험 | MCP-Atlas | MCP-Zero | MCPToolBench++ | MCPVerse | ToolRet | Description Smells |
|------|-----------|----------|----------------|----------|---------|-------------------|
| **E0** (1L vs 2L) | ✅ Primary GT | ✅ Pool | 🔧 smoke test | 🔧 L1만 | ❌ | — |
| **E1** (전략 비교) | ✅ Primary GT | ✅ Pool | 🔧 소규모 | ❌ multi-tool | ❌ | — |
| **E2** (임베딩) | ✅ Primary GT | ✅ 사전 벡터 | 🔧 가능 | ❌ | ⚠️ 참조 비교 | — |
| **E3** (Reranker) | ✅ Primary GT | ✅ Pool | ❌ | ❌ | ❌ | — |
| **E4** (Description) | ✅ + self seed | — | ⚠️ desc 짧음 | ❌ | ❌ | ✅ 선행 연구 |
| **E5** (Pool 스케일) | ✅ | ✅ 308 서버 | ❌ | 🔧 552 tools pool 보강 | ❌ | — |
| **E6** (Pool 유사도) | ✅ | ✅ 서브셋 | ❌ | 🔧 domain 참조 | ❌ | — |
| **E7** (GEO 점수) | ✅ | — | ❌ | ❌ | ❌ | ✅ 4차원 비교 |

---

## GT 요구 필드 충족도 비교 (2026-03-30 검증)

| 요구 필드 | MCP-Atlas | MCPToolBench++ | MCPVerse | ToolRet |
|----------|-----------|----------------|----------|---------|
| 자연어 query | ✅ | ⚠️ 지시형 | ⚠️ task형 | ✅ |
| single correct_tool_id | 🔧 분해 필요 | ✅ | ❌ multi | ⚠️ config 의존 |
| server_id | 🔧 변환 필요 | ✅ mcp_server | ✅ required_MCPs | ❌ 없음 |
| tool description | ✅ (307 tools) | ✅ (평균 42자) | ✅ (552 tools) | ⚠️ 일부 빈값 |
| input_schema | ✅ | ✅ | ✅ | ⚠️ 일부만 |
| difficulty | ❌ 수동 추가 | ❌ | ⚠️ L1/L2/L3 | ❌ |
| MCP 도메인 일치 | ✅ | ✅ MCP native | ✅ MCP native | ❌ REST API |
| Human-authored | ✅ Scale AI | ❌ template | ⚠️ 반자동 | ❌ LLM+template |
| 라이선스 | ✅ CC-BY-4.0 | ⚠️ 미확인 | ✅ Apache 2.0 | ✅ Apache 2.0 |

---

## 데이터셋별 상세 검증 (2026-03-30 API 직접 호출)

> 이하 섹션은 MCP-Atlas 외 후보 GT 데이터셋을 API 직접 호출 및 GitHub 리포 확인으로 심층 검증한 결과.

### MCPToolBench++ ⭐ 보조 사용 가능

- **출처**: arXiv:2508.07575 (Aug 2025)
- **규모**: 1,509 instances / 87 unique tools / 6 categories
- **포맷**: HuggingFace JSON
- **라이선스**: CC-BY 4.0 (논문), 리포 라이선스 미명시
- **접근**: `load_dataset("MCPToolBench/MCPToolBenchPP")`

**API 직접 검증 결과:**

```
FIELDS: ['uuid', 'category', 'call_type', 'tools', 'mcp_tools_dict', 'query', 'function_call_label']
function_call_label = {name, step, id, mcp_server, similar_tools, input, output}
tool schema = {name, description, input_schema}

Stats (first 200 entries):
- Categories: browser 188, filesystem 12
- Call types: single 200 (100%)
- Description 비어있음: 0/3,200
- Description 평균 길이: 42자 (min 17, max 129)
- Tools per entry: 32 (browser), 11 (filesystem)
```

**장점:** MCP-native 포맷, `mcp_server` 필드로 server_id 직접 추출, `tool_id = "{mcp_server}::{tool_name}"` 조합으로 우리 포맷 일치, `similar_tools` 대안 목록 제공

**한계:** tool pool 87개 (우리 target 308+ 대비 작음), browser/filesystem 카테고리 편향, 쿼리가 지시형 ("Click the button…"), description 짧음 (평균 42자), HuggingFace Parquet 변환 에러 — GitHub JSON 직접 다운로드 필요

**판정: 일부 가공 후 사용 가능** — E0/E1 파이프라인 regression test용 소규모 외부 GT로 활용. Primary GT로는 부적합.

---

### ToolRet (ACL 2025)

- **출처**: ACL 2025 Findings, 중국과학기술대학+PKU
- **규모**: 7,961 queries / 44,453 tools
- **포맷**: HuggingFace Parquet (35개 config로 분리)
- **라이선스**: Apache 2.0
- **접근**: `load_dataset("mangopy/ToolRet-Queries", "<config>")`

**API 직접 검증 — config별 single/multi-label 분포:**

| Config | 총 쿼리 | Single-label | Multi-label | 빈 description |
|--------|---------|-------------|-------------|---------------|
| `toolbench` | 301 | 13 (4%) | 288 (96%) | 70개 |
| `metatool` | 200 | 179 (90%) | 21 (10%) | 0 |
| `gorilla-huggingface` | 301 | 301 (100%) | 0 (0%) | 0 |
| `apibank` | 101 | 48 (48%) | 53 (52%) | 0 |
| `toolalpaca` | 94 | 94 (100%) | 0 (0%) | 0 |

**치명적 한계:** server_id 없음 (RapidAPI/HuggingFace API 기반), MCP tool 구조 아님, 35개 config 간 스키마 불일치, relevance score 전부 binary (graded 없음)

**판정: 제한적 사용** — `gorilla-huggingface` (301) + `toolalpaca` (94)를 method validation용으로만 활용. 논문 인용: "기존 IR 모델은 Recall@10 < 52%" → 우리 2-stage 차별점 논증.

---

### MCPVerse (2025)

- **출처**: arXiv:2508.16260
- **규모**: 250 tasks / 65 MCP servers / 552 tools
- **라이선스**: Apache 2.0
- **접근**: https://github.com/hailsham/mcpverse

**Task 필드:** `question, required_MCPs, required_tools, time_sensitivity, complexity, task_type, ground_truth`

**Tool Registry:** `tool_full.json` — 표준 MCP tool 스키마 (name, description, inputSchema)

**한계:** required_tools가 리스트 (multi-tool), L1만 single-tool 가능성, time-sensitive tasks 재현성 문제, outcome-based 평가 (task completion 기반)

**판정: 제한적 사용** — L1 single-tool tasks 필터링 시 보조 GT 가능. `tool_full.json` (552 tools)을 E5 pool 확장용으로 활용.

---

### 부적합 데이터셋 요약

| 데이터셋 | 부적합 사유 |
|----------|-----------|
| **MCP-Radar** (arXiv:2505.16700) | 라이선스 미명시, anonymous repo, tool selection GT 부재, answer-based 평가 |
| **ToolBench/StableToolBench** (ICLR 2024) | Pre-selected pool이라 retrieval 평가 무의미, RapidAPI 기반 |
| **AppSelectBench** (Microsoft) | 데스크톱 앱 선택 도메인, multi-label GT, MCP 무관 |
| **MCP-Bench** (Accenture) | Execution-based E2E 벤치마크, tool selection GT 없음 |
| **MCPBench** (ModelScope) | 서버 간 성능 비교 목적, tool selection 무관 |
| **MCPMark** | 스트레스 테스트 벤치마크, tool selection 무관 |

---

## 전략 변경 요약

| 영역 | AS-IS (지금) | TO-BE (변경 후) |
|------|-------------|----------------|
| Tool Pool | 8 servers, ~80 tools | MCP-Zero 308 servers, 2,797 tools (✅ 바로 사용 가능) |
| Ground Truth | gpt-4o-mini 838개 + 수동 검증 168개 | MCP-Atlas 500개 (human, 36 servers, 307 tools) + 자체 seed 80개 (✅ 구조 대부분 확인, parquet 최종 확인만 남음) |
| 보조 GT | 없음 | MCPToolBench++ single-step subset (E0/E1 regression test) |
| Pool 보강 | 없음 | MCPVerse 552 tools (E5 확장용), MCP-Bench 28 servers (참고) |
| Method validation | 없음 | ToolRet gorilla/toolalpaca (논문 인용) |
| Distractor | 없음 | MCPAgentBench 개념 참고 + 자체 설계 |
| Description 평가 | GEO Score 6차원 | GEO Score + Description Smells 4차원 비교 (✅ 수치 검증됨) |

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
| ToolRet | Tool retrieval 벤치마크 | 2-stage MCP-specific pipeline |

---

## 액션 아이템

### 이번 주 (High) — 2026-03-28 원본

1. **MCP-Atlas parquet 다운로드 + TRAJECTORY 구조 확인** → `data/external/mcp-atlas/`
2. **MCP-Zero 데이터셋 다운로드** → `data/external/mcp-zero/`
3. **Description Smells 논문 정독** — 4차원 18카테고리 전체 목록 정리

### 이번 스프린트 (High) — 2026-03-30 추가

4. ~~MCP-Atlas per-step 분해~~ (기존 계획 유지)
5. **MCPToolBench++ single-step subset 다운로드** → `data/external/mcptoolbench/`
   - GitHub에서 JSON 직접 다운로드 (HuggingFace Parquet 변환 에러 있음)
   - 변환 스크립트: `scripts/convert_mcptoolbench.py` (field mapping → GroundTruthEntry)

### 다음 주 (Medium)

6. 자체 Synthetic GT 중 MCP-Atlas와 겹치는 서버 GT는 대체, 나머지만 유지
7. E4 A/B Description 작성 시 GEO + Smell 기준 병행
8. E5 Pool 설계를 MCP-Zero 308 기준으로 재설계
9. MCPVerse `tool_full.json` 다운로드 → E5 pool 확장 검토
10. ToolRet gorilla/toolalpaca subset으로 retrieval 성능 cross-validation 설계

### 실험 단계에서 (Low)

11. MCPAgentBench distractor 방식 E6에 적용
12. BFCL Irrelevance Detection을 confidence branching 평가에 참고

### 논문 작성 시

13. ToolRet 논문 인용: "기존 IR 모델은 Recall@10 < 52%" → 우리 2-stage 파이프라인의 차별점 강조
14. MCPToolBench++ 인용: 외부 MCP-native 데이터에서도 파이프라인 작동 확인 (external validity)

---

## 링크 모음

| 자원 | 링크 | 상태 |
|------|------|------|
| MCP-Zero 논문 | https://arxiv.org/abs/2506.01056 | — |
| MCP-Zero GitHub | https://github.com/xfey/MCP-Zero | ✅ |
| MCP-Atlas 논문 | https://arxiv.org/abs/2602.00933 | — |
| MCP-Atlas GitHub | https://github.com/scaleapi/mcp-atlas | ✅ |
| MCP-Atlas HuggingFace | https://huggingface.co/datasets/ScaleAI/MCP-Atlas | ✅ |
| MCP-Atlas Leaderboard | https://labs.scale.com/leaderboard/mcp_atlas | ✅ |
| MCPToolBench++ GitHub | https://github.com/mcp-tool-bench/MCPToolBenchPP | ✅ 공개 |
| MCPToolBench++ HF | https://huggingface.co/datasets/MCPToolBench/MCPToolBenchPP | ⚠️ Parquet 에러 |
| MCPToolBench++ 논문 | https://arxiv.org/abs/2508.07575 | Aug 2025 |
| ToolRet GitHub | https://github.com/mangopy/tool-retrieval-benchmark | ✅ 공개 |
| ToolRet Queries (HF) | https://huggingface.co/datasets/mangopy/ToolRet-Queries | ✅ API 검증 |
| ToolRet Tools (HF) | https://huggingface.co/datasets/mangopy/ToolRet-Tools | ✅ API 검증 |
| ToolRet 논문 | https://arxiv.org/abs/2503.01763 | ACL 2025 |
| MCPVerse GitHub | https://github.com/hailsham/mcpverse | ✅ 공개 |
| MCPVerse 논문 | https://arxiv.org/abs/2508.16260 | Aug 2025 |
| MCPAgentBench 논문 | https://arxiv.org/abs/2512.24565 | — |
| MCPAgentBench GitHub | https://github.com/zixianglhhh/MCPAgentBench | ✅ |
| Description Smells 논문 (1) | https://arxiv.org/abs/2602.18914 | 10,831 servers |
| Description Smells 논문 (2) | https://arxiv.org/abs/2602.14878 | 103 servers |
| MCP-Radar 논문 | https://arxiv.org/abs/2505.16700 | ⚠️ Anonymous |
| MCP-Bench GitHub | https://github.com/Accenture/mcp-bench | ✅ Apache 2.0 |
| MCPBench GitHub | https://github.com/modelscope/MCPBench | ✅ |
| BFCL V4 | https://gorilla.cs.berkeley.edu/leaderboard.html | — |
| ToolBench GitHub | https://github.com/OpenBMB/ToolBench | ✅ Apache 2.0 |
| StableToolBench | https://zhichengg.github.io/stb.github.io/ | ✅ |
| AppSelectBench | https://microsoft.github.io/appselectbench/ | CC-BY-SA 4.0 |
