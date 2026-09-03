import json
from pathlib import Path
import smtplib
import pytest
import main
from src.email import SMTPConfig, build_message, send_briefing

HTML = "<!doctype html><p>unchanged body</p><p>LLM editorial edition · 2026-09-03 10:00 UTC</p>"

def env(monkeypatch):
    values = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": "587", "SMTP_USERNAME": "user", "SMTP_PASSWORD": "very-secret", "EMAIL_FROM": "sender@example.com", "EMAIL_TO": "a@example.com, b@example.com"}
    for key, value in values.items(): monkeypatch.setenv(key, value)
    return values

class FakeSMTP:
    instances = []
    def __init__(self, host, port, timeout): self.calls = []; self.message = None; self.__class__.instances.append(self)
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def ehlo(self): self.calls.append("ehlo")
    def starttls(self, **kwargs): self.calls.append("starttls")
    def login(self, username, password): self.calls.append("login")
    def send_message(self, message, **kwargs): self.calls.append("send_message"); self.message = message

def test_config_message_and_starttls(monkeypatch, tmp_path):
    values = env(monkeypatch); config = SMTPConfig.from_env()
    assert (config.host, config.password, config.recipients) == (values["SMTP_HOST"], values["SMTP_PASSWORD"], ("a@example.com", "b@example.com"))
    message = build_message(HTML, config)
    assert "2026-09-03" in message["Subject"]
    assert [part.get_content_type() for part in message.iter_parts()] == ["text/plain", "text/html"]
    assert HTML in message.get_body(preferencelist=("html",)).get_content()
    FakeSMTP.instances.clear(); monkeypatch.setattr("src.email.smtplib.SMTP", FakeSMTP)
    briefing, metadata = tmp_path / "briefing.html", tmp_path / "delivery.json"; briefing.write_text(HTML)
    assert send_briefing(briefing, metadata)
    assert FakeSMTP.instances[0].calls == ["ehlo", "starttls", "ehlo", "login", "send_message"]
    payload = json.loads(metadata.read_text()); assert payload["recipient_count"] == 2
    assert "very-secret" not in metadata.read_text()

def test_missing_password_and_auth_failure_are_safe(monkeypatch, tmp_path):
    env(monkeypatch); briefing, metadata = tmp_path / "briefing.html", tmp_path / "delivery.json"; briefing.write_text(HTML)
    monkeypatch.delenv("SMTP_PASSWORD"); assert not send_briefing(briefing, metadata)
    assert "SMTP_PASSWORD" in json.loads(metadata.read_text())["error"]
    env(monkeypatch)
    monkeypatch.setattr(FakeSMTP, "login", lambda self, u, p: (_ for _ in ()).throw(smtplib.SMTPAuthenticationError(535, b"server text very-secret")))
    monkeypatch.setattr("src.email.smtplib.SMTP", FakeSMTP); assert not send_briefing(briefing, metadata)
    assert json.loads(metadata.read_text())["error"] == "SMTP authentication failed"
    assert briefing.read_text() == HTML and "very-secret" not in metadata.read_text()

def test_cli_only_sends_when_explicit(monkeypatch, tmp_path):
    calls = []; output = tmp_path / "llm.html"; output.write_text(HTML)
    monkeypatch.setattr(main, "run_pipeline", lambda: tmp_path / "sample.html")
    monkeypatch.setattr(main, "deliver_briefing_locally", lambda path: "saved")
    monkeypatch.setattr(main, "send_briefing", lambda path: calls.append(path) or True)
    assert main.main([]) == 0 and calls == []
    monkeypatch.setattr(main, "run_llm_pipeline", lambda strategy_region=None: output)
    assert main.main(["--live", "--llm", "--send-email"]) == 0 and calls == [output]

def test_email_only_skips_collectors_and_openai(monkeypatch, tmp_path):
    briefing = tmp_path / "existing.html"; briefing.write_text(HTML)
    monkeypatch.setattr(main, "DEFAULT_BRIEFING", briefing)
    monkeypatch.setattr(main, "run_live_pipeline", lambda: pytest.fail("collector called"))
    monkeypatch.setattr(main, "create_client", lambda: pytest.fail("OpenAI called"))
    monkeypatch.setattr(main, "send_briefing", lambda path: path == briefing)
    assert main.main(["--email-existing-briefing"]) == 0

def test_missing_existing_briefing_fails_without_smtp(tmp_path):
    metadata = tmp_path / "delivery.json"
    assert not send_briefing(tmp_path / "missing.html", metadata)
    assert json.loads(metadata.read_text())["success"] is False

def test_workflow_is_manual_only():
    workflow = Path(".github/workflows/manual_llm_test.yml").read_text()
    assert "workflow_dispatch:" in workflow and "schedule:" not in workflow
