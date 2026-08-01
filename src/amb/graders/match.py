from __future__ import annotations

import re
from typing import Any

from amb.norm import norm_v1


def match_text(corpus: str, match: dict[str, Any]) -> tuple[bool, str | None]:
    mode = match.get("mode", "normalized_any")
    if mode == "normalized_any":
        c = norm_v1(corpus)
        for form in match.get("forms_any") or []:
            f = norm_v1(form)
            if f and f in c:
                return True, form
        return False, None
    if mode == "normalized_all":
        c = norm_v1(corpus)
        for form in match.get("forms_all") or []:
            f = norm_v1(form)
            if not f or f not in c:
                return False, None
        return True, "all"
    if mode == "absent_normalized_any":
        c = norm_v1(corpus)
        for form in match.get("forms_any") or []:
            f = norm_v1(form)
            if f and f in c:
                return False, form
        return True, None
    if mode == "regex_any":
        flags = re.MULTILINE | re.IGNORECASE
        for pat in match.get("regex_any") or []:
            if re.search(pat, corpus, flags):
                return True, pat
        return False, None
    raise ValueError(f"unknown match mode {mode}")
