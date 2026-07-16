def _request(
    self, method: str, path: str, *, json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{self.base_url}{path}"

    logger.info(
        "[ORCH] %s %s payload=%s",
        method, path, _redact(json) if json is not None else "<none>",
    )

    try:
        response = self.session.request(
            method, url, json=json, timeout=_DEFAULT_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        logger.error("[ORCH] %s %s network error: %s", method, path, exc)
        raise OrchestratorHTTPError(0, f"Request failed: {exc}") from exc

    if not response.ok:
        body = _safe_extract_error(response)
        logger.error(
            "[ORCH] %s %s failed status=%d body=%s",
            method, path, response.status_code, body,
        )
        raise OrchestratorHTTPError(
            response.status_code,
            f"{method} {path} failed",
            body=body,
        )

    try:
        return response.json()
    except ValueError as exc:
        logger.error(
            "[ORCH] %s %s returned non-JSON body=%s",
            method, path, response.text[:500],
        )
        raise OrchestratorHTTPError(
            response.status_code,
            f"{method} {path} returned non-JSON",
            body=response.text[:500],
        ) from exc


_SENSITIVE_KEYS = frozenset({
    "password", "token", "bearer_token", "secret", "authorization", "api_key",
})


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    """Shallow-copy the payload with any sensitive fields replaced."""
    return {
        k: ("***REDACTED***" if k.lower() in _SENSITIVE_KEYS else v)
        for k, v in payload.items()
    }


def _safe_extract_error(response: requests.Response) -> str:
    """Return the most useful error text the orchestrator gave us.

    Errors are usually JSON like {"detail": "..."} but may be plain text or
    HTML on infra failures. Fall back gracefully in all cases.
    """
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or "<empty body>"

    for key in ("detail", "message", "error", "reason"):
        if isinstance(data, dict) and (val := data.get(key)):
            return str(val)
    return str(data)[:500]


