"""Behavioral checks requiring no external model or API key."""
import asyncio
import json
from types import SimpleNamespace


def test_sliding_window_expiry_and_user_isolation(monkeypatch):
    from assignment import rate_limiter as mod
    now = [100.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: now[0])
    limiter = mod.RateLimitPlugin(1, 60)
    async def send(user):
        return await limiter.on_user_message_callback(invocation_context=SimpleNamespace(user_id=user), user_message=None)
    assert asyncio.run(send("a")) is None
    assert asyncio.run(send("a")) is not None
    assert asyncio.run(send("b")) is None
    now[0] += 60
    assert asyncio.run(send("a")) is None


def test_output_callback_redacts_all_text_parts():
    from google.genai import types
    from guardrails.output_guardrails import OutputGuardrailPlugin
    response = SimpleNamespace(content=types.Content(role="model", parts=[
        types.Part.from_text(text="Password is ad"), types.Part.from_text(text="min123 and test@example.com")]))
    plugin = OutputGuardrailPlugin(False)
    result = asyncio.run(plugin.after_model_callback(callback_context=None, llm_response=response))
    text = result.content.parts[0].text
    assert "admin123" not in text and "test@example.com" not in text
    assert plugin.redacted_count == 1


def test_lab_pii_dataset():
    from guardrails.output_guardrails import content_filter, load_lab_pii_dataset
    for case in load_lab_pii_dataset()["pii_cases"]:
        result = content_filter(case["input_text"])
        assert result["safe"] == case["expect_safe"], case["id"]


def test_egress_url_tricks_and_sensitive_payloads():
    from assignment.pipeline import is_egress_allowed
    for url in ["http://api.vinbank.example", "https://api.vinbank.example.evil.com",
                "https://evil.com@api.vinbank.example", "https://api.vinbank.example:8443"]:
        assert not is_egress_allowed(url, "bank transfer")
    for payload in ["a@b.com", "0901234567", "db.vinbank.internal:5432", "ａｄｍｉｎ１２３"]:
        assert not is_egress_allowed("https://api.vinbank.example", payload)


def test_audit_pairs_concurrent_requests_and_redacts(tmp_path):
    from assignment.audit_log import AuditLogPlugin
    audit = AuditLogPlugin()
    for request_id in ("a", "b"):
        audit.record_input(user_id="same", text="password=admin123", request_id=request_id)
    for request_id in ("b", "a"):
        audit.record_output(user_id="same", text="test@example.com", request_id=request_id)
    path = audit.export_json(str(tmp_path / "nested/audit.json"))
    rows = json.loads(path.read_text())
    assert [r["request_id"] for r in rows] == ["b", "a"]
    assert "admin123" not in path.read_text() and "test@example.com" not in path.read_text()
    assert all(r["latency_ms"] >= 0 for r in rows)


def test_monitoring_repeated_checks_do_not_duplicate_alerts():
    from assignment.monitoring import MonitoringAlert
    monitor = MonitoringAlert(total_requests=10, blocked_requests=8, rate_limit_hits=6)
    assert len(monitor.check_metrics()) == 2
    assert len(monitor.check_metrics()) == 2


def test_assignment_suite_executes_plugins_and_writes_schema_valid_results(monkeypatch, tmp_path):
    from pathlib import Path
    import assignment.pipeline as pipeline
    from agents import agent as factories
    from core import config
    from core.openai_runtime import OpenAIRunner
    import jsonschema

    schema = Path(__file__).resolve().parents[2] / "schemas/results.schema.json"
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/results.schema.json").write_text(schema.read_text())
    monkeypatch.setattr(pipeline, "__file__", str(tmp_path / "src/assignment/pipeline.py"))
    monkeypatch.setattr(config, "get_openrouter_api_key", lambda: "test-only")
    model_calls = []
    class TestRunner(OpenAIRunner):
        async def chat(self, agent, text):
            blocked = await self._run_input_plugins(text)
            if blocked is not None:
                return blocked
            model_calls.append(text)
            return await self._run_output_plugins("Please check savings rates with your bank.")
    plugins = pipeline.build_production_plugins()
    monkeypatch.setattr(factories, "create_blue_agent", lambda plugins: (None, TestRunner(app_name="test", model="test", plugins=plugins)))
    audit, monitor = pipeline.build_observability()
    monkeypatch.setattr(audit, "export_json", lambda: None)
    monkeypatch.setattr(monitor, "export_json", lambda: None)
    result = asyncio.run(pipeline.run_assignment_suite(dict(plugins=plugins, audit=audit, monitor=monitor)))
    jsonschema.validate(result, json.loads(schema.read_text()))
    assert all(not row["blocked"] for row in result["safe_queries"])
    assert all(row["blocked"] for row in result["attack_queries"] + result["edge_cases"])
    assert len(model_calls) == 16
    assert result["rate_limit"]["passed"] == 10
    assert result["rate_limit"]["blocked"] == 5
    assert len(audit.logs) == monitor.total_requests == 32
    assert (tmp_path / "outputs/results.json").exists()


def test_local_configuration_routes_blue_red_and_nemo(monkeypatch):
    from core import config
    from agents.red_advance_nemo import _model_entry
    monkeypatch.setenv("LAB_RUNTIME", "local")
    monkeypatch.setenv("LOCAL_MODEL", "qwen3:4b-instruct")
    monkeypatch.setenv("LOCAL_BASE_URL", "http://localhost:11434/v1")
    assert config.get_blue_provider() == config.get_red_provider() == "local"
    assert config.get_blue_model() == config.get_red_model() == "qwen3:4b-instruct"
    assert config.red_uses_openai_sdk()
    assert config.blue_client_kwargs()["base_url"] == config.red_openai_client_kwargs()["base_url"]
    assert _model_entry("local", config.get_red_model())["parameters"]["base_url"] == "http://localhost:11434/v1"


def test_egress_blocks_url_encoded_sensitive_data():
    from assignment.pipeline import is_egress_allowed
    assert not is_egress_allowed("https://api.vinbank.example/collect?value=admin%31%32%33", "bank transfer")


def test_liquid_configuration_routes_blue_red_and_nemo(monkeypatch):
    from core import config
    from agents.red_advance_nemo import _model_entry
    monkeypatch.setenv("LAB_RUNTIME", "liquid")
    monkeypatch.setenv("LIQUID_MODEL", "lfm3-1.7b")
    monkeypatch.setenv("LIQUID_API_KEY", "test-only")
    assert config.get_blue_provider() == config.get_red_provider() == "liquid"
    assert config.get_blue_model() == config.get_red_model() == "lfm3-1.7b"
    assert config.red_uses_openai_sdk()
    assert config.blue_client_kwargs() == config.red_openai_client_kwargs()
    entry = _model_entry("liquid", config.get_red_model())
    assert entry["parameters"]["base_url"] == "https://api.liquid.ai/openai/v1"
    assert entry["parameters"]["api_key"] == "test-only"
