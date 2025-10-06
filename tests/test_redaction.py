from app.redaction import redact_text


def test_redact_basic_patterns():
    text = "Patient: John Doe\nAccount # 12345\nMRN: 999"
    result = redact_text(text)
    assert "[REDACTED]" in result
