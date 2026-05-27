"""Per-candidate Gemini judge. Pass-through threshold is fixed at SCORE_THRESHOLD.

Memory [[discovery-threshold-policy]]: do NOT lower the threshold to pad results.
A zero-result run is the expected outcome on some days.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.filter.profile import Profile
from src.llm import gemini
from src.sources.base import Candidate

SCORE_THRESHOLD = 4
BODY_CHARS_FOR_JUDGE = 1500

_SYSTEM = """\
너는 사용자의 옵시디언 2nd brain을 보호하는 큐레이터다. 외부 글이 사용자의 wiki에
편입될 가치가 있는지 0~5로 평가하고 한 줄 이유를 적어라.

평가 기준 (사용자 핵심 맥락·위키 인덱스·지식 그래프를 모두 고려):
- 5: 사용자 본업/사이드 프로젝트/사고방식에 직접 활용 가능. 즉시 wiki에 추가할 만함.
- 4: 사용자가 다루는 토픽에 깊이를 더하거나 새 각도를 제공. wiki 추가 의미 있음.
- 3: 흥미로우나 표면 정보. wiki 편입할 정도의 깊이/관련성은 아님.
- 2: 사용자 관심 영역 근처지만 활용도 낮음.
- 1: 사용자 관심사와 거의 무관.
- 0: 잘못된 후보 (스팸/광고/오염 등).

원칙:
- 표면 요약 글, 단순 트렌드 나열, 광고성 글, 그로스해킹은 감점.
- 1차 자료(논문/구현 리포트/원리 분석), 깊은 회고, 도메인 연결 글은 가점.
- "재미있어 보임"만으로 4점 이상 주지 말 것. 사용자 토픽과의 직접 연결 근거가 있어야 함.
- 사용자가 그로스해킹·중독 설계·광고 의존을 반대한다는 점을 존중.

이유는 한국어 한 줄(최대 80자). 점수 근거를 구체적으로(예: "wiki의 X 페이지/태그와 직접 연결, 깊이 있음").
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 5},
        "reason": {"type": "string"},
    },
    "required": ["score", "reason"],
}


@dataclass
class ScoreResult:
    score: int
    reason: str


def _build_user_prompt(profile: Profile, candidate: Candidate) -> str:
    body = (candidate.body or candidate.summary or "")[:BODY_CHARS_FOR_JUDGE]
    return (
        profile.as_prompt_block()
        + "\n\n---\n\n## 평가 대상 후보\n"
        + f"- 제목: {candidate.title}\n"
        + f"- 출처: {candidate.source} ({candidate.source_url})\n"
        + (f"- 원본 URL: {candidate.original_url}\n" if candidate.original_url else "")
        + f"\n### 본문 발췌 (최대 {BODY_CHARS_FOR_JUDGE}자)\n{body}\n"
    )


def score(candidate: Candidate, profile: Profile) -> ScoreResult:
    prompt = _build_user_prompt(profile, candidate)
    try:
        data = gemini.generate_json(prompt, _SCHEMA, system=_SYSTEM)
    except Exception as e:
        return ScoreResult(score=0, reason=f"judge_error: {e!r}")
    raw_score = data.get("score", 0)
    try:
        s = max(0, min(5, int(raw_score)))
    except (TypeError, ValueError):
        s = 0
    reason = str(data.get("reason", "")).strip()[:200]
    return ScoreResult(score=s, reason=reason)


def passes(result: ScoreResult) -> bool:
    return result.score >= SCORE_THRESHOLD
