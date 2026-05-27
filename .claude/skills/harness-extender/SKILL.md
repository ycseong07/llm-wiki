---
name: harness-extender
description: Use when you detect repeated patterns or friction during work in this project (same tool calls 3+ times, repeated permission prompts, re-discovering the same workflow, user re-stating the same rule). Proposes and adds the right harness piece (skill / settings / agent / hook / command) at the minimum viable form.
---

# Harness Extender

이 프로젝트의 하네스는 최소로 시작해 필요할 때 자란다. 이 skill은 **언제 자라야 하는지 감지하고, 무엇을 어떻게 추가할지** 정한다.

CLAUDE.md `§4 Harness Evolution Policy`의 운영 매뉴얼이다.

---

## When to Use

다음 중 하나라도 만족하면 이 skill을 발동한다:

1. **반복 작업**: 같은 영역의 비슷한 작업을 3회 이상 수행했다 (예: Qdrant 컬렉션 조작, RSS 파싱, MCP 도구 정의).
2. **권한 반복**: 같은 명령 패턴으로 권한 프롬프트가 3회 이상 떴다.
3. **재발견**: 같은 디버깅 경로/검증 명령을 다시 찾고 있다.
4. **컨텍스트 비대**: 새 영역에 들어가 매번 동일한 외부 문서/API 레퍼런스를 다시 읽고 있다.
5. **사용자 반복 교정**: 사용자가 같은 규칙을 2회 이상 짚어줬다 (memory가 아닌 영구 규칙으로 승격 신호).

---

## Decision Cheat Sheet

| 신호 | 추가할 하네스 | 위치 |
|---|---|---|
| 같은 안전한 명령에 권한 프롬프트 반복 | `permissions.allow` 항목 | `.claude/settings.json` |
| 특정 영역(Qdrant/MCP/LangGraph 등)의 작업 흐름 반복 | skill 1개 | `.claude/skills/<area-name>/SKILL.md` |
| 격리된 검사/리뷰(보안 리뷰, 코드 리뷰) 위임 가능 | subagent 1개 | `.claude/agents/<agent-name>.md` |
| 사용자가 자주 호출할 명령 (예: `/ingest-now`) | slash command | `.claude/commands/<cmd>.md` |
| 매번 같은 사전/사후 행동 (예: edit 후 ruff) | hook | `.claude/settings.json` `hooks` |
| 사용자 한 명에 특화된 일회성 사실 (한 번만 의미 있음) | memory | `~/.claude/.../memory/` |
| 프로젝트 차원의 규칙 (모든 작업에 영향) | CLAUDE.md 섹션 추가 | `CLAUDE.md` |

**판단 흐름**:
```
사용자/Claude만 알면 됨?      → memory
한 시나리오 한정?              → skill
모든 작업에 영향?              → CLAUDE.md
독립 위임 가능?                → subagent
명령 단축이 핵심?              → slash command
자동 트리거가 핵심?            → hook
```

---

## How to Apply (절차)

### Step 1 — Detect
신호를 감지하면 즉시 작업을 멈추지 말고, **다음 자연스러운 종료점에서** 사용자에게 한 줄로 알린다:

> "관찰: Qdrant 컬렉션 조작이 3번째입니다. `qdrant-ops` skill 추가 어떠세요? (검색 스키마, 마이그레이션 규칙 ~20줄 예상)"

### Step 2 — Propose (Karpathy 1.1)
제안에는 항상:
- **무엇이 N회 반복됐는지** (구체 명령/패턴)
- **추가할 하네스 타입** (위 cheat sheet 기준)
- **예상 크기** (5~30줄 권장, 50줄 넘으면 분할)
- **포함할 내용 목차** (3~5 bullet)

### Step 3 — Update Existing First (Karpathy 1.3)
새 파일 만들기 전 다음을 확인:
- CLAUDE.md의 기존 섹션을 한 줄 추가로 해결할 수 있는가?
- 기존 skill에 케이스를 추가할 수 있는가?
- 기존 settings 항목을 일반화할 수 있는가?

가능하면 **항상 기존 것 갱신**을 선택한다.

### Step 4 — Write Minimal (Karpathy 1.2)
- skill: frontmatter + When to Use + 핵심 규칙/예시 1~2개. 끝.
- agent: frontmatter + 1~2문단 역할 + 안 할 일 명시.
- settings 항목: 가장 좁은 패턴 (`Bash(uv sync*)` ✓, `Bash(uv:*)`는 더 넓음 — 의도가 그럴 때만).
- hook: matcher는 구체적으로, exit 1은 진짜 차단 의도일 때만.

### Step 5 — Verify (Karpathy 1.4)
추가 후:
- 같은 패턴이 다시 나타나면 새 하네스가 잘 작동했는가?
- 다른 작업이 의도치 않게 영향받지 않았는가? (특히 hooks/permissions)
- 한 줄짜리 변경 기록을 PROJECT_PLAN.md 부록 B 의사결정 기록에 남길 가치가 있는가?

---

## Anti-Patterns (이런 경우는 추가 금지)

- "나중에 쓸 것 같아서" — Karpathy 1.2 위반.
- 한 번 본 패턴 — N=1은 신호 아님.
- 다른 프로젝트에서 본 베스트 프랙티스 — 이 프로젝트에서 마찰이 실제로 발생해야.
- everything-claude-code의 48개 agent 묶음 복제 — 필요한 1~2개만.
- 너무 일반적인 skill (예: "general-coding") — 영역 특정해야 함.
- Hook으로 강제 포맷팅 (사용자 동의 없이) — 사용자가 명시 요청할 때만.

---

## Examples for This Project

가능성 높은 후보(미리 만들지 말 것 — 신호 떴을 때만):

| 영역 | 후보 skill | 발동 신호 예 |
|---|---|---|
| Qdrant | `qdrant-ops` | 컬렉션/벡터/필터 조작 반복 |
| MCP 서버 | `mcp-tools` | MCP 도구 정의/스키마 반복 |
| LangGraph 노드 | `langgraph-nodes` | 노드 패턴/상태 정의 반복 |
| Obsidian Vault I/O | `vault-writer` | frontmatter/Markdown 템플릿 반복 |
| Tailscale/보안 | `security-review` (agent) | JWT/`tailscale serve` 노출 범위 검토 위임 가능 |
| Langfuse 트레이싱 | `langfuse-trace` | trace/score 코드 반복 |
| 평가 메트릭 | `eval-metrics` | RAGAS/임베딩 메트릭 코드 반복 |

각 항목은 **실제 마찰이 발생했을 때만** 만든다.

---

## How It Should Feel

올바로 작동하면:
- 매주 하네스가 1~2개씩 자라난다 (3개 이상이면 빠르다, 0개면 감지 실패).
- 같은 명령에 권한 프롬프트가 두 번 이상 안 뜬다.
- 사용자가 같은 규칙을 두 번 짚을 일이 없다.
- CLAUDE.md는 천천히만 두꺼워진다 — 대부분 새 내용은 skill로 격리된다.
