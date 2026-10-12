# Finviz MCP for ChatGPT on Render

The Docker entry point uses GitHub OAuth and restricts MCP access to the numeric
GitHub account ID in ALLOWED_GITHUB_USER_ID. It requests read:user only, with no
repository-writing permission. The Finviz API token stays on the server.

## 1. Reserve the Render URL without credentials

Create a Render Web Service using this repository and branch:

- Repository: https://github.com/jenningswill331/finviz-mcp-server
- Branch: fix/secure-render-deployment
- Language: Docker
- Root Directory: empty
- Dockerfile Path: ./Dockerfile (default)
- Docker Command: empty (use the image default)
- Compute: Free for initial testing
- Health Check Path: /healthz
- Environment variable: SETUP_ONLY=true

Deploy. In setup mode, /healthz returns 200; all other paths return 503.
No Finviz tools, account credentials or market-data requests are available.
Copy the actual HTTPS onrender.com service URL from Render after deployment.
Do not assume a hostname from the service name.

## 2. Register your GitHub sign-in app

Open https://github.com/settings/applications/new (OAuth App, not GitHub App).

- Application name: Will Finviz Research
- Homepage URL: the actual Render service URL
- Authorization callback URL: the actual Render service URL + /auth/callback

Save the app and generate a client secret. Enter it directly in Render;
do not put it in GitHub source code, chat, screenshots or URLs.

## 3. Enable the authenticated server

Set the following environment variables in Render:

| Name | Value |
| --- | --- |
| FINVIZ_API_KEY | Your regenerated Finviz Elite token |
| GITHUB_CLIENT_ID | Client ID from the new OAuth App |
| GITHUB_CLIENT_SECRET | Client secret from the new OAuth App |
| OAUTH_SIGNING_KEY | Separate random secret, at least 32 characters; use Generate |
| ALLOWED_GITHUB_USER_ID | 341563411 (verified ID for jenningswill331) |
| SETUP_ONLY | false |

Render provides PORT and RENDER_EXTERNAL_HOSTNAME automatically.
Do not set MCP_ACCESS_TOKEN; that belongs to an unused alternate entry point.
Save and redeploy. Without the required configuration, the server fails closed.

## 4. Connect and test

In ChatGPT's custom MCP connection, use the actual Render URL + /mcp and OAuth.
The server publishes OAuth discovery metadata and supports client registration.
Sign in as jenningswill331. All other GitHub account IDs are denied MCP access.
Verify with a small stock screen before using any results for trade research.
No trading tools or Robinhood credentials are added to this server.

## Limits and validation

Free hosting can sleep. OAuth state uses FastMCP's encrypted local storage;
Render's ephemeral filesystem means redeploys may require reconnecting the
ChatGPT connection. For persistent sessions, use durable encrypted storage.
Access logs are disabled to avoid recording OAuth codes in request URLs.

Local tests cover setup mode, missing secrets, OAuth discovery, rejected missing
or invalid tokens, owner allowlisting and Host validation, plus the alternate
bearer entry point. They do not prove the live GitHub OAuth callback, Render
Docker build or live Finviz API works. Those checks need the deployment and
credentials entered by the owner.

Run: python -m pytest tests/test_render_auth.py tests/test_oauth_server.py -q
