# llm_wiki — Obsidian Vault Candidate Discovery

> 옵시디언 볼트(2nd brain)에 쌓인 사용자 성향을 바탕으로, 외부 소스에서 후보 글 몇 개만 추려 `raw/articles/`에 클리퍼 호환 형태로 떨어뜨리는 보조 도구.
>
> **이 프로젝트는 옵시디언 볼트의 `wiki/`, `Output/`에 절대 쓰지 않는다.** raw 직전까지만 책임. ingest·합성·newsletter·blog는 옵시디언 안의 `/ingest` `/query` `/lint` 스킬이 수행.

**Last Updated**: 2026-05-28
**Owner**: Yeonchan
**Budget**: ≤$3/월 (Gemini Flash judge, 자동 실행 없음)

---

## 1. 한 줄 정체성

GeekNews → (옵시디언 wiki 기반 필터) → `raw/articles/{YYYY-MM-DD}_{slug}.md` (`ingested: false`)

자동화 정도: **수동 트리거(`uv run python scripts/discover_geeknews.py`)**. 옵시디언 쪽에서 사용자가 `/ingest` 로 결정.

---

## 2. 왜 이렇게 바뀌었나 (이전 설계와의 차이)

기존 `PROJECT_PLAN.md` (v0.1)는 RSS+Gmail 자동 수집 → 분류 → 요약 → 토픽 폴더 저장 → Qdrant 인덱싱 → FastAPI MCP RAG 였다.

문제:
1. **저장만 자동화하면 쓰레기통이 됨** (사용자 진단). 인사이트 없는 글이 무한 누적.
2. 옵시디언 볼트가 **의도 기반 wiki(entities/concepts/sources/syntheses)**로 재구축되면서 토픽 폴더(`10_Finance/`, `20_AI/`) 모델이 어긋남.
3. query는 옵시디언 내부 `/query` 스킬 + graphify가 담당 → 별도 임베딩 RAG 불필요.
4. Gmail 클리핑은 사용자 Obsidian Web Clipper가 처리 → Gmail OAuth 불필요.

해결: **이 프로젝트의 역할을 raw 후보 추천으로 한정**. 자동 저장 → 후보 추천. 외부 노출/MCP/평가 인프라 전부 제거.

---

## 3. 디렉터리 구조 (Phase 1 목표)

```
llm_wiki/
├── README.md
├── PROJECT_PLAN.md                  # 이 문서
├── CLAUDE.md                         # 행동 규칙
├── .env.example                      # OBSIDIAN_VAULT_PATH 만
├── .gitignore
├── pyproject.toml
├── uv.lock
│
├── src/
│   ├── __init__.py
│   ├── config.py                     # Vault 경로 + 소스 enable 플래그
│   ├── credentials.py                # keyring (Gemini 키 하나)
│   │
│   ├── sources/                      # 외부 수집 어댑터 (확장 단위)
│   │   ├── __init__.py
│   │   ├── base.py                   # SourceAdapter: fetch() -> list[Candidate]
│   │   └── geeknews.py               # 첫 번째 (hada.io RSS + 메타 본문 추출)
│   │
│   ├── filter/                       # 사용자 성향 기반 필터
│   │   ├── __init__.py
│   │   ├── profile.py                # wiki/index.md + concepts/ + entities/
│   │   │                             # + 나의 핵심 맥락.md + graphify-out/graph.json 로딩
│   │   ├── scorer.py                 # Gemini Flash judge 0~5점, score≥4만 통과
│   │   └── dedupe.py                 # raw/, wiki/sources/ 기존 URL/제목 중복 컷
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── gemini.py                 # generate() 공용 (메모리 [[gemini_tier1]] 규약)
│   │
│   └── pipeline/
│       ├── __init__.py
│       └── discover.py               # sources → filter → write_raw_candidates
│
├── scripts/
│   ├── setup_credentials.py          # Gemini 키 1개만
│   └── discover_geeknews.py          # 수동 실행 진입점
│
└── tests/
    └── test_geeknews_smoke.py        # fetch → 1건 raw 떨구는 스모크
```

옵시디언 볼트 (외부, 이 프로젝트는 raw/articles/ 에만 쓴다):
```
%OBSIDIAN_VAULT_PATH%/
├── raw/articles/             ← 우리가 후보 떨구는 유일한 위치
├── wiki/                     ← 읽기만. 절대 쓰지 않음
├── Output/                   ← 손대지 않음
└── graphify-out/             ← profile.py 가 읽기만
```

---

## 4. 동작 흐름 (MVP)

```
$ uv run python scripts/discover_geeknews.py

1. sources/geeknews.py
   - hada.io RSS fetch → 후보 N건
   - 각 후보의 원본 URL 추출 (메타 페이지면 본문 링크 따라가기)
   - trafilatura 본문 추출

2. filter/dedupe.py
   - raw/articles/ + wiki/sources/ 기존 URL·제목 매칭 컷

3. filter/profile.py (캐시 가능)
   - wiki/index.md, wiki/concepts/, wiki/entities/, 나의 핵심 맥락.md, graphify-out/graph.json
   - 사용자 관심 시그널: 페이지명 집합 + 태그 집합 + god nodes 가중치 + community 토픽

4. filter/scorer.py
   - 후보별: Gemini Flash judge(본문 1500자 + profile 발췌) → 0~5 점수 + 한 줄 이유
   - score ≥ 4 만 통과

5. pipeline/discover.py
   - 통과한 모든 후보를 raw/articles/{YYYY-MM-DD}_{slug}.md 작성
   - frontmatter: title, source, source_type=article, author, published, created, tags=[raw/article, clippings, discover/geeknews], ingested=false
   - 본문: 추출된 원문. 메타 페이지면 raw/CLAUDE.md 의 AUTO-APPENDED zone 규약 준수.
   - 본문 하단에 "## Discover 메모" 섹션으로 score + judge 이유 노출
   - 콘솔: "raw/articles/에 N건 저장됨. 옵시디언에서 /ingest 로 처리"
```

---

## 5. 핵심 결정 사항

| 항목 | 결정 | 이유 |
|---|---|---|
| 임계값 | **Top-N 캡 없이 score ≥ 4** | 어떤 날은 0건, 어떤 날은 5건. 쓰레기 누적보다 가뭄이 안전. |
| Profile 소스 | wiki 페이지명·태그 + 나의 핵심 맥락.md + graphify-out/graph.json (god nodes·community) | 가장 풍부한 신호. 캐시 가능하므로 비용 영향 미미. |
| 자동 실행 | **안 한다 (Phase 4까지 보류)** | "쓰레기통 안 되는가" 검증 후 결정. |
| ingest 결정 | 옵시디언 안 사용자가 `/ingest` 로 | AI 자동 wiki 편입 금지. |
| `wiki/` 쓰기 | **절대 금지** | 옵시디언 스킬의 책임. |
| 메타 페이지 | raw/CLAUDE.md AUTO-APPENDED zone 규약 따라 단일 파일 + 원문 zone | 별도 `_원문.md` 만들지 않음. |
| 비용 가드 | Gemini Flash judge 호출 후보 수 ≤ 후보 fetch 수 | 무한 루프 방지. |

---

## 6. Phase 계획

### Phase 0 — 청소 ✅ (완료)
이전 RSS/Gmail/LangGraph/Qdrant/FastAPI/Langfuse 코드 일괄 삭제. 백업 브랜치 `archive/pre-refactor` 보존. PROJECT_PLAN·CLAUDE 재작성.

### Phase 1 — GeekNews MVP
- `src/sources/base.py`, `src/sources/geeknews.py`
- `src/filter/profile.py` (캐시 포함), `src/filter/scorer.py`, `src/filter/dedupe.py`
- `src/llm/gemini.py`
- `src/pipeline/discover.py` + `scripts/discover_geeknews.py`
- `tests/test_geeknews_smoke.py`

**검증 (Karpathy 1.4)**: `discover_geeknews.py` 실행 → `raw/articles/`에 `ingested: false` 파일 1~3건 떨어짐 → 옵시디언에서 `/ingest` 정상 처리.

### Phase 2 — Gemini judge 튜닝
- score 산출 프롬프트 다듬기. 통과한 글이 실제로 사용자에게 가치 있는지 1~2주 운용하며 조정.
- 통과 사유를 frontmatter `discover_reason` 으로도 노출.
- 비용 측정 → 월 ~$1 이내 확인.

### Phase 3 — 소스 1개씩 확장
- 후보: Anthropic news / HuggingFace blog / 한국 경제지 1개.
- 한 번에 하나씩만 켠다. 각 소스 추가 후 1주 모니터링.
- `src/sources/<name>.py` + `config.py` enable 플래그 토글.

### Phase 4 (보류) — 정기 실행
- Windows Task Scheduler로 하루 1회 `discover_*.py`.
- **자동 ingest 절대 금지** — raw에만 쌓이고 사용자가 옵시디언에서 결정.
- 진입 조건: Phase 3 끝나고 "쓰레기통 안 됨" 재점검.

---

## 7. 보안 / 데이터 가드

- Tailscale/JWT/FastAPI 없음. 외부 노출 0.
- Gemini API 키는 `keyring`(Windows Credential Manager). `src/credentials.py` 단일 경로로만.
- 옵시디언 볼트 경로는 `.env` 의 `OBSIDIAN_VAULT_PATH`. 코드 하드코딩 금지.
- `raw/articles/` 외의 옵시디언 볼트 경로에 쓰기 금지(코드 레벨 가드 권장).

---

## 8. 빠른 명령어

```powershell
uv sync                                        # 의존성 설치
uv run python scripts/setup_credentials.py     # Gemini 키 1회 등록
uv run python scripts/discover_geeknews.py     # 수동 후보 추천
uv run pytest                                  # 스모크 테스트
```

---

## 부록 A: 의사결정 기록

| 일자 | 결정 | 근거 |
|---|---|---|
| 2026-05 | Claude API → Claude Pro 구독 활용 | $0 운영비 |
| 2026-05 | Ollama 제외 | 자동화 목적엔 불필요, GPU 점유 |
| 2026-05 | LangSmith → Langfuse self-host | 무료 한도 충분, 데이터 외부 비공개 |
| 2026-05 | Qdrant Cloud → Qdrant Docker | $25/월 절약 |
| 2026-05 | mTLS 제외 | Tailscale WireGuard가 단말 인증 대체 |
| 2026-05 | 수동 골든셋 → 합성+행동시그널+교차검증 | 작성 부담 제거, 다중 신호로 LLM 편향 견제 |
| 2026-05 | vLLM 제외 | 이 트래픽 규모에 오버킬 |
| 2026-05-24 | Cloudflare Tunnel/Access → Tailscale 전환 | 단일 사용자엔 공개 노출 불필요; 도메인 비용 없이 $0 |
| 2026-05-26 | Gemini Free → Tier 1 + `gemini-2.5-flash` | 한국 리전+신규 GCP는 무료 limit:0; 2.0-flash는 신규 차단. Tier 1 pay-as-you-go |
| 2026-05-27 | 본문 추출(trafilatura) 도입 | RSS summary 비어있는 경우 다수 (HuggingFace 등) |
| 2026-05-27 | 링크 확장 + 통합 요약 | "이미 요약된 콘텐츠를 또 요약" 정보 손실 구조 회피 |
| **2026-05-28** | **옵시디언 의도 기반 wiki로 전환. 이 프로젝트는 raw 후보 추천 도구로 축소.** | 자동 수집·저장 모델이 "쓰레기통" 문제. 옵시디언 안 `/ingest`·`/query`·`/lint` 스킬 + graphify가 wiki/Output 책임. 이 프로젝트는 raw/articles/ 직전까지만. Qdrant/FastAPI/MCP/Langfuse/Gmail/Tailscale 전부 제거. |
| **2026-05-28** | **임계값 정책 = score ≥ 4 (Top-N 캡 없음)** | 어떤 날은 0건이 자연스러움. 무리한 통과보다 가뭄이 안전. |
| **2026-05-28** | **Profile = wiki + 나의 핵심 맥락.md + graphify-out/graph.json** | 가장 풍부한 신호. graphify의 god nodes·community 가중치 활용 가능. |

---

## 부록 B: 이전 설계 보관

기존 v0.1 (RSS+Gmail 자동 수집 → Qdrant RAG → MCP) 코드와 명세는 `archive/pre-refactor` 브랜치에 보존. 필요 시 참조.
