import os
import json
import sqlite3
from typing import Any, Generator

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

os.environ["M14404_ENV"] = "test"
os.environ["M14404_DB_PATH"] = "./.M14404_test.db"
os.environ["M14404_ORIGIN_DOMAIN_NAME"] = "abc.xyz"

from M14404.main import M14404  # noqa: E402

HTTP_TABLE = "http_logs"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    try:
        os.remove(os.environ["M14404_DB_PATH"])
    except FileNotFoundError:
        pass
    try:
        with TestClient(M14404) as c:
            yield c
    finally:
        db_path = os.environ["M14404_DB_PATH"]
        for suffix in ["", "-shm", "-wal"]:
            try:
                os.remove(db_path + suffix)
            except FileNotFoundError:
                pass


def test_http_request_logs_and_returns_id(client: TestClient) -> None:
    response = client.get(
        "/some/path?foo=bar",
        headers={
            "Host": "www.abc.xyz",
            "User-Agent": "pytest-agent",
            "Accept": "text/html",
        },
    )
    assert response.status_code == 200
    body = response.text
    assert "HTTP Log ID" in body

    # quick check that an integer ID is present in the HTML
    assert any(ch.isdigit() for ch in body)


def test_websocket_handshake_and_message_logging(client: TestClient) -> None:
    with client.websocket_connect(
        "/ws/test?x=1", headers={"Host": "www.abc.xyz"}
    ) as ws:
        first_msg = ws.receive_text()
        assert first_msg.isdigit()

        ws.send_text("ping")
        second_msg = ws.receive_text()
        assert second_msg.isdigit()
        assert int(second_msg) >= int(first_msg)


def test_full_url_and_headers_shape(client: TestClient) -> None:
    host = "www.abc.xyz"
    path = "/abc/def"
    query = "q=1"
    url = f"{path}?{query}"

    response = client.get(
        url,
        headers={
            "Host": host,
            "User-Agent": "pytest-agent",
            "Accept": "application/json",
            "X-Extra": "value",
        },
    )
    assert response.status_code == 200

    conn = sqlite3.connect(os.environ["M14404_DB_PATH"])
    try:
        cur = conn.execute(
            f"SELECT full_url, user_agent, accept, other_headers FROM {HTTP_TABLE} ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    finally:
        conn.close()

    assert row is not None
    full_url, user_agent, accept, other_headers = row

    assert full_url == f"{host}{path}?{query}"
    assert user_agent == "pytest-agent"
    assert accept == "application/json"
    other = (
        other_headers if isinstance(other_headers, dict) else json.loads(other_headers)
    )
    assert other["x-extra"] == "value"


def test_origin_domain_redirects_to_www(client: TestClient) -> None:
    response = client.get(
        "/some/path?foo=bar",
        headers={"Host": "abc.xyz"},
        follow_redirects=False,
    )
    assert response.status_code == 308
    assert response.headers["location"] == "http://www.abc.xyz/some/path?foo=bar"


def test_root_subdomain_redirects_with_port(client: TestClient) -> None:
    response = client.get(
        "/some/path?foo=bar",
        headers={"Host": "abc.xyz:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 308
    # Notice that standard starlette request url scheme/netloc might strip default ports or parse them
    # Let's ensure the redirect contains what's expected for a port.
    location = response.headers["location"]
    assert "www.abc.xyz" in location
    assert location.endswith("/some/path?foo=bar")


def test_about_subdomain_returns_M14404(client: TestClient) -> None:
    response = client.get("/anything", headers={"Host": "about.abc.xyz"})
    assert response.status_code == 200
    assert response.text == "M14404"


def test_other_subdomain_returns_404(client: TestClient) -> None:
    response = client.get("/anything", headers={"Host": "nope.abc.xyz"})
    assert response.status_code == 404


def test_about_subdomain_ws_returns_M14404_and_closes(client: TestClient) -> None:
    with client.websocket_connect("/ws/about", headers={"Host": "about.abc.xyz"}) as ws:
        assert ws.receive_text() == "M14404"


def test_other_subdomain_ws_closes_with_policy_violation(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/nope", headers={"Host": "nope.abc.xyz"}):
            pass
    assert exc_info.value.code == 1008


def test_misconfigured_origin_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("M14404_ORIGIN_DOMAIN_NAME", "")
    try:
        os.remove(os.environ["M14404_DB_PATH"])
    except FileNotFoundError:
        pass
    try:
        with TestClient(M14404) as c:
            response = c.get("/anything", headers={"Host": "abc.xyz"})
            assert response.status_code == 404
    finally:
        try:
            os.remove(os.environ["M14404_DB_PATH"])
        except FileNotFoundError:
            pass


def test_www_subdomain_template_caching(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from M14404.subdomains.www import WwwSubdomainHandler

    # Reset internal cache
    WwwSubdomainHandler._html_template = None

    # Mock pathlib.Path.read_text
    read_text_calls = 0
    import pathlib

    original_read_text = pathlib.Path.read_text

    def mock_read_text(*args: Any, **kwargs: Any) -> str:
        nonlocal read_text_calls
        read_text_calls += 1
        return str(original_read_text(*args, **kwargs))

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read_text)

    # First request should trigger read
    response1 = client.get("/", headers={"Host": "www.abc.xyz"})
    assert response1.status_code == 200
    assert read_text_calls == 1

    # Second request should not trigger read
    response2 = client.get("/", headers={"Host": "www.abc.xyz"})
    assert response2.status_code == 200
    assert read_text_calls == 1


def test_websocket_exception_handling(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from starlette.websockets import WebSocketDisconnect

    class MockError(Exception):
        pass

    import M14404.subdomains.www as www_module

    original_insert_ws_log = www_module._insert_ws_log
    call_count = 0

    async def mock_insert_ws_log(payload: Any) -> int:
        nonlocal call_count
        call_count += 1
        if call_count > 1:  # first call is the handshake; crash on the message
            raise MockError("Simulated random crash")
        return int(await original_insert_ws_log(payload))

    monkeypatch.setattr(www_module, "_insert_ws_log", mock_insert_ws_log)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/ws/test?x=1", headers={"Host": "www.abc.xyz"}
        ) as ws:
            ws.receive_text()  # Receive handshake id
            ws.send_text("ping")  # triggers _insert_ws_log for message → crashes
            ws.receive_text()  # should hit the closed connection

    assert exc_info.value.code == 1011
