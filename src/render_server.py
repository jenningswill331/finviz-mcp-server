"""Authenticated HTTP entry point for a single-user Render deployment.

The MCP client must support an Authorization: Bearer header. This is not
an OAuth server; verify client compatibility before deployment.
"""

import hmac
import logging
import os
import re


class BearerGate:
    """Protect every HTTP route except a non-sensitive liveness probe."""

    def __init__(self, app, token):
        if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError("MCP_ACCESS_TOKEN must contain at least 32 non-whitespace ASCII characters")
        self.app = app
        self.expected = ("Bearer " + token).encode("ascii")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["path"] == "/healthz" and scope["method"] in ("GET", "HEAD"):
            status, body, headers = 200, b"ok", []
        else:
            values = [v for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
            if len(values) == 1 and hmac.compare_digest(values[0], self.expected):
                return await self.app(scope, receive, send)
            status, body = 401, b"Unauthorized"
            headers = [(b"www-authenticate", b'Bearer realm="finviz-mcp"')]
        headers.extend([(b"content-type", b"text/plain"), (b"cache-control", b"no-store")])
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": b"" if scope["method"] == "HEAD" else body})


class SecretFilter(logging.Filter):
    """Finviz upstream errors can include its token in a query URL."""

    def __init__(self, secrets):
        super().__init__()
        self.secrets = secrets

    def filter(self, record):
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "[REDACTED]")
        record.msg, record.args = message, ()
        # Traceback text may also carry a request URL; omit it from hosted logs.
        record.exc_info = record.exc_text = None
        return True


def create_app():
    token = os.environ.get("MCP_ACCESS_TOKEN", "")
    key = os.environ.get("FINVIZ_API_KEY", "")
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    BearerGate(None, token)  # Fail closed before importing tools.
    if not key:
        raise ValueError("FINVIZ_API_KEY is required")
    if token == key:
        raise ValueError("MCP_ACCESS_TOKEN must be different from FINVIZ_API_KEY")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", host):
        raise ValueError("RENDER_EXTERNAL_HOSTNAME must be a hostname without scheme or path")

    from mcp.server.transport_security import TransportSecuritySettings
    from .server import server

    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretFilter((token, key)))
    server.settings.stateless_http = True
    server.settings.json_response = True
    server.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[host, "localhost:*", "127.0.0.1:*"],
        allowed_origins=["https://" + host],
    )
    return BearerGate(server.streamable_http_app(), token)


def main():
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), access_log=False)


if __name__ == "__main__":
    main()
