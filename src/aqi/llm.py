"""Thin Claude wrapper used by the LLM-assisted agents (EDA narration, critic, explainer).

Every response is cached by prompt hash in the run directory, so a finished run can be replayed
exactly (AQI_REPLAY_FROM=<run_id>) without calling the API again. If no Anthropic credentials are
available the agents fall back to their rule-based behaviour and the ledger records that.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .config import ROOT
from .ledger import Ledger

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


class LLM:
    def __init__(self, cfg: dict, ledger: Ledger):
        self.cfg = cfg
        self.ledger = ledger
        self.cache_path = ledger.dir / "llm_cache.json"
        replay = os.environ.get("AQI_REPLAY_FROM")
        if replay and not self.cache_path.exists():
            src = ROOT / "runs" / replay / "llm_cache.json"
            if src.exists():
                shutil.copy(src, self.cache_path)
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}
        self._client = None
        self.disabled_reason = None if cfg.get("enabled") and anthropic else "disabled in config"

    def _client_or_none(self):
        if self.disabled_reason:
            return None
        if self._client is None:
            try:
                self._client = anthropic.Anthropic()
            except Exception as e:  # missing credentials raise at construction
                self.disabled_reason = f"no Anthropic credentials ({type(e).__name__})"
                return None
        return self._client

    def _save(self) -> None:
        self.cache_path.write_text(json.dumps(self.cache, indent=2))

    def ask(self, system: str, user: str, schema: dict | None = None) -> dict | str | None:
        """Return parsed JSON (when schema is given) or text; None when the LLM is unavailable."""
        key = hashlib.sha256(json.dumps([self.cfg.get("model"), system, user, schema]).encode()).hexdigest()
        if key in self.cache:
            return self.cache[key]
        client = self._client_or_none()
        if client is None:
            return None

        output_config = {"effort": self.cfg.get("effort", "medium")}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        try:
            response = client.beta.messages.create(
                model=self.cfg["model"],
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config=output_config,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except TypeError as e:  # the SDK raises this when no API key / auth token / profile is found
            if "authentication" not in str(e):
                raise
            self.disabled_reason = "no Anthropic credentials"
            return None
        except anthropic.AuthenticationError:
            self.disabled_reason = "Anthropic authentication failed"
            return None
        except anthropic.RateLimitError:
            self.disabled_reason = "Anthropic rate limit"
            return None
        except anthropic.APIStatusError as e:
            self.disabled_reason = f"Anthropic API error {e.status_code}"
            return None
        except anthropic.APIConnectionError:
            self.disabled_reason = "cannot reach the Anthropic API"
            return None

        if response.stop_reason == "refusal":
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        result = json.loads(text) if schema else text
        self.cache[key] = result
        self._save()
        return result
