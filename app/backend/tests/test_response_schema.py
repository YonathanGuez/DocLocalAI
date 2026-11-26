import pytest
from pydantic import ValidationError

from app.schemas.response_schema import BusinessRuleValidator, RunbookResponse


def test_runbook_response_accepts_valid_payload():
    resp = RunbookResponse(
        answer="Restart the pod with kubectl delete pod [1].",
        citations=[{"chunk_id": 1, "source_file": "pods.md"}],
        confidence="high",
    )
    assert resp.confidence == "high"
    assert resp.citations[0].source_file == "pods.md"


def test_runbook_response_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        RunbookResponse(answer="Some answer here.", confidence="certain")


def test_business_rule_validator_detects_dangerous_command():
    response = "Run this to clean up: rm -rf / and reboot."
    assert BusinessRuleValidator.find_dangerous_command(response) is not None


def test_business_rule_validator_ignores_safe_commands():
    response = "Restart the pod with: kubectl delete pod my-pod"
    assert BusinessRuleValidator.find_dangerous_command(response) is None


def test_business_rule_validator_detects_dangerous_command_in_code_fence():
    response = "The fastest way to reset it is to run `rm -rf /` on the node."
    assert BusinessRuleValidator.find_dangerous_command(response) is not None


def test_business_rule_validator_ignores_rm_rf_on_subdirectory():
    response = "Clean up build artifacts with `rm -rf /tmp/build-cache`."
    assert BusinessRuleValidator.find_dangerous_command(response) is None


def test_business_rule_validator_detects_credential_leak():
    response = "Use api_key=sk-1234567890abcdef to authenticate."
    assert BusinessRuleValidator.find_credential_leak(response) is not None


def test_business_rule_validator_ignores_normal_text():
    response = "Restart a pod by deleting it; the deployment recreates it."
    assert BusinessRuleValidator.find_credential_leak(response) is None
