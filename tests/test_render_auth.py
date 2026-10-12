import asyncio

import pytest
from starlette.testclient import TestClient

from src.render_server import BearerGate, create_app

TOKEN = "test-only-access-token-" + "x" * 32


def test_gate_rejects_missing_wrong_duplicate_and_query_tokens():
    calls = []

    async def inner(scope, receive, send):
        calls.append(scope)

    async def check(headers, query=b""):
        events = []

        async def send(event):
            events.append(event)

        await BearerGate(inner, TOKEN)(
            {"type": "http", "method": "POST", "path": "/mcp", "headers": headers, "query_string": query},
            None, send,
        )
        assert events[0]["status"] == 401

    for headers, query in [([], b""), ([(b"authorization", b"Bearer wrong")], b""),
                           ([(b"authorization", ("Bearer " + TOKEN).encode())] * 2, b""),
                           ([], ("auth=" + TOKEN).encode())]:
        asyncio.run(check(headers, query))
    assert not calls


def test_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("MCP_ACCESS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="MCP_ACCESS_TOKEN"):
        create_app()


def test_http_mcp_handshake_and_host_validation(monkeypatch):
    monkeypatch.setenv("MCP_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("FINVIZ_API_KEY", "test-only-finviz-key")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "finviz-test.onrender.com")
    with TestClient(create_app(), base_url="https://finviz-test.onrender.com") as client:
        assert client.get("/healthz").status_code == 200
        assert client.post("/mcp").status_code == 401
        headers = {"Authorization": "Bearer " + TOKEN, "Accept": "application/json, text/event-stream"}
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
        response = client.post("/mcp", headers=headers, json=payload)
        assert response.status_code == 200
        assert response.json()["result"]["serverInfo"]["name"] == "Finviz MCP Server"
        bad_headers = dict(headers, host="attacker.example")
        assert client.post("/mcp", headers=bad_headers, json=payload).status_code == 421
