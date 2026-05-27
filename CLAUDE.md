# CLAUDE.md — llm_wiki (Obsidian Vault Candidate Discovery)

이 파일은 이 저장소에서 Claude Code가 따라야 할 규칙을 정의한다. 모든 세션 시작 시 자동 로드된다.

상세 프로젝트 명세는 [PROJECT_PLAN.md](./PROJECT_PLAN.md) 참조. 이 파일은 **사용자 맥락 + Claude의 행동 규칙**을 다룬다. 자기 인터뷰 기반 전체 맥락은 옵시디언 볼트의 `나의 핵심 맥락.md` (경로는 `OBSIDIAN_VAULT_PATH/나의 핵심 맥락.md`).

---

## 나는 누구인가

- 이름: Yeonchan Seong (`ycseong07@gmail.com`)
- 하는 일: **4년차 의료 AI 엔지니어** (스타트업 경험 위주). 사회학과 졸업.
- 핵심 가치:
  - **"정말 안다 = 전혀 모르는 사람에게 쉽게 설명할 수 있다."** → 깊이가 선행되어야 함.
  - 사용자 편의 · 구조 효율 · 완성도 우선. 판매·트래픽 극대화는 후순위.
  - 광고 떡칠 · 그로스해킹 · 중독 설계 ❌.

## 나의 역할들

- **의료 AI 엔지니어 (본업)** — ML/DL 모델링, LLM 서비스 개발·출시. 의료 도메인에 갇히고 싶지 않음.
- **풀스택/백엔드 개발자** — Python · FastAPI 기반 서빙, 하네스 엔지니어링, 클라우드 인프라 학습 중.
- **블로거 / 1인 개발자 지망** — wiki 기반 실전 튜토리얼 · 원리 분석 글 발행. 1인 개발 제품으로 가치 전달 지향.
- 관심 도메인: AI(메인), 경제·금융, 국제정세, 사회.

## 나의 비전과 목표

- 장기 비전: **경제적 자유를 갖춘 1인 개발자 / 디지털 노마드**.
- llm_wiki 4가지 산출: ① 매일 아침 **나만의 뉴스레터** ② wiki 기반 **블로그 작성 시스템** ③ **나의 사고방식 문서** ④ **Claude CLI ↔ wiki 연동**.
- 1년 KPI(유연): 블로그 **월 2편**, llm_wiki **월 1커밋 이상**. 점진적 개선 우선, strict 금지.
- 타겟 독자: ① 비슷한 연차의 AI/데이터 엔지니어 ② 미래의 나.

## AI에게 기대하는 것

1. **깊이 우선** — 표면 요약 ❌. 원리 · 근거 · 1차 자료까지 함께 제시.
2. **도메인 연결 시도** — 의료 외(금융 · 경제 · 사회학 · 일반 ML)를 의료에 가져올 때 **데이터 구조 차이**까지 함께 검토.
3. **추구미 정렬** — 0→1 새 구현보다 **근본 원인 분석 / 구조 개선 / 완성도 향상** 제안을 우선.
4. **반대 패턴 차단** — 그로스해킹 · 광고 의존 · 중독 설계 제안 ❌.
5. **사고방식 축적** — 사용자가 던지는 깨달음/인사이트를 사고방식 문서에 편입 가능한 형태로 정리.
6. **블로그 톤** — 동료 엔지니어 + 미래의 나가 읽는다는 가정. 전문성 있되, 1차 자료 부족으로 막힌 지점을 채워주는 글을 함께 설계.

## 작업 규칙

- **언어**: 한국어. 코드 · 식별자 · 공식 문서 인용은 영어 그대로.
- **톤**: 간결, 핵심만. 불필요한 머리말·후미 요약 금지. 사실은 직설적으로.
- **결과물 형태**: 코드는 Karpathy 4원칙(§1) 준수. 글은 **실전 튜토리얼 + 원리 분석** 위주, 가끔 회고/에세이.
- **세부 코딩 · 보안 · 환경 규칙**: 아래 §0 ~ §6 참조.

---

## 0. 프로젝트 한 줄 요약

옵시디언 볼트(2nd brain)에 쌓인 사용자 성향을 기반으로 외부 소스(처음엔 GeekNews)에서 후보를 추려 `raw/articles/`에 클리퍼 호환 형태로 떨어뜨리는 **수동 트리거** 보조 도구.
스택: **Python (uv) + feedparser + trafilatura + google-genai (Gemini Flash judge) + keyring**.
운영 비용 **≤$3/월** (Gemini judge만). 외부 노출 0 (FastAPI/MCP/Tailscale/JWT 모두 없음).

**중요 경계**: 이 프로젝트는 옵시디언 볼트의 `raw/articles/` 에만 쓴다. `wiki/`, `Output/`, 다른 raw 하위 폴더에는 **절대 쓰지 않는다**. ingest·합성·newsletter/blog는 옵시디언 안의 `/ingest` `/query` `/lint` 스킬이 수행.

---

## 1. 코딩 4원칙 (Karpathy)

이 4가지가 **다른 모든 규칙보다 우선**한다. 자세한 설명은 `/karpathy-guidelines` 또는 `.claude/skills/karpathy-guidelines/SKILL.md` 참조.

### 1.1 Think Before Coding — 가정하지 말고, 혼란을 숨기지 말고, 트레이드오프를 드러내라
- 구현 전에 가정을 명시한다. 불확실하면 묻는다.
- 해석이 여러 갈래면 제시한다. 조용히 고르지 않는다.
- 더 단순한 방법이 있으면 말한다. 정당하면 푸시백한다.
- 불분명하면 멈춘다. 무엇이 헷갈리는지 말하고 묻는다.

### 1.2 Simplicity First — 문제를 푸는 최소 코드만. 투기적 코드 금지
- 요청 범위를 넘는 기능 추가 금지.
- 일회성 코드에 추상화 금지.
- 요청 안 한 "유연성/설정 가능성" 추가 금지.
- 일어날 수 없는 시나리오에 대한 에러 핸들링 금지.
- 200줄로 짠 게 50줄로 가능하면 다시 짠다.

### 1.3 Surgical Changes — 손대야 할 것만 손댄다. 본인이 만든 것만 치운다
- 인접한 코드/주석/포맷을 "개선"하지 않는다.
- 안 망가진 걸 리팩터링하지 않는다.
- 기존 스타일이 본인 취향과 달라도 매치한다.
- 무관한 데드 코드는 발견해도 **언급만** 하고 지우지 않는다.
- 본인 변경으로 생긴 고아(미사용 import/변수)만 정리한다.
- **테스트**: 변경된 모든 줄이 사용자 요청에 직접 연결되는가?

### 1.4 Goal-Driven Execution — 성공 기준을 정의하고 검증까지 루프
- 명령형 작업을 검증 가능한 목표로 변환한다.
  - "validation 추가" → "잘못된 입력에 대한 테스트 작성 → 통과시킨다"
  - "버그 고쳐" → "버그 재현하는 테스트 작성 → 통과시킨다"
- 다단계 작업은 `1. [단계] → verify: [확인방법]` 형태로 짧게 계획.

---

## 2. 프로젝트별 작업 가드

### 2.1 환경
- **개발/운영 모두 Windows 11** (PowerShell 5.1 기본). Bash도 Bash 툴로 사용 가능.
- **수동 트리거**: `uv run python scripts/discover_*.py`. 자동 스케줄러 없음 (Phase 4까지 보류).
- 디렉터리 구조는 `PROJECT_PLAN.md §3` 따른다. **임의로 디렉터리 만들기 금지** (Karpathy 1.2).
- 옵시디언 볼트 경로는 `OBSIDIAN_VAULT_PATH` 환경변수만 통해 접근. 코드 하드코딩 금지.

### 2.2 PowerShell 주의 (Windows 5.1)
- `&&` / `||` 없음 → `A; if ($?) { B }`
- `?:` `??` `?.` 없음 → `if/else`
- 네이티브 exe에 `2>&1` 금지 (stderr가 ErrorRecord로 래핑됨)
- 파일 작성은 `-Encoding utf8` 명시 (기본은 UTF-16 LE BOM)
- 가능한 한 전용 도구(Read/Edit/Write/Grep/Glob) 사용, Bash/PowerShell은 쉘 전용 작업에만.

### 2.3 Python 환경
- 패키지 매니저: **`uv` 고정**. `pip` 직접 사용 금지 (`uv pip ...`은 OK).
- 가상환경/락 파일은 `uv`가 관리 → 임의로 `requirements.txt`, `setup.py` 만들지 않는다.
- Python 코드 실행: `uv run python ...` 또는 `uv run <script>`.

### 2.4 보안 — 절대 금지 (Must Never)
- `.env`, API 키 등을 **코드/주석/로그/커밋**에 평문 노출하지 않는다.
- 비밀은 **`keyring` 라이브러리 + Windows Credential Manager**로 조회 (`src/credentials.py` 단일 경로).
- Phase 1~4 동안 외부 노출 없음 (FastAPI/MCP 코드 없음). Phase 5(먼 미래 — Mac에서 옵시디언 볼트 read-only query)에서만 Tailscale tailnet HTTPS 경유로 노출. 공개 인터넷 직접 바인딩 영구 금지.
- 위험 git 명령(`push --force`, `reset --hard`, `clean -f`, `branch -D`, `--no-verify`)은 사용자가 **명시 요청**할 때만.

### 2.5 옵시디언 볼트 가드 (가장 중요)
- 옵시디언 볼트의 **`raw/articles/` 외 경로에 쓰기 금지**. `wiki/`, `Output/`, 다른 raw 하위 폴더, `graphify-out/`, 클리퍼 JSON 7개는 **모두 읽기만**.
- raw 파일에 쓸 때는 옵시디언 `raw/CLAUDE.md` 규약 준수 (frontmatter `ingested: false`, 메타 페이지면 AUTO-APPENDED zone 사용, 별도 `_원문.md` 만들지 않음).
- `wiki/` 페이지는 절대 새로 만들거나 수정하지 않는다. 그건 옵시디언 내부 `/ingest` 스킬의 책임.
- 사용자 클리핑 본문은 절대 수정하지 않는다.
- 디렉터리 구조 변경, 파일 이동/삭제, frontmatter 임의 수정 금지.

### 2.6 의존성 추가
- 새 의존성은 `PROJECT_PLAN.md`의 목적과 부합해야 한다.
- 제외 목록(LangSmith, Qdrant, vLLM, Ollama, FastAPI, MCP, Langfuse, LangGraph, Tailscale, JWT, Gmail API)에 있는 걸 다시 도입하려면 **PROJECT_PLAN.md 부록 A 의사결정 로그 갱신**하고 이유를 적는다.
- 무거운 의존성(>50MB) 추가는 사용자 확인 받는다.

---

## 3. 테스트 정책

Karpathy 정신: **필요할 때 더한다**. 강제 커버리지 목표 없음.

**필수로 테스트를 쓰는 경우**:
1. 버그 수정 — 먼저 재현 테스트를 쓰고 통과시킨다 (Karpathy 1.4).
2. 회귀가 명확히 위험한 변경 — 검증 케이스를 남긴다.
3. 옵시디언 볼트 쓰기 경로 — `raw/articles/` 외 위치에 쓰지 않음을 보장하는 경계 테스트.

그 외에는 사용자가 요구할 때만. 투기적 테스트 작성 금지.

---

## 4. Harness Evolution Policy (자동 하네스 추가)

이 프로젝트의 하네스는 **최소로 시작해서, 필요할 때 자라난다**. Claude는 작업 중 다음을 **자가 모니터링**한다:

### 4.1 트리거 — 언제 하네스 추가를 제안하는가
- 같은 유형의 작업을 **세 번 이상** 반복 (예: RSS 피드 파싱, 옵시디언 wiki 페이지 로딩).
- 권한 프롬프트가 **같은 패턴**으로 반복해서 뜸 (→ settings.json 확장).
- 디버깅에 같은 명령/검증 흐름을 **재발견**하고 있음.
- 새 영역(예: graphify 그래프 JSON, trafilatura 옵션)에 들어가서 매번 같은 문서를 다시 봄.
- 사용자가 같은 코딩 규칙을 **두 번 이상** 짚어줌 → memory가 아닌 skill/CLAUDE.md로 승격.

### 4.2 대응 — 무엇을 어떻게 추가하는가
세부 절차와 cheat sheet는 `/harness-extender` 또는 `.claude/skills/harness-extender/SKILL.md` 참조.

요약:
| 패턴 | 추가할 하네스 |
|---|---|
| 같은 명령 반복 + 권한 프롬프트 | `.claude/settings.json` allow 항목 |
| 영역별 작업 흐름 반복 (예: source 어댑터 작성, profile 캐시) | `.claude/skills/<area>/SKILL.md` |
| 위임 가능한 독립 작업 (예: 코드리뷰, 옵시디언 볼트 쓰기 경계 검증) | `.claude/agents/<agent>.md` |
| 자동 트리거가 필요한 행동 | `.claude/settings.json`의 hooks |
| 사용자가 자주 호출하는 슬래시 명령 | `.claude/commands/<cmd>.md` |

### 4.3 절차 — 추가 시 따르는 규칙 (Karpathy 1.2/1.3 적용)
1. **제안 먼저** — Claude가 임의로 만들지 않는다. "이 패턴이 N회 반복됨, X 하네스 추가 어떠세요?" 로 제안.
2. **최소 형태** — 처음에는 5~30줄짜리 SKILL.md 하나면 충분. 미래의 시나리오 대비 금지.
3. **기존 것 먼저 갱신** — 새 파일 만들기 전에, CLAUDE.md나 기존 skill을 확장할 수 있는지 본다.
4. **사용자 승인 후 추가** — 사용자가 OK 한 다음 commit-ready 형태로 만든다.

---

## 5. Must Always / Must Never (요약)

### Must Always
- 작업 전 가정을 1~2줄로 명시 (Karpathy 1.1).
- 다단계 작업은 짧은 plan을 먼저 보여주고 실행.
- 의존성/구조 변경은 `PROJECT_PLAN.md` 부록 A 의사결정 기록과 충돌하지 않는지 확인.
- 새 파일 만들기 전에 기존 파일 수정 가능성을 먼저 확인.
- 비밀은 keyring 경유로만 로드.
- 옵시디언 볼트에 쓸 때는 `raw/articles/` 경로임을 코드로 검증.

### Must Never
- 요청 범위 밖 "개선" (포맷, 리네이밍, 무관한 리팩토링).
- `.env` / API 키를 코드/로그/커밋에 노출.
- 옵시디언 볼트의 `raw/articles/` 외 경로에 쓰기 (특히 `wiki/`, `Output/`, `graphify-out/`).
- 사용자 클리핑 본문 수정. `ingested` 외 frontmatter 임의 변경.
- Phase 5 외 외부 노출용 서버(FastAPI, MCP, HTTP listener) 추가, 또는 Phase 5 MCP에 쓰기 도구 노출 — 별도 의사결정 필요.
- 사용자 명시 없이 위험 git 명령 실행 (`--force`, `--hard`, `--no-verify`, `-D` 등).

---

## 6. 빠른 명령어 참조

```powershell
uv sync                                          # 의존성 설치
uv run python scripts/setup_credentials.py       # Gemini 키 1회 등록
uv run python scripts/discover_geeknews.py       # 수동 후보 추천 (Phase 1+)
uv run pytest                                    # 스모크 테스트
```

---

**이 규칙이 작동하면**: diff에 요청 외 변경이 줄어들고, 같은 실수를 반복하지 않고, 하네스가 천천히 두꺼워진다.
