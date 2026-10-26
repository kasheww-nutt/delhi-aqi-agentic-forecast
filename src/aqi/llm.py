"""LLM access for the LLM-assisted agents (schema mapping, EDA notes, critic, explainer).

Two backends:
  * `cli` (default) — the coding-agent CLIs already installed and logged in on this machine
    (Claude Code, Gemini CLI, Codex, agy), run headless. Uses the user's subscriptions; no API bill.
    Tried in the configured order; the next one is used when one fails or hits its usage limit.
  * `api` — the Anthropic API (needs ANTHROPIC_API_KEY).

Every answer is cached by prompt hash in the run directory, so a finished run can be replayed exactly
(AQI_REPLAY_FROM=<run_id>) without calling any LLM again. When no backend answers, the agents fall back
to their rule-based behaviour and the ledger records why.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .config import ROOT
from .ledger import Ledger

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

# The prompt goes in on stdin wherever the CLI reads it, because on Windows `claude` and `gemini` are
# .cmd shims and cmd.exe would re-parse quotes and symbols in arguments. agy reads no stdin; it is a
# real .exe, so its prompt is passed as one argument (quoted by CreateProcess, not re-parsed by cmd).
CLI_FLAGS = {
    "claude": lambda schema, out, web, prompt: ["-p", "--output-format", "json"]
                                               + (["--allowedTools", "WebSearch", "WebFetch"] if web else []),
    "gemini": lambda schema, out, web, prompt: ["-p", "Answer the request given on standard input.", "-o", "json",
                                                "--approval-mode", "plan"],
    "codex": lambda schema, out, web, prompt: ["exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                                               "-o", out] + (["--output-schema", schema] if schema else []) + ["-"],
    "agy": lambda schema, out, web, prompt: ["--output-format", "json", "--mode", "plan"]
                                            + (["--json-schema", schema] if schema else []) + [f"-p={prompt}"],
}
STDIN_PROMPT = {"claude", "gemini", "codex"}
CLI_TIMEOUT = 240  # seconds per call
LIMIT_HINTS = ("rate limit", "usage limit", "quota", "limit reached", "too many requests", "429")


def _extract_json(text: str):
    """The first JSON object in a reply (CLIs may wrap it in prose or a ``` fence)."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    return json.loads(text[start:end + 1])


def _reply_text(name: str, stdout: str, out_file: Path) -> str:
    if name == "codex":
        return out_file.read_text(encoding="utf-8") if out_file.exists() else stdout
    env = None
    for chunk in [stdout] + [ln for ln in reversed(stdout.splitlines()) if ln.lstrip().startswith("{")]:
        try:  # the whole output, else the last JSON line (some CLIs print warnings before it)
            env = json.loads(chunk)
            break
        except json.JSONDecodeError:
            continue
    if env is None:
        return stdout
    if isinstance(env, dict):
        if env.get("is_error"):
            raise RuntimeError(str(env.get("result", "error"))[:200])
        if isinstance(env.get("structured_output"), dict):
            return json.dumps(env["structured_output"])
        for key in ("result", "response", "text", "content", "output"):
            if isinstance(env.get(key), str):
                return env[key]
    return stdout


class LLM:
    def __init__(self, cfg: dict, ledger: Ledger, agent: str = "llm"):
        self.cfg = cfg
        self.ledger = ledger
        self.agent = agent  # the ledger node each CLI call is logged under (shown in the agent terminals)
        self.backend = cfg.get("backend", "cli")
        self.cache_path = ledger.dir / "llm_cache.json"
        replay = os.environ.get("AQI_REPLAY_FROM")
        if replay and not self.cache_path.exists():
            src = ROOT / "runs" / replay / "llm_cache.json"
            if src.exists():
                shutil.copy(src, self.cache_path)
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}
        self.disabled_reason = None if cfg.get("enabled") else "disabled in config"
        self.answered_by: str | None = None
        self._client = None
        self._spent: set[str] = set()  # CLIs that failed or hit a limit during this run
        self._last_prompt: str | None = None

    # ── public ────────────────────────────────────────────────────────────
    def ask(self, system: str, user: str, schema: dict | None = None, web: bool = False) -> dict | str | None:
        """Parsed JSON (when `schema` is given) or text; None when no backend answers.

        A schema-shaped answer is checked for its required keys and enum values here; agents still
        validate meaning (e.g. that an action is allowed) themselves."""
        key = hashlib.sha256(json.dumps([self.backend, system, user, schema, web]).encode()).hexdigest()
        if key in self.cache:
            self.answered_by = "cache"
            return self.cache[key]
        if self.disabled_reason == "disabled in config":
            return None
        result = self._ask_cli(system, user, schema, web) if self.backend == "cli" else self._ask_api(system, user, schema)
        if result is not None:
            self.cache[key] = result
            self.cache_path.write_text(json.dumps(self.cache, indent=2))
        return result

    # ── CLI backend ───────────────────────────────────────────────────────
    def _ask_cli(self, system: str, user: str, schema: dict | None, web: bool):
        order = [c for c in self.cfg.get("cli", ["claude", "gemini", "codex", "agy"]) if c not in self._spent]
        errors = []
        for name in order:
            exe = shutil.which(name)
            if not exe:
                errors.append(f"{name}: not installed")
                self._spent.add(name)
                continue
            for attempt in range(2):  # one retry when the reply is not valid JSON
                t0 = time.time()
                try:
                    result = self._run_cli(name, exe, system, user, schema, web)
                    self.answered_by, self.disabled_reason = name, None
                    self._log_call(name, t0, schema, web, reply=result)
                    return result
                except subprocess.TimeoutExpired:
                    errors.append(f"{name}: timed out after {CLI_TIMEOUT}s")
                    self._log_call(name, t0, schema, web, error=errors[-1])
                    break
                except (ValueError, json.JSONDecodeError) as e:
                    errors.append(f"{name}: {e}")
                    self._log_call(name, t0, schema, web, error=errors[-1])
                    continue
                except RuntimeError as e:
                    errors.append(f"{name}: {e}")
                    self._log_call(name, t0, schema, web, error=errors[-1])
                    break
            self._spent.add(name)
        self.disabled_reason = "no CLI answered (" + "; ".join(errors)[:300] + ")"
        return None

    def _log_call(self, name: str, t0: float, schema: dict | None, web: bool, reply=None, error: str | None = None):
        """One ledger event per CLI call: the command line (prompt elided), the prompt and the raw answer."""
        flags = CLI_FLAGS[name]("<schema.json>" if schema else None, "<answer.txt>", web, "<prompt>")
        reply_text = json.dumps(reply, indent=2, ensure_ascii=False) if isinstance(reply, dict) else reply
        self.ledger.log(self.agent, "llm", f"{name} {'answered' if error is None else 'failed'} in {time.time() - t0:.0f}s",
                        cli=name, command=" ".join([name, *flags]), prompt=(self._last_prompt or "")[:6000],
                        reply=(reply_text or "")[:6000], error=error, seconds=round(time.time() - t0, 1),
                        stdin=name in STDIN_PROMPT)

    def _prompt(self, system: str, user: str, schema: dict | None) -> str:
        parts = [system.strip(), "", user.strip()]
        if schema:
            parts += ["", "Reply with ONLY one JSON object, no prose and no code fence, matching this JSON Schema:",
                      json.dumps(schema)]
        return "\n".join(parts)

    def _run_cli(self, name: str, exe: str, system: str, user: str, schema: dict | None, web: bool):
        with tempfile.TemporaryDirectory(prefix="aqi-llm-") as tmp:   # empty folder: no project files in reach
            tmp = Path(tmp)
            schema_file = tmp / "schema.json"
            if schema:
                schema_file.write_text(json.dumps(schema), encoding="utf-8")
            out_file = tmp / "answer.txt"
            prompt = self._last_prompt = self._prompt(system, user, schema)
            cmd =[exe] + CLI_FLAGS[name](str(schema_file) if schema else None, str(out_file), web, prompt)
            proc = subprocess.run(cmd, input=prompt if name in STDIN_PROMPT else "", capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", cwd=tmp, timeout=CLI_TIMEOUT)
            blob = f"{proc.stdout}\n{proc.stderr}".lower()
            if proc.returncode != 0:
                why = "usage limit" if any(h in blob for h in LIMIT_HINTS) else f"exit code {proc.returncode}"
                raise RuntimeError(why)
            text = _reply_text(name, proc.stdout, out_file)
        if not schema:
            return text.strip()
        answer = _extract_json(text)
        missing = [k for k in schema.get("required", []) if k not in answer]
        if missing:
            raise ValueError(f"reply is missing {missing}")
        for k, spec in schema.get("properties", {}).items():
            if "enum" in spec and answer.get(k) not in spec["enum"]:
                raise ValueError(f"{k}={answer.get(k)!r} is not an allowed value")
        return answer

    # ── API backend ───────────────────────────────────────────────────────
    def _ask_api(self, system: str, user: str, schema: dict | None):
        if anthropic is None:
            self.disabled_reason = "anthropic package not installed"
            return None
        if self._client is None:
            try:
                self._client = anthropic.Anthropic()
            except Exception as e:  # missing credentials can raise at construction
                self.disabled_reason = f"no Anthropic credentials ({type(e).__name__})"
                return None
        output_config = {"effort": self.cfg.get("effort", "medium")}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        try:
            response = self._client.beta.messages.create(
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
        self.answered_by = "api"
        return json.loads(text) if schema else text
