"""Render endpoint with GitHub OAuth restricted to the configured owner."""
import logging
import os
import re

from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .render_server import SecretFilter


class OwnerGitHubProvider(GitHubProvider):
    def __init__(self, *, owner_id, **kwargs):
        self.owner_id = str(owner_id)
        super().__init__(**kwargs)

    async def verify_token(self, token):
        validated = await super().verify_token(token)
        if validated is None or str(validated.claims.get("sub", "")) != self.owner_id:
            return None
        return validated


async def health(request):
    return PlainTextResponse("ok", headers={"Cache-Control": "no-store"})


async def setup(request):
    return PlainTextResponse("Finviz MCP setup is not complete. Tools are disabled.", status_code=503)


def create_app():
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", host):
        raise ValueError("RENDER_EXTERNAL_HOSTNAME is required")
    host_middleware = Middleware(TrustedHostMiddleware, allowed_hosts=[host, "localhost", "127.0.0.1"])
    if os.environ.get("SETUP_ONLY", "").lower() == "true":
        # Reserve a Render URL without secrets or any market-data tools.
        return Starlette(routes=[Route("/healthz", health), Route("/{path:path}", setup, methods=["GET", "POST", "DELETE"])], middleware=[host_middleware])

    names = ("FINVIZ_API_KEY", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "OAUTH_SIGNING_KEY", "ALLOWED_GITHUB_USER_ID")
    config = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in config.items() if not value]
    if missing:
        raise ValueError("Missing required settings: " + ", ".join(missing))
    if len(config["OAUTH_SIGNING_KEY"]) < 32:
        raise ValueError("OAUTH_SIGNING_KEY must contain at least 32 characters")
    if not config["ALLOWED_GITHUB_USER_ID"].isdigit():
        raise ValueError("ALLOWED_GITHUB_USER_ID must be a numeric GitHub account ID")

    from .server import server as backend
    secrets = tuple(config[name] for name in ("FINVIZ_API_KEY", "GITHUB_CLIENT_SECRET", "OAUTH_SIGNING_KEY"))
    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretFilter(secrets))
    # Avoid third-party HTTP logs containing OAuth code query strings.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    auth = OwnerGitHubProvider(
        owner_id=config["ALLOWED_GITHUB_USER_ID"],
        client_id=config["GITHUB_CLIENT_ID"],
        client_secret=config["GITHUB_CLIENT_SECRET"],
        base_url="https://" + host,
        required_scopes=["read:user"],
        jwt_signing_key=config["OAUTH_SIGNING_KEY"],
        require_authorization_consent=True,
    )
    proxy = FastMCP.as_proxy(backend, name="Will's Finviz Research", auth=auth, mask_error_details=True)
    proxy.custom_route("/healthz", methods=["GET"])(health)
    return proxy.http_app(path="/mcp", stateless_http=True, json_response=True, middleware=[host_middleware])


def main():
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), access_log=False)


if __name__ == "__main__":
    main()
