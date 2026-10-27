"""Scout tools and the Claude CLI tool lock-down, with every network call replaced by a fake."""
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from aqi import scout_tools as T
from aqi.ledger import Ledger
from aqi.llm import LLM, _claude_tool_calls, _reply_text

FIRMS_CSV = """latitude,longitude,bright_ti4,acq_date,confidence,frp
30.10,75.80,330,2024-11-01,h,40.5
30.20,75.90,320,2024-11-01,n,10.0
29.90,76.10,315,2024-11-02,l,5.5
"""


def _fake_get(text):
    return lambda *a, **k: SimpleNamespace(text=text, raise_for_status=lambda: None)


def test_fires_summarises_firms_csv(monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    monkeypatch.setattr(T.requests, "get", _fake_get(FIRMS_CSV))
    out = T.fires("2024-11-01", days=2)
    assert out["fires"] == 3 and out["high_confidence"] == 1
    assert out["by_day"] == {"2024-11-01": 2, "2024-11-02": 1}
    assert out["total_fire_radiative_power_mw"] == 56.0
    assert out["strongest"][0]["frp"] == 40.5
    assert out["source"].endswith("VIIRS_SNPP_SP")  # an old date uses the archive product


def test_fires_rejects_bad_input(monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    with pytest.raises(ValueError, match="unknown region"):
        T.fires("2024-11-01", region="mars")
    with pytest.raises(ValueError, match="future"):
        T.fires("2999-01-01")


def test_nearby_sources_groups_and_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "ROOT", tmp_path)
    monkeypatch.setattr(T, "SNAPSHOT", tmp_path / "none.json")
    monkeypatch.setattr(T, "geocode", lambda place: {"name": place, "lat": 28.65, "lon": 77.30})
    overpass = {"elements": [
        {"tags": {"landuse": "construction", "name": "Metro depot"}, "center": {"lat": 28.651, "lon": 77.301}},
        {"tags": {"landuse": "industrial"}, "center": {"lat": 28.66, "lon": 77.31}},
        {"tags": {"highway": "trunk", "ref": "NH9"}, "center": {"lat": 28.65, "lon": 77.29}},
        {"tags": {"highway": "trunk", "ref": "NH9"}, "center": {"lat": 28.652, "lon": 77.292}},
    ]}
    calls = []

    def fake_post(url, **k):
        calls.append(url)
        return SimpleNamespace(ok=True, text=json.dumps(overpass), json=lambda: overpass)

    monkeypatch.setattr(T.requests, "post", fake_post)
    out = T.nearby_sources("Anand Vihar", 2)
    s = out["sources"]
    assert s["construction"]["count"] == 1 and s["construction"]["nearest"][0]["name"] == "Metro depot"
    assert s["industrial"]["count"] == 1 and s["landfill"]["count"] == 0
    assert s["major_road"] == {"segments": 2, "named": ["NH9"]}
    T.nearby_sources("Anand Vihar", 2)  # second call is served from the cache
    assert len(calls) == 1


def test_nearby_sources_reports_busy_servers(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "ROOT", tmp_path)
    monkeypatch.setattr(T, "SNAPSHOT", tmp_path / "none.json")
    monkeypatch.setattr(T, "geocode", lambda place: {"name": place, "lat": 28.65, "lon": 77.30})
    monkeypatch.setattr(T.requests, "post", lambda *a, **k: SimpleNamespace(ok=False, text="busy"))
    with pytest.raises(RuntimeError, match="busy"):
        T.nearby_sources("ITO")


def test_station_snapshot_matches_plain_names(monkeypatch, tmp_path):
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    pd.DataFrame({"station": ["301_Anand_Vihar_Delhi_DPCC"] * 3, "date": pd.date_range("2025-12-29", periods=3),
                  "aqi": [480.0, 500.0, None], "bucket": [5.0, 5.0, None], "PM2.5": [350.0, 361.5, None]}
                 ).to_parquet(run / "daily.parquet")
    monkeypatch.setattr(T, "ROOT", tmp_path)
    out = T.station_snapshot("Anand Vihar", days=2)
    assert out["station"] == "301_Anand_Vihar_Delhi_DPCC"
    assert out["days"][0] == {"date": "2025-12-30", "aqi": 500, "category": "Severe", "pm25": 361.5}
    assert out["days"][1]["aqi"] is None
    with pytest.raises(ValueError, match="no station"):
        T.station_snapshot("Atlantis")


def test_claude_tool_calls_are_read_from_the_stream():
    stream = "\n".join(json.dumps(e) for e in [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "a", "name": "mcp__aqi-scout__fires", "input": {"days": 2}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "a", "content": [{"type": "text", "text": '{"fires": 618}'}]}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "b", "name": "mcp__aqi-scout__nearby_sources", "input": {"place": "ITO"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "b", "content": '{"error": "busy"}'}]}},
        {"type": "result", "result": "the brief", "is_error": False},
    ])
    calls = _claude_tool_calls(stream)
    assert [c["tool"] for c in calls] == ["mcp__aqi-scout__fires", "mcp__aqi-scout__nearby_sources"]
    assert calls[0]["ok"] is True and calls[1]["ok"] is False
    assert _reply_text("claude", stream, None) == "the brief"


def test_claude_gets_only_the_tools_it_needs(tmp_path):
    led = Ledger("t", runs_dir=tmp_path)
    plain = LLM({"enabled": True}, led)
    assert plain._tool_flags("claude", False, "m.json") == ["--tools", "", "--strict-mcp-config"]
    mcp = {"servers": {"s": {"command": "python"}}, "tools": ["mcp__s__fires"]}
    scout = LLM({"enabled": True}, led, mcp=mcp)
    flags = scout._tool_flags("claude", True, "m.json")
    assert flags[:3] == ["--tools", "WebSearch,WebFetch", "--strict-mcp-config"]
    assert flags[flags.index("--allowedTools") + 1:] == ["WebSearch", "WebFetch", "mcp__s__fires"]
    assert scout._tool_flags("gemini", True, "m.json") == []


def test_nearby_sources_falls_back_to_the_saved_snapshot(monkeypatch, tmp_path):
    snap = tmp_path / "osm_snapshot.json"
    snap.write_text(json.dumps({"taken": "2026-10-27", "radius_km": 2.0, "places": {
        "anand_vihar": {"place": "Anand Vihar", "sources": {"industrial": {"count": 4, "nearest": []}}}}}))
    monkeypatch.setattr(T, "ROOT", tmp_path)
    monkeypatch.setattr(T, "SNAPSHOT", snap)
    monkeypatch.setattr(T, "geocode", lambda place: {"name": place, "lat": 28.65, "lon": 77.30})
    monkeypatch.setattr(T.requests, "post", lambda *a, **k: SimpleNamespace(ok=False, text="busy"))
    out = T.nearby_sources("Anand Vihar", 2)
    assert out["sources"]["industrial"]["count"] == 4 and "2026-10-27" in out["note"]
    with pytest.raises(RuntimeError):  # no snapshot for this place: the error goes back to the model
        T.nearby_sources("ITO", 2)
