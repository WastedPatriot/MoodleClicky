"""Every explanation is appended to a dated Markdown file, so you can revise from it later."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from moodleclicky.brain import Explanation
from moodleclicky.config import data_dir


def notes_dir() -> Path:
    d = data_dir() / "notes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def to_markdown(exp: Explanation, question: str, mode: str, when: datetime) -> str:
    out = [f"## {when:%H:%M} - {exp.title}", f"*Mode: {mode}*", ""]
    if question:
        out += [f"**You asked:** {question}", ""]
    if exp.summary:
        out += [f"**What it's asking:** {exp.summary}", ""]
    for i, s in enumerate(exp.steps, 1):
        out.append(f"{i}. {s.text}")
    if exp.steps:
        out.append("")
    if exp.answer:
        out += ["**Answer:**", "", exp.answer, ""]
    if exp.why:
        out += [f"**Why it works:** {exp.why}", ""]
    if exp.check_yourself:
        out += [f"**Check yourself:** {exp.check_yourself}", ""]
    return "\n".join(out) + "\n"


def save(exp: Explanation, question: str, mode: str, when: datetime | None = None) -> Path | None:
    if exp.error:
        return None
    when = when or datetime.now()
    path = notes_dir() / f"{when:%Y-%m-%d}.md"
    first = not path.exists()
    with path.open("a", encoding="utf-8") as f:
        if first:
            f.write(f"# MoodleClicky notes - {when:%A %d %B %Y}\n\n")
        f.write(to_markdown(exp, question, mode, when))
    return path
