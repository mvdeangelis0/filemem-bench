"""Token usage aggregation and rough USD estimates."""

from __future__ import annotations

from typing import Any

# On-demand list prices ($ / 1M tokens). US regional profiles may be ~+10%.
_PRICE_TABLE: list[tuple[str, float, float]] = [
    ("opus", 5.0, 25.0),
    ("sonnet", 3.0, 15.0),
    ("haiku", 1.0, 5.0),
]


def prices_for_model(model_id: str) -> tuple[float, float] | None:
    """Return (input_$/MTok, output_$/MTok) or None if unknown."""
    key = (model_id or "").casefold()
    for needle, pin, pout in _PRICE_TABLE:
        if needle in key:
            return pin, pout
    return None


def empty_usage(*, model_id: str | None = None) -> dict[str, Any]:
    return {
        "n_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "model_id": model_id,
    }


def add_bedrock_usage(bucket: dict[str, Any], usage: dict[str, Any] | None) -> None:
    """Fold a Bedrock Converse usage block into bucket."""
    if not usage:
        return
    bucket["n_calls"] = int(bucket.get("n_calls") or 0) + 1
    bucket["input_tokens"] = int(bucket.get("input_tokens") or 0) + int(
        usage.get("inputTokens") or 0
    )
    bucket["output_tokens"] = int(bucket.get("output_tokens") or 0) + int(
        usage.get("outputTokens") or 0
    )
    # Newer Converse responses may include cache stats under these keys.
    bucket["cache_read_tokens"] = int(bucket.get("cache_read_tokens") or 0) + int(
        usage.get("cacheReadInputTokens")
        or usage.get("cacheReadInputTokenCount")
        or 0
    )
    bucket["cache_write_tokens"] = int(bucket.get("cache_write_tokens") or 0) + int(
        usage.get("cacheWriteInputTokens")
        or usage.get("cacheWriteInputTokenCount")
        or 0
    )


def merge_usage(*parts: dict[str, Any] | None) -> dict[str, Any]:
    out = empty_usage()
    models: list[str] = []
    for p in parts:
        if not p:
            continue
        out["n_calls"] += int(p.get("n_calls") or 0)
        out["input_tokens"] += int(p.get("input_tokens") or 0)
        out["output_tokens"] += int(p.get("output_tokens") or 0)
        out["cache_read_tokens"] += int(p.get("cache_read_tokens") or 0)
        out["cache_write_tokens"] += int(p.get("cache_write_tokens") or 0)
        mid = p.get("model_id")
        if isinstance(mid, str) and mid and mid not in models:
            models.append(mid)
    out["model_id"] = models[0] if len(models) == 1 else (models or None)
    return out


def estimate_usd(usage: dict[str, Any], model_id: str | None = None) -> dict[str, Any]:
    mid = model_id or usage.get("model_id")
    if isinstance(mid, list):
        mid = mid[0] if mid else None
    prices = prices_for_model(str(mid or ""))
    if prices is None:
        return {
            "ok": False,
            "model_id": mid,
            "usd": None,
            "note": "no price table entry for model",
        }
    pin, pout = prices
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    usd = inp / 1e6 * pin + out / 1e6 * pout
    return {
        "ok": True,
        "model_id": mid,
        "input_usd_per_mtok": pin,
        "output_usd_per_mtok": pout,
        "usd": round(usd, 6),
        "note": "list-price estimate; ignores cache discounts and regional premiums",
    }


def usage_snapshot(llm: Any, *, role: str | None = None) -> dict[str, Any]:
    """Read usage counters from an LLM instance if present."""
    getter = getattr(llm, "usage_dict", None)
    if callable(getter):
        data = getter()
    else:
        data = empty_usage(model_id=getattr(llm, "model", None))
        data["n_calls"] = int(getattr(llm, "n_calls", 0) or 0)
    if role:
        data = dict(data)
        data["role"] = role
    return data


def build_run_usage(
    *,
    manage: dict[str, Any] | None,
    search: dict[str, Any] | None,
    llm_mode: str,
) -> dict[str, Any]:
    total = merge_usage(manage, search)
    model = None
    for part in (manage, search):
        if part and part.get("model_id"):
            model = part["model_id"]
            break
    est = estimate_usd(total, model_id=str(model) if model else None)
    return {
        "schema_version": "amb_usage_v1",
        "llm_mode": llm_mode,
        "total": total,
        "by_role": {
            "manage": manage or empty_usage(),
            "search": search or empty_usage(),
        },
        "estimate": est,
    }
