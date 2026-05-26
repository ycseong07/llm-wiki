"""Retroactively add `tags:` frontmatter to existing vault .md files.

For each file without tags (or empty tags):
  1. Call Gemini once for keyword extraction (3~5 tags).
  2. Insert/replace `tags:` in the YAML frontmatter (preserving other fields and body).
  3. Re-index the file into Qdrant so the new tags become searchable.

Idempotent — files that already have non-empty tags are skipped.
Skips vault/00_Daily/ (digest files don't need entry-level tags).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from src.agents.nodes._gemini import generate  # noqa: E402
from src.config import VAULT_PATH  # noqa: E402
from src.index.indexer import index_file  # noqa: E402

_PROMPT = """다음 콘텐츠의 핵심 키워드/엔티티 3~5개를 추출하라. 고유명사·기술용어·회사명·인명 우선, 일반 명사 지양. 한·영 혼용 가능.

JSON으로만 응답 (다른 텍스트 금지):
{{"tags": ["키워드1", "키워드2", "키워드3"]}}

제목: {title}
본문:
{body}
"""

_FRONTMATTER_ORDER = ["source", "url", "category", "published"]


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2]


def _format_frontmatter(meta: dict) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for k in _FRONTMATTER_ORDER:
        if k in meta:
            lines.append(f"{k}: {meta[k]}")
            seen.add(k)
    for k, v in meta.items():
        if k in seen or k == "tags":
            continue
        lines.append(f"{k}: {v}")
    tags = meta.get("tags") or []
    if isinstance(tags, list) and tags:
        quoted = ", ".join(f"\"{t}\"" for t in tags)
        lines.append(f"tags: [{quoted}]")
    else:
        lines.append("tags: []")
    return "---\n" + "\n".join(lines) + "\n---\n"


def _extract_title(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _safe_json(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip("` \n")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {}


def main() -> int:
    md_files = [
        p
        for p in VAULT_PATH.rglob("*.md")
        if not p.name.startswith(".") and "00_Daily" not in p.parts
    ]
    print(f"Scanning {len(md_files)} files in {VAULT_PATH}")

    processed = 0
    skipped_has_tags = 0
    skipped_error = 0

    for path in md_files:
        raw = path.read_text(encoding="utf-8")
        meta, rest = _split_frontmatter(raw)
        existing = meta.get("tags")
        if isinstance(existing, list) and existing:
            skipped_has_tags += 1
            continue

        body = rest.lstrip("\n")
        title = _extract_title(body)
        try:
            response = generate(_PROMPT.format(title=title, body=body[:4000]))
            parsed = _safe_json(response)
            tags = parsed.get("tags") or []
            if not isinstance(tags, list) or not tags:
                print(f"  skip (no tags returned): {path.name}")
                skipped_error += 1
                continue
            tags = [str(t).strip() for t in tags if str(t).strip()][:8]
        except Exception as e:
            print(f"  error: {path.name}  {e!r}")
            skipped_error += 1
            continue

        meta["tags"] = tags
        new_content = _format_frontmatter(meta) + "\n" + body.lstrip("\n")
        path.write_text(new_content, encoding="utf-8")
        index_file(path)
        processed += 1
        print(f"  ok: {path.name}  tags={tags}")

    print(f"\nProcessed {processed}, skipped(has_tags) {skipped_has_tags}, skipped(error) {skipped_error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
