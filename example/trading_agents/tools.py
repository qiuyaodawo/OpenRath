"""Real market data tools (no fabricated quotes)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from rath.flow.tool import FlowToolCall
from rath.session.session import Session

_ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"


class GlobalQuoteInput(BaseModel):
    symbol: str = Field(
        description="US equity ticker symbol, e.g. NVDA, AAPL.",
        min_length=1,
        max_length=16,
    )


class AlphaVantageGlobalQuoteTool(FlowToolCall):
    """Alpha Vantage ``GLOBAL_QUOTE`` over HTTPS."""

    @property
    def name(self) -> str:
        return "alpha_vantage_global_quote"

    @property
    def description(self) -> str | None:
        return (
            "Retrieve latest Global Quote for a US symbol from Alpha Vantage. "
            "Requires ALPHA_VANTAGE_API_KEY in the environment."
        )

    @property
    def parameters(self) -> Mapping[str, Any]:
        return dict(GlobalQuoteInput.model_json_schema())

    def __call__(
        self,
        session: Session,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        del session

        data = dict(arguments or {})
        model = GlobalQuoteInput.model_validate(data)
        symbol = model.symbol.strip().upper()
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "PW2FBNP02JA924O9").strip()
        if not api_key:
            return {
                "ok": False,
                "error": "ALPHA_VANTAGE_API_KEY is not set",
            }

        params = urllib.parse.urlencode(
            {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": api_key,
            }
        )
        url = f"{_ALPHAVANTAGE_URL}?{params}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:4000]
            return {
                "ok": False,
                "http_status": exc.code,
                "error": body,
            }
        except OSError as exc:
            return {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": "non-JSON response",
                "raw_preview": raw[:2000],
            }

        if isinstance(parsed, dict) and "Note" in parsed:
            return {
                "ok": False,
                "error": "alpha_vantage_rate_limit_or_note",
                "detail": parsed.get("Note"),
            }
        if isinstance(parsed, dict) and "Error Message" in parsed:
            return {
                "ok": False,
                "error": str(parsed.get("Error Message")),
            }

        quote = None
        if isinstance(parsed, dict):
            quote = parsed.get("Global Quote")
        return {
            "ok": True,
            "symbol": symbol,
            "global_quote": quote,
            "raw_keys": list(parsed.keys()) if isinstance(parsed, dict) else None,
        }
