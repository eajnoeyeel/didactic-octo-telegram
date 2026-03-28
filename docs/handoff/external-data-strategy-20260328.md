# Claude Code 핸드오프: 외부 데이터셋 전략 변경

> 작성: 2026-03-28
> 대상: Claude Code 세션 (다음 작업자용)
> 배경: `docs/research/external-benchmarks-20260328.md` 리서치 결과를 프로젝트에 반영하기 위한 지침서

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
| Ground Truth | gpt-4o-mini 838개 + 수동 검증 168개 | MCP-Atlas 500개 (human-authored) + 자체 seed 80개 |
| Distractor 설계 | 없음 (ambiguity 필드만) | MCPAgentBench 방식 (정답 + 비슷한 distractor 혼합) |
| Description 품질 평가 | GEO Score 6차원 (자체) | GEO Score + Description Smells 4차원 비교 |

**핵심 원칙**: 데이터 준비 시간을 줄이고 E4(Description 품질 → 선택률) 실험에 집중.

---

## 외부 자원 정보

### MCP-Zero (Tool Pool 확장용)
- 논문: https://arxiv.org/abs/2506.01056
- GitHub: https://github.com/xfey/MCP-Zero
- 데이터: 308 servers, 2,797 tools, text-embedding-3-large 벡터 포함
- 다운로드: GitHub README의 Google Drive 링크 → JSON
- 저장 위치: `data/external/mcp-zero/`

### MCP-Atlas (Ground Truth 대체용)
- 논문: https://arxiv.org/abs/2602.00933 (Scale AI)
- HuggingFace: https://huggingface.co/datasets/ScaleAI/MCP-Atlas
- 데이터: 500개 human-authored tasks, 36 servers, 220 tools
- 주의: multi-step task → 첫 번째 tool call만 추출 필요
- 저장 위치: `data/external/mcp-atlas/`

### Description Smells 논문 (E4 선행 연구)
- 논문: https://arxiv.org/abs/2602.18914
- 핵심: Description 품질 → 선택률 인과 관계 검증 완료 (+11.6%, p < 0.001)
- 4차원(Accuracy/Functionality/Completeness/Conciseness) 18카테고리 smell 분류
- 우리 차별점: 그들은 "smell 유무" 비교, 우리는 GEO 기법으로 체계적 개선 방법론 제시

### MCPAgentBench (Distractor 설계 참고)
- 논문: https://arxiv.org/abs/2512.24565
- 방법: 정답 tool + distractor tool 혼합으로 ambiguity 체계적 평가

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

#### `docs/design/ground-truth-design.md`
- "외부 GT 소스" 섹션 추가
  - MCP-Atlas: human-authored, 변환 방법 (첫 번째 tool call 추출)
  - source 필드에 `external_mcp_atlas` 값 추가
- Seed set 전략 변경: 자체 seed 80개 유지 + MCP-Atlas 500개 병합
- Synthetic GT(838개)의 역할 재정의: 보조 자료로 격하, MCP-Atlas GT와 겹치는 서버 GT는 대체

#### `docs/design/ground-truth-schema.md`
- `source` 필드 enum에 `external_mcp_atlas`, `external_mcp_zero` 추가
- 외부 GT의 `query_id` 네이밍 규칙 정의 (예: `gt-atlas-{number}`)

#### `docs/design/metrics-rubric.md`
- GEO Score 섹션에 Description Smells 4차원과의 매핑 테이블 추가
- E7 비교 축 명시: GEO 6차원 vs Smells 4차원 vs 통합 모델

#### `docs/design/code-structure.md`
- `data/external/` 디렉토리 추가
  - `data/external/mcp-zero/` — MCP-Zero 데이터셋 (servers.json, embeddings/)
  - `data/external/mcp-atlas/` — MCP-Atlas GT (raw parquet, converted JSONL)
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
  - External GT (MCP-Atlas): human-authored, `source=external_mcp_atlas`
  - 실험 간 GT 통일 원칙 유지: 외부 GT도 동일 JSONL 포맷으로 변환 후 사용
  - MCP-Atlas GT 사용 시 첫 번째 tool call만 추출하는 규칙 명시

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

#### 새 파일 작성
```
scripts/
├── import_mcp_zero.py        # MCP-Zero JSON → MCPServer/MCPTool 변환 + Qdrant 인덱싱
├── convert_mcp_atlas.py      # MCP-Atlas parquet → seed_set JSONL (첫 번째 tool call 추출)
└── download_external.py      # (선택) 외부 데이터 자동 다운로드 스크립트

data/external/
├── mcp-zero/                 # MCP-Zero 원본 (Git에서 제외, .gitignore 추가)
│   ├── servers.json
│   └── embeddings/
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
- multi-step task에서 첫 번째 tool call만 추출
- query_id 네이밍 규칙 준수 (gt-atlas-{number})
- source 필드가 "external_mcp_atlas"

# tests/unit/test_import_mcp_zero.py
- MCP-Zero JSON → MCPServer/MCPTool 변환 정상 동작
- tool_id 포맷이 "{server_id}::{tool_name}" 준수
- 임베딩 벡터 차원 검증 (3072 for text-embedding-3-large)
```

---

## 작업 순서 권장

```
1. ADR 작성 (docs/adr/0011-external-dataset-strategy.md)
2. 설계 문서 업데이트 (docs/design/ 5개 파일)
3. .claude/rules/ 업데이트 (3개 파일)
4. .claude/evals/ 업데이트 (4개 파일)
5. 계획 문서 업데이트 (docs/plan/ 3개 파일 + status-report)
6. CLAUDE.md 업데이트
7. 코드 변경 (models.py, config.py, .gitignore)
8. 새 스크립트 작성 (import_mcp_zero.py, convert_mcp_atlas.py)
9. 테스트 작성 + 검증
```

단계 1-6은 문서 변경이므로 한 커밋으로 묶어도 됨.
단계 7-9는 코드 변경이므로 별도 커밋 (feat: add external dataset integration).

---

## 참고 문서

- 리서치 원본: `docs/research/external-benchmarks-20260328.md`
- 프로젝트 개요: `docs/context/project-overview.md`
- 실험 설계: `docs/design/experiment-design.md`
- GT 설계: `docs/design/ground-truth-design.md`
