# Claude Code 핸드오프: 외부 데이터셋 전략 변경

> 작성: 2026-03-28
> 대상: Claude Code 세션 (다음 작업자용)
> 배경: `docs/research/external-benchmarks-20260328.md` 리서치 결과를 프로젝트에 반영하기 위한 지침서
> 상태 메모 (2026-03-29): 이 문서는 2026-03-28 시점 handoff snapshot이다. 현재 SOT는 `docs/adr/0011-external-dataset-strategy.md`, `docs/adr/0012-per-step-ground-truth-decomposition.md`, `docs/design/*`, 그리고 현재 repo 코드다. 아래 체크리스트 일부는 이미 완료 또는 부분 완료 상태다.

---

## 변경 배경

자체 Synthetic GT(838개, gpt-4o-mini) 수동 검증 중 3가지 구조적 문제 발견:

1. Ambiguity 과소평가 (생성 프롬프트가 tool 하나만 보여줌)
2. Difficulty 기준 모호 (LLM이 감으로 판단)
3. 크로스-서버 대안 미반영 (`alternative_tools`가 같은 서버 내부만 참조)

외부 리서치 결과, 이미 고품질 데이터셋과 관련 논문이 존재. 바퀴를 재발명하지 말고 가져다 쓴다.

---

## 전략 변경 요약

| 영역 | AS-IS | TO-BE |
|------|-------|-------|
| Tool Pool | 8 servers, ~80 tools (Smithery 직접 크롤링) | MCP-Zero 308 servers, 2,797 tools |
| Ground Truth | gpt-4o-mini 838개 + 수동 검증 168개 | MCP-Atlas 500개 (human-authored, 36 servers, 307 tools) + 자체 seed 80개 |
| Distractor 설계 | 없음 (ambiguity 필드만) | MCPAgentBench 방식 (정답 + 비슷한 distractor 혼합) |
| Description 품질 평가 | GEO Score 6차원 (자체) | GEO Score + Description Smells 4차원 비교 |

**핵심 원칙**: 데이터 준비 시간을 줄이고 E4(Description 품질 → 선택률) 실험에 집중.

---

## 외부 자원 정보

### MCP-Zero (Tool Pool 확장용) — ✅ 검증 완료 (GitHub에서 전체 스키마 확인)
- 논문: https://arxiv.org/abs/2506.01056
- GitHub: https://github.com/xfey/MCP-Zero
- 데이터: 308 servers, 2,797 tools, text-embedding-3-large (3072차원) 벡터 포함
- 수집 원본: MCP 공식 repo (Tag: 2025.4.28, Commit: ad2d4e6) — 396 servers 중 필터링 후 308개
- upstream 파일: 단일 JSON (`mcp_tools_with_embedding.json`)
- 로컬 canonical 파일: `data/external/mcp-zero/servers.json` — repo 스크립트 기준 입력 경로
- 다운로드: GitHub README의 Google Drive 링크 (HuggingFace는 "Coming soon")
- 라이선스: upstream README 기준 **MIT** (사용 전 재확인 권장)
- 저장 위치: `data/external/mcp-zero/`
- Server 필드 (확인됨):
  - `server_name`: string — 서버 이름 (README에서 추출)
  - `server_summary`: string — 서버 기능 요약
  - `server_description`: string — 메타데이터 설명
  - `description_embedding`: float[3072] — text-embedding-3-large
  - `summary_embedding`: float[3072] — text-embedding-3-large
  - `tools`: array — 하위 도구 목록
- Tool 필드 (확인됨):
  - `name`: string — 도구 식별자
  - `description`: string — 도구 설명
  - `description_embedding`: float[3072] — text-embedding-3-large
  - `parameter`: object — `{"param_name": "(type) description"}` 형식
- ⚠️ `tool_id` 필드 없음 → 우리 포맷 `"{server_name}::{tool_name}"` 으로 조합 필요

### MCP-Atlas (Ground Truth 대체용) — ✅ 논문+코드 교차 확인 (parquet 최종 확인만 남음)
- 논문: https://arxiv.org/abs/2602.00933 (Scale AI)
- GitHub: https://github.com/scaleapi/mcp-atlas
- HuggingFace: https://huggingface.co/datasets/ScaleAI/MCP-Atlas
- Leaderboard: https://labs.scale.com/leaderboard/mcp_atlas
- 데이터: 500개 공개 (총 1,000개), 36 servers, **307 tools** (이전 220은 오류)
- 파일: **parquet** (HuggingFace)
- 필드 (확인됨):
  - `TASK`: string — 고유 24자 ID
  - `PROMPT`: string — 자연어 쿼리 (single-turn, multi-tool-call 요구)
  - `ENABLED_TOOLS`: string — 10-25개 도구 서브셋 (task당 노출된 도구)
  - `TRAJECTORY`: string — **"the minimal sequence of tool calls (names, methods, dependencies, arguments, and tool outputs)"** (논문 정의)
  - `GTFA_CLAIMS`: string — 독립적으로 검증 가능한 claims 집합
- ✅ **TRAJECTORY 내용 확인**: 단순 서버명 목록이 아닌 **tool name + method + args + output + dependency** 포함 구조화 시퀀스
- ⚠️ **TRAJECTORY JSON 내부 스키마 미확정**: 평가 코드(`mcp_evals_scores.py`)에서 TRAJECTORY를 로드하지만 파싱하지 않음 → 정확한 key 이름은 parquet 직접 확인 필요
- ⚠️ **ENABLED_TOOLS 형식 미확인**: flat name vs server::tool 형태
- 📌 TRAJECTORY는 pass/fail 스코어링이 아닌 진단 분석(diagnostic analysis)용으로만 사용됨
- 저장 위치: `data/external/mcp-atlas/`
- ✅ **parquet 분석 완료**: TRAJECTORY는 대화 메시지 JSON array. assistant 메시지에 `tool_calls: [{function: {name, arguments}, id, type}]` 내장
- ✅ **tool_calls 통계**: 모든 500행에 존재, min 3, max 17, avg 4.8 calls/task
- ⚠️ **보일러플레이트 오염**: `filesystem_list_allowed_directories`(36회), `cli-mcp-server_show_security_rules`(26회), `desktop-commander_get_config`(22회) 등 초기화 호출이 첫 call로 빈번
- ⚠️ **범용 도구 집중**: `exa_web_search_exa`(42회) 같은 범용 검색이 첫 substantive call인 경우 다수
- 📋 **GT 변환 전략 (ADR-0012 updated 3/29)**: multi-step task를 **per-step single-tool GT로 분해**. 50~80 task 선별 → 각 substantive tool call마다 LLM으로 step-level query 생성 → Human review. Hit@K 폐기, Precision@1 통일

### Description Smells 논문 (E4 선행 연구) — ✅ 수치 검증 완료 + 관련 논문 2편 확인
- **논문 1**: https://arxiv.org/abs/2602.18914 — "From Docs to Descriptions" (10,831 servers, 4차원 18카테고리)
- **논문 2**: https://arxiv.org/abs/2602.14878 — "Tool Descriptions Are Smelly!" (856 tools / 103 servers, 6-component scoring rubric)
- 핵심: Description 품질 → 선택률 인과 관계 검증 완료 (+11.6%, p < 0.001)
- 분석 규모: **10,831 MCP servers** (논문 1 기준)
- 4차원(Accuracy/Functionality/Completeness/Conciseness) 18카테고리 smell 분류 (AST-based pattern matching + LLM card-sorting)
- 주요 발견: 73% tool이 tool name 반복, 3,449개가 잘못된 parameter semantics, 3,093개가 return description 누락
- 경쟁 환경(동일 기능 서버 5개): 양질 description → **72% 선택** (baseline 20% 대비, **260% 증가**)
- 우리 차별점: 그들은 "smell 유무" 비교, 우리는 GEO 기법으로 체계적 개선 방법론 제시
- ⚠️ **18카테고리 전체 목록은 논문 Table에서 확인 필요** (arxiv 접근 차단으로 미수집)
- ⚠️ 코드/데이터 공개 여부 미확인 — 논문 PDF에서 확인 필요

### MCPAgentBench (Distractor 개념 참고) — ✅ tasks.json 스키마 확인
- 논문: https://arxiv.org/abs/2512.24565
- GitHub: https://github.com/zixianglhhh/MCPAgentBench
- 규모: **200+ tasks** (tasks.json), 841 raw → 180 curated instances (수동 라벨링)
- 방법: 정답 tool (G) + distractor tool (F) 혼합으로 ambiguity 체계적 평가
- 파일: JSON (`data/daytasks.json`, `data/protasks.json`, `data/tasks.json`, + `*_with_*_tools.json` 변형)
- Task 스키마 (확인됨):
  - `id`: string — 고유 식별자 (예: `"daytask_1_tool_18"`)
  - `content`: string — 사용자 요청 (task description)
  - `tools`: array[array[string]] — nested 배열: `[["tool1"]]`(single), `[["tool1"],["tool2"]]`(sequential), `[["tool1","tool2"]]`(parallel)
  - `inputs`: array[array[object]] — tools에 대응하는 입력 파라미터
- TFS(Tool Function Selection): tools + inputs 정답 비율 (순서 무시)
- TEFS(Tool Execution Function Selection): 정확한 실행 순서 매칭 필요
- ⚠️ **실행 기반 벤치마크**: `servers/` 에 Python MCP 서버 구현 포함. 에이전트 기본 서버 수: 40개 (config.json)
- ⚠️ `correct_tools` vs `distractor_tools` 명시적 라벨링 없음 — `tools` 필드가 정답, 나머지 서버가 distractor
- 📋 **활용 방향**: 데이터셋 직접 사용 불가 → **distractor 개념 + nested tool 패턴만 참고, E6 pool 구성은 MCP-Zero 기반 자체 설계**

---

## 수정 대상 파일 목록 및 지침

### 1단계: 설계 문서 (Source of Truth) 업데이트

#### `docs/design/experiment-design.md`
- E0: "MCP-Zero 308 servers pool에서 테스트" 반영
- E1: "MCP-Atlas 500 GT 활용" 반영
- E2: text-embedding-3-large (MCP-Zero 제공) 비교 대상 추가 (2개 → 3개)
- E4: Description Smells 논문을 external validation으로 명시
- E5: Pool 범위를 5/20/50/100/200/308으로 확장
- E6: MCPAgentBench distractor 접근법 명시
- E7: Description Smells 4차원을 비교 루브릭으로 추가

#### `docs/design/experiment-details.md`
- 각 실험의 입력/출력 스펙에 외부 데이터셋 경로 추가
- E2에 text-embedding-3-large 조건 추가

#### `docs/design/ground-truth-design.md` — ✅ 완료 (ADR-0012 per-step 반영)
- "외부 GT 소스" 섹션 추가 + ADR-0012 per-step single-tool 분해 전략 반영
  - MCP-Atlas: 50~80 task 선별 → per-step 분해 (~150-240 single-step GT)
  - 보일러플레이트 blocklist, 서버/도구 ID 변환 규칙, `origin_task_id` + `step_index` lineage
  - source 필드에 `external_mcp_atlas` 값 추가, 모든 GT는 `task_type=single_step`
- Seed set: 자체 seed 80개 유지 + MCP-Atlas per-step ~150-240 병합 (~230-320 primary)
- Synthetic GT(838개)의 역할 재정의: 보조 자료로 격하

#### `docs/design/ground-truth-schema.md`
- `source` 필드 enum에 `external_mcp_atlas`, `external_mcp_zero` 추가
- `task_type` 필드 추가 (모든 GT는 `single_step`)
- `origin_task_id`, `step_index` lineage 필드 추가 (ADR-0012 per-step)
- 외부 GT의 `query_id` 네이밍 규칙: `gt-atlas-{task:03d}-s{step:02d}`

#### `docs/design/metrics-rubric.md`
- GEO Score 섹션에 Description Smells 4차원과의 매핑 테이블 추가
- E7 비교 축 명시: GEO 6차원 vs Smells 4차원 vs 통합 모델

#### `docs/design/code-structure.md`
- `data/external/` 디렉토리 추가
  - `data/external/mcp-zero/` — MCP-Zero 데이터셋 (repo-local canonical input: `servers.json`)
  - `data/external/mcp-atlas/` — MCP-Atlas GT (raw parquet, converted JSONL)
- `scripts/import_mcp_zero.py` — MCP-Zero JSON → MCPServer/MCPTool + Qdrant 인덱싱
- `scripts/convert_mcp_atlas.py` — MCP-Atlas parquet → 우리 GT JSONL 변환 스크립트

---

### 2단계: 계획 문서 업데이트

#### `docs/plan/implementation.md`
- Phase 1 (데이터 수집)에 "외부 데이터셋 통합" 태스크 추가
- 새로운 스크립트 목록에 `scripts/convert_mcp_atlas.py`, `scripts/import_mcp_zero.py` 추가

#### `docs/plan/checklist.md`
- OQ-2 (Smithery 크롤링 + Pool 구성) 범위 변경:
  - 기존: Smithery에서 카테고리별 5-10개 균형 수집
  - 변경: MCP-Zero 308 servers 활용 + Smithery는 보조 소스
- 새 체크리스트 항목 추가:
  - [ ] MCP-Zero 데이터셋 다운로드 → `data/external/mcp-zero/`
  - [ ] MCP-Atlas GT 다운로드 → `data/external/mcp-atlas/`
  - [ ] `scripts/convert_mcp_atlas.py` 작성 (parquet → JSONL)
  - [ ] `scripts/import_mcp_zero.py` 작성 (JSON → 우리 MCPServer/MCPTool 모델)
  - [ ] Description Smells 4차원 vs GEO Score 6차원 매핑 테이블 작성

#### `docs/plan/deferred.md`
- 자체 Synthetic GT 838개의 추가 수동 검증은 후순위로 이동 (MCP-Atlas가 대체)

#### `docs/progress/status-report.md`
- "전략 변경" 섹션 추가: 외부 데이터셋 활용 결정 (2026-03-28)
- 다음 단계 업데이트: Phase 6 + OQ-2 → Phase 6 + 외부 데이터 통합

---

### 3단계: .claude/ 규칙 업데이트

#### `.claude/rules/architecture.md`
- Module Structure에 `data/external/` 디렉토리 반영
- 데이터 소스 다이어그램에 외부 데이터 흐름 추가:
  ```
  External Sources (MCP-Zero, MCP-Atlas)
      ↓ import scripts
  data/external/ → data/ground_truth/ (변환 후)
                 → Qdrant (인덱싱 후)
  ```

#### `.claude/rules/eval-workflow.md`
- Ground Truth 룰 섹션에 추가:
  - External GT (MCP-Atlas): human-authored 기반, per-step 분해 후 `source=external_mcp_atlas`
  - 실험 간 GT 통일 원칙 유지: 외부 GT도 동일 JSONL 포맷으로 변환 후 사용
  - MCP-Atlas per-step 분해 규칙 명시 (ADR-0012): 50~80 task 선별, LLM query 생성, Human review

#### `.claude/evals/E0-baseline.md` ~ `.claude/evals/E4-thesis.md`
- 각 eval 정의에 데이터 소스 명시 (기존 자체 GT → MCP-Atlas + 자체 seed)
- E2에 text-embedding-3-large 조건 추가
- E4에 Description Smells 논문을 baseline 참조로 추가

---

### 4단계: ADR 작성

#### `docs/adr/0011-external-dataset-strategy.md` (신규)
- 제목: "외부 데이터셋(MCP-Zero, MCP-Atlas) 활용 전략"
- 컨텍스트: 자체 Synthetic GT 품질 문제 → 외부 고품질 데이터 활용 결정
- 결정:
  1. Pool은 MCP-Zero 308 servers 기반
  2. GT는 MCP-Atlas 500 + 자체 seed 80
  3. Description 품질 평가는 GEO + Smells 병행
- 근거: 시간 절약, 품질 향상, 선행 연구와의 비교 가능성
- 결과: 기존 Smithery 크롤링 데이터(8 servers)는 보조 소스로 유지

---

### 5단계: 코드 변경

#### 코드 상태 메모
```
scripts/
├── import_mcp_zero.py        # 존재함. canonical input은 data/external/mcp-zero/servers.json
├── convert_mcp_atlas.py      # 존재함. ADR-0012 per-step target state는 아직 TODO
└── download_external.py      # (선택) 외부 데이터 자동 다운로드 스크립트

data/external/
├── mcp-zero/                 # MCP-Zero 원본 (Git에서 제외, .gitignore 추가)
│   └── servers.json          # repo-local canonical filename
├── mcp-atlas/                # MCP-Atlas 원본 (Git에서 제외)
│   └── *.parquet
└── README.md                 # 다운로드 방법, 라이선스 정보
```

#### 기존 파일 수정
- `src/models.py`:
  - `GroundTruthEntry.source` Enum에 `external_mcp_atlas`, `external_mcp_zero` 추가
- `src/data/ground_truth.py`:
  - 외부 GT 로딩 함수 추가 (`load_external_gt()`)
  - MCP-Atlas 포맷 → 우리 GroundTruthEntry 변환 로직
- `src/config.py`:
  - `external_data_dir: str = "data/external"` 설정 추가
- `.gitignore`:
  - `data/external/mcp-zero/` 추가
  - `data/external/mcp-atlas/` 추가
- `CLAUDE.md`:
  - Commands 섹션에 외부 데이터 관련 스크립트 추가
  - 상세 컨텍스트 참조 테이블에 `docs/research/external-benchmarks-20260328.md` 추가

---

### 6단계: 테스트

```python
# tests/unit/test_convert_mcp_atlas.py
- MCP-Atlas parquet → GroundTruthEntry 변환 정상 동작
- multi-step task를 substantive tool call 단위로 per-step 분해 (ADR-0012 target state)
- query_id 네이밍 규칙 준수 (gt-atlas-{task:03d}-s{step:02d})
- source 필드가 "external_mcp_atlas"

# tests/unit/test_import_mcp_zero.py
- MCP-Zero JSON → MCPServer/MCPTool 변환 정상 동작
- tool_id 포맷이 "{server_id}::{tool_name}" 준수
- 임베딩 벡터 차원 검증 (3072 for text-embedding-3-large)
```

---

## 작업 순서 권장

```
0. [선행] MCP-Atlas parquet 다운로드 → TRAJECTORY 필드 구조 확인 — ✅ 완료
   → multi-step (avg 4.8 calls), 보일러플레이트 오염 확인
   → ADR-0012 결정 (3/29 업데이트): per-step single-tool GT 분해 (Hit@K 폐기)
1. ADR 작성 (docs/adr/0011-external-dataset-strategy.md) — ✅ 완료
2. 설계 문서 업데이트 (docs/design/ 6개 파일)
3. .claude/rules/ 업데이트 — ✅ 완료 (architecture.md, eval-workflow.md 반영됨)
4. .claude/evals/ 업데이트 (3개 파일)
5. 계획 문서 업데이트 (docs/plan/ 3개 파일 + status-report)
6. CLAUDE.md 업데이트 — ✅ 완료 (참조 테이블 반영됨)
7. 코드 변경 (models.py, config.py, .gitignore)
8. 새 스크립트 작성 (import_mcp_zero.py, convert_mcp_atlas.py)
9. 테스트 작성 + 검증
```

단계 0은 반드시 먼저 — MCP-Atlas 활용 가능 여부에 따라 후속 작업이 달라짐.
단계 2-5는 문서 변경이므로 한 커밋으로 묶어도 됨.
단계 7-9는 코드 변경이므로 별도 커밋 (feat: add external dataset integration).

---

## 참고 문서

- 리서치 원본: `docs/research/external-benchmarks-20260328.md`
- 프로젝트 개요: `docs/context/project-overview.md`
- 실험 설계: `docs/design/experiment-design.md`
- GT 설계: `docs/design/ground-truth-design.md`
