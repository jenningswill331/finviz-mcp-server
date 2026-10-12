# Private Finviz MCP on Render

Prepared for jenningswill331/finviz-mcp-server. These changes are not deployed.

## Compatibility gate

This entry point requires `Authorization: Bearer <MCP_ACCESS_TOKEN>` on every
MCP request. It does not implement OAuth. Before deploying, confirm that the
intended ChatGPT plugin connection accepts a configured Authorization header.
If the connection only supports OAuth, add an OAuth gateway first. Never
work around that requirement by removing authentication or putting a secret
in the MCP URL.

## Render configuration (after the compatibility gate)

- Repository: the user's fork containing these changes.
- Language: Docker; branch: the branch containing the changes.
- Root directory: empty; Dockerfile: `./Dockerfile`.
- Start command: Docker default (runs `python -m src.render_server`).
- Health-check path: `/healthz`.
- Start with the Free compute plan for testing. Availability is subject to
  Render's free-tier restrictions, including idle shutdown.
- Environment secret `FINVIZ_API_KEY`: the newly regenerated Finviz token.
- Environment secret `MCP_ACCESS_TOKEN`: generate a separate random secret
  of at least 32 characters (use Render's Generate control).
- `PORT`: Render supplies this automatically (defaults to 10000).
- `RENDER_EXTERNAL_HOSTNAME`: Render supplies this for web services. Must
  contain only the public hostname, without a scheme or path.

After deployment the MCP URL is `https://<service-hostname>/mcp`.
Keep both secrets out of GitHub, screenshots, chat, and connection URLs.
The server refuses startup without its required secrets and hostname.

## What was verified

Offline tests check missing, incorrect, duplicate and query-string tokens;
fail-closed configuration; an authenticated MCP initialize request; liveness;
and rejection of an unexpected Host header. No live Finviz calls were made.
The tests use MCP 1.30.0, pinned because the original unbounded dependency
installed MCP 2.x, which removed the FastMCP import used by this project.
The hosted entry point also avoids the original invalid host/port run arguments.

Run: `python -m pytest tests/test_render_auth.py -q`

Remaining checks: target plugin authentication compatibility, actual Render
Docker build, and a live Finviz screening request after secret entry.
