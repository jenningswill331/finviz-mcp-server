import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth import AccessToken
from src.oauth_server import OwnerGitHubProvider, create_app


def configure(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'finviz-test.onrender.com')
    monkeypatch.setenv('FASTMCP_HOME', str(tmp_path))
    monkeypatch.delenv('SETUP_ONLY', raising=False)
    for name in ['FINVIZ_API_KEY','GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET','OAUTH_SIGNING_KEY']:
        monkeypatch.setenv(name, 'test-only-' + name + 'x'*40)
    monkeypatch.setenv('ALLOWED_GITHUB_USER_ID', '341563411')


def test_setup_mode_exposes_no_tools(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'finviz-test.onrender.com')
    monkeypatch.setenv('SETUP_ONLY', 'true')
    with TestClient(create_app(), base_url='https://finviz-test.onrender.com') as c:
        assert c.get('/healthz').status_code == 200
        assert c.post('/mcp', json={'method':'tools/list'}).status_code == 503


def test_oauth_discovery_and_unauthorized(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    with TestClient(create_app(), base_url='https://finviz-test.onrender.com') as c:
        assert c.get('/healthz').status_code == 200
        r = c.get('/.well-known/oauth-authorization-server')
        assert r.status_code == 200
        assert r.json()['authorization_endpoint'].startswith('https://finviz-test.onrender.com/')
        assert c.post('/mcp', json={'method':'tools/list'}).status_code == 401
        assert c.post('/mcp', headers={'Authorization':'Bearer invalid'}).status_code == 401
        assert c.get('/healthz', headers={'Host':'attacker.example'}).status_code == 400


def test_owner_allowlist():
    provider = OwnerGitHubProvider(owner_id='341563411', client_id='test', client_secret='test-secret', base_url='https://test.example', jwt_signing_key='x'*40)
    for sub, allowed in [('341563411', True), ('123', False), ('', False)]:
        token = AccessToken(token='test', client_id='test', scopes=['read:user'], claims={'sub':sub})
        with patch.object(GitHubProvider, 'verify_token', new=AsyncMock(return_value=token)):
            assert (asyncio.run(provider.verify_token('test')) is not None) == allowed


def test_missing_secrets_fail_closed(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'finviz-test.onrender.com')
    monkeypatch.delenv('SETUP_ONLY', raising=False)
    monkeypatch.delenv('GITHUB_CLIENT_SECRET', raising=False)
    with pytest.raises(ValueError, match='GITHUB_CLIENT_SECRET'):
        create_app()


def test_authenticated_proxy_lists_tools(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    token = AccessToken(token='test', client_id='test', scopes=['read:user'], claims={'sub':'341563411'})
    with patch.object(OwnerGitHubProvider, 'verify_token', new=AsyncMock(return_value=token)):
        with TestClient(create_app(), base_url='https://finviz-test.onrender.com') as c:
            headers = {'Authorization':'Bearer test', 'Accept':'application/json, text/event-stream'}
            response = c.post('/mcp', headers=headers, json={'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}})
            assert response.status_code == 200
            data = response.json()
            assert 'result' in data, data
            assert len(data['result']['tools']) > 0
