"""Parse agent markdown output into structured sections + confidence tally."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


_HC_RE  = re.compile(r"\[HIGH CONFIDENCE\]", re.IGNORECASE)
_MC_RE  = re.compile(r"\[MEDIUM CONFIDENCE\]", re.IGNORECASE)
_LC_RE  = re.compile(r"\[LOW CONFIDENCE(?:\s*/?\s*INFERRED)?\]", re.IGNORECASE)
_GAP_RE = re.compile(r"\[INSUFFICIENT DATA[^\]]*\]", re.IGNORECASE)

_H2_RE  = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

_EXEC_HINTS = ("executive summary", "summary", "tl;dr", "tldr", "headline")


@dataclass
class Tally:
    hc: int = 0
    mc: int = 0
    lc: int = 0
    gap: int = 0

    def add(self, other: "Tally") -> None:
        self.hc += other.hc
        self.mc += other.mc
        self.lc += other.lc
        self.gap += other.gap

    def is_empty(self) -> bool:
        return not (self.hc or self.mc or self.lc or self.gap)


@dataclass
class Section:
    title: str
    body: str
    tally: Tally = field(default_factory=Tally)


@dataclass
class ParsedOutput:
    exec_summary: Optional[str]
    sections: list[Section]
    total: Tally
    raw: str


def _tally_for(text: str) -> Tally:
    return Tally(
        hc=len(_HC_RE.findall(text)),
        mc=len(_MC_RE.findall(text)),
        lc=len(_LC_RE.findall(text)),
        gap=len(_GAP_RE.findall(text)),
    )


def _looks_like_exec_summary(title: str) -> bool:
    t = title.strip().lower().lstrip("0123456789. )-")
    return any(hint in t for hint in _EXEC_HINTS)


def _first_paragraph(text: str, limit: int = 480) -> str:
    """Pull the first non-empty paragraph as a fallback exec summary."""
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("#"):
            continue
        clean = re.sub(r"\s+", " ", chunk)
        if len(clean) > limit:
            clean = clean[:limit].rsplit(" ", 1)[0] + "…"
        return clean
    return ""


def parse_output(markdown: str) -> ParsedOutput:
    """Split agent output by H2 headers; extract exec summary + tallies."""
    text = (markdown or "").strip()
    if not text:
        return ParsedOutput(exec_summary=None, sections=[], total=Tally(), raw=text)

    matches = list(_H2_RE.finditer(text))
    sections: list[Section] = []

    if not matches:
        sections.append(Section(title="Output", body=text, tally=_tally_for(text)))
    else:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(Section(title="Sources Evaluated", body=preamble, tally=_tally_for(preamble)))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end():end].strip()
            sections.append(Section(title=m.group(1).strip(), body=body, tally=_tally_for(body)))

    exec_summary: Optional[str] = None
    exec_tally = Tally()
    remaining: list[Section] = []
    for s in sections:
        if exec_summary is None and _looks_like_exec_summary(s.title):
            exec_summary = s.body
            exec_tally = s.tally
            continue
        remaining.append(s)

    if exec_summary is None and remaining:
        exec_summary = _first_paragraph(remaining[0].body) or None

    total = Tally()
    total.add(exec_tally)
    for s in remaining:
        total.add(s.tally)

    return ParsedOutput(exec_summary=exec_summary, sections=remaining, total=total, raw=text)
