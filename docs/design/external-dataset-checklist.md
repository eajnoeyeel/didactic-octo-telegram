# External Dataset Checklist (ADR-0013)

외부 데이터셋을 GT 또는 Pool에 추가하기 전 반드시 완료해야 하는 체크리스트.
이 문서를 건너뛰면 E5 sweep 무효화 사태(2026-04-02)가 반복된다.

---

## Phase 1: Pool-GT Alignment 검증 (Blocking Gate)

**모든 GT 추가/변경 전에 반드시 실행한다.**

```bash
uv run python scripts/validate_pool_gt_alignment.py \
  --pool data/raw/mcp_zero_servers.jsonl \
  --gt data/ground_truth/seed_set.jsonl data/ground_truth/mcp_atlas.jsonl \
  --pool-sizes 5 20 50 100 200 292 \
  --json-out data/results/alignment_report.json
```

**통과 기준 (모두 충족해야 PR merge 가능):**
- [ ] covered_servers / total_gt_servers >= 25%
- [ ] 최소 실험 pool_size에서 GT entries >= 20개
- [ ] 단일 서버 query 집중도 < 50% (HIGH SKEW 경보 없음)
- [ ] alignment_report.json을 PR에 첨부

---

## Phase 2: GT 데이터셋 추가 시

새 외부 소스(MCP-Atlas 등)에서 GT를 생성할 때:

- [ ] `--pool-file data/raw/mcp_zero_servers.jsonl` 옵션 명시 (pool filter 적용)
  ```bash
  uv run python scripts/convert_mcp_atlas.py \
    --pool-file data/raw/mcp_zero_servers.jsonl \
    --max-tasks 80
  ```
- [ ] `verify_ground_truth.py` Quality Gate 통과
  ```bash
  uv run python scripts/verify_ground_truth.py
  ```
- [ ] Phase 1 alignment 재실행 → coverage 수치 기록

**확인할 필드 매핑:**
| GT 소스 필드 | 내부 필드 | 형식 |
|------------|---------|-----|
| `correct_server_id` | server_id | MCP-Zero의 `server_id`와 일치해야 함 |
| `correct_tool_id` | `{server_id}::{tool_name}` | TOOL_ID_SEPARATOR = `::` |
| `query_id` | `gt-{source}-{task:03d}-s{step:02d}` | 고유해야 함 |

---

## Phase 3: Pool 확장 시

MCP-Zero pool에 서버를 추가할 때:

- [ ] Smithery API로 fetch 가능 여부 확인 (dry-run 먼저)
  ```bash
  uv run python scripts/fetch_missing_gt_servers.py --dry-run
  ```
- [ ] Qdrant Free tier 한도 확인 (1GB)
- [ ] `import_mcp_zero.py --index --index-servers` 재실행 (멱등)
  ```bash
  uv run python scripts/import_mcp_zero.py --index --index-servers
  ```
- [ ] Phase 1 alignment 재실행 → coverage 개선 확인

---

## Phase 4: 실험 실행 전 Gate

실험 스크립트를 실행하기 전:

- [ ] `run_e0.py`가 GT-first 정렬을 사용하는지 확인 (`gt_paths` 인수 전달됨)
- [ ] `validate_pool_gt_alignment.py` 결과를 실험 결과 디렉토리에 함께 저장
- [ ] pool_size별 expected n_queries를 사전 계산해서 실험 결과 해석에 활용
  ```
  pool=5:   N GT servers, M queries
  pool=20:  N GT servers, M queries  ← 이 값들이 안정적이어야 유효한 sweep
  ```

---

## 빠른 진단 (10초)

```bash
uv run python scripts/validate_pool_gt_alignment.py \
  --pool data/raw/mcp_zero_servers.jsonl \
  --gt data/ground_truth/seed_set.jsonl data/ground_truth/mcp_atlas.jsonl
```

---

## 위반 시 조치

| 위반 | 조치 |
|-----|-----|
| covered_pct < 25% | Pool 확장 (`fetch_missing_gt_servers.py`) 또는 GT 소스 변경 |
| HIGH SKEW 경보 | GT 쿼리 다양화 또는 dominant server GT 축소 |
| pool_size별 GT set 불일치 | GT-first 정렬 확인, `gt_paths` 인수 전달 여부 확인 |
| pool filter 미적용으로 GT 생성 | `mcp_atlas.jsonl` 재생성 with `--pool-file` |

---

## 이 체크리스트가 필요한 이유

2026-04-02 발견된 문제:
- Pool: MCP-Zero 292 servers
- GT: MCP-Atlas 40 servers → pool 내 11개만 존재 (27.5%)
- 알파벳 슬라이스 `pool[:50]` = 2 GT servers → E5 sweep 전체 무효
- P@1=0.636 at pool=5 (airtable 전용 trivial test) — 성능 좋음으로 잘못 해석될 뻔

이 체크리스트를 먼저 실행했으면 30분 안에 발견했을 문제였다.
