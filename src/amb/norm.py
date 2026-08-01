"""Normalization helpers (AMB-DD-05 norm_v1)."""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+", re.UNICODE)


def norm_v1(text: str | None, *, for_answer: bool = False) -> str:
    if text is None:
        return ""
    s = text.encode("utf-8", errors="replace").decode("utf-8")
    s = unicodedata.normalize("NFKC", s)
    s = s.casefold()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _WS.sub(" ", s).strip()
    if for_answer:
        s = s.strip(".,;:!?\"'")
    return s
