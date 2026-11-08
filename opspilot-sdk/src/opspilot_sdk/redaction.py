"""Conservative bounded projection. Never stringify arbitrary objects."""
import json
import math
import re

SENSITIVE = re.compile(
    r"password|passwd|secret|token|authorization|cookie|api.?key|email|"
    r"card|credit|phone|address|ssn|session|credential|private.?key", re.I
)


def clean_text(text: str, secrets=()) -> str:
    # Cap work before regex processing; redact before final field truncation.
    for secret in secrets:
        text = text.replace(secret, "[REDACTED]")
    text = text[:16000]
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*", "[REDACTED]", text, flags=re.S)
    text = re.sub(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+", "[REDACTED]", text)
    text = re.sub(r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|cookie|credential)\b[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)", r"\1=[REDACTED]", text)
    text = re.sub(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+", "[URL REDACTED]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b(?:\d[ -]?){9,19}\b", "[NUMBER REDACTED]", text)
    text = re.sub(r"\b(?:sk-[\w-]+|AIza[\w-]+|gh[pousr]_[\w]+|eyJ[\w-]+\.[\w-]+\.[\w-]+)\b", "[REDACTED]", text)
    return text


def project(value, depth=0, secrets=()):
    if depth > 4:
        return "[TRUNCATED]"
    if type(value) is dict:
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 20:
                break
            if type(key) is not str:
                continue
            result[clean_text(key, secrets)[:80]] = "[REDACTED]" if SENSITIVE.search(key) else project(item, depth + 1, secrets)
        return result
    if type(value) in (list, tuple):
        return [project(item, depth + 1, secrets) for item in value[:20]]
    if type(value) is str:
        return clean_text(value, secrets)[:500]
    if value is None or type(value) in (bool, int):
        return value if type(value) is not int or value.bit_length() < 128 else "[TRUNCATED]"
    if type(value) is float:
        return value if math.isfinite(value) else None
    return "[OMITTED]"


def metadata_projection(metadata, secrets=()):
    result = project(metadata, secrets=secrets) if type(metadata) is dict else {}
    # The API bounds json.dumps(metadata) to 4000 characters.
    return result if len(json.dumps(result)) <= 4000 else {"sdk": "metadata omitted: size limit"}
