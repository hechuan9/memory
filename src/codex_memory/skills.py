from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence


def write_skill_candidate(
    *,
    output_dir: str | Path,
    title: str,
    slug: str,
    applies_when: str,
    triggers: Sequence[str],
    steps: Sequence[str],
    counterexamples: Sequence[str],
    evidence: str,
    suggested_install_path: str | Path,
) -> Path:
    safe_slug = _safe_slug(slug)
    target_dir = Path(output_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{safe_slug}.md"
    content = _render_skill_candidate(
        title=title,
        applies_when=applies_when,
        triggers=triggers,
        steps=steps,
        counterexamples=counterexamples,
        evidence=evidence,
        suggested_install_path=str(suggested_install_path),
    )
    path.write_text(content, encoding="utf-8")
    return path


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("slug cannot be empty")
    return slug


def _render_skill_candidate(
    *,
    title: str,
    applies_when: str,
    triggers: Sequence[str],
    steps: Sequence[str],
    counterexamples: Sequence[str],
    evidence: str,
    suggested_install_path: str,
) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            "## 适用场景",
            applies_when.strip(),
            "",
            "## 触发条件",
            *[f"- {item}" for item in triggers],
            "",
            "## 建议步骤",
            *[f"- {item}" for item in steps],
            "",
            "## 反例",
            *[f"- {item}" for item in counterexamples],
            "",
            "## 证据摘要",
            evidence.strip(),
            "",
            "## 建议安装位置",
            suggested_install_path,
            "",
            "## 状态",
            "候选草稿；需要人工审核后才能安装或改写现有 skill。",
            "",
        ]
    )
