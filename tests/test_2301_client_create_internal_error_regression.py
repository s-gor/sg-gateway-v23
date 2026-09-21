from __future__ import annotations

import app.main as main


def _app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SG_GATEWAY_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("SG_GATEWAY_SECRET_KEY", "client-create-regression")
    monkeypatch.setenv("SG_GATEWAY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SG_GATEWAY_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("SG_GATEWAY_PUBLIC_ADDRESS", "203.0.113.10")
    monkeypatch.setenv("SG_GATEWAY_COUNTRY_CODE", "fr")
    app = main.create_app()
    app.config.update(TESTING=True)
    http = app.test_client()
    http.post("/login", data={"password": "secret"})
    return http


def test_client_create_requires_stabilized_runtime(tmp_path, monkeypatch):
    http = _app(tmp_path, monkeypatch)
    calls: list[bool] = []

    monkeypatch.setattr(main, "create_client", lambda **kwargs: 77)
    monkeypatch.setattr(
        main,
        "apply_clients_runtime",
        lambda *, stabilize=False: calls.append(stabilize)
        or {"ok": True, "message": "applied"},
    )

    response = http.post(
        "/clients",
        data=[
            ("name", "Regression"),
            ("protocols", "xray_xhttp_reality"),
            ("protocols", "mihomo"),
            ("protocols", "naiveproxy"),
        ],
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/clients/77")
    assert calls == [True]


def test_unexpected_runtime_error_is_rolled_back_without_flask_500(tmp_path, monkeypatch):
    http = _app(tmp_path, monkeypatch)
    deleted: list[int] = []
    calls: list[bool] = []

    monkeypatch.setattr(main, "create_client", lambda **kwargs: 88)

    def apply(*, stabilize=False):
        calls.append(stabilize)
        if stabilize:
            raise TypeError("simulated protocol bootstrap signature failure")
        return {"ok": True, "message": "previous runtime restored"}

    monkeypatch.setattr(main, "apply_clients_runtime", apply)
    monkeypatch.setattr(main, "delete_client", lambda client_id: deleted.append(client_id) or True)
    monkeypatch.setattr(main, "log_operation", lambda *args, **kwargs: None)

    response = http.post(
        "/clients",
        data=[
            ("name", "Regression"),
            ("protocols", "xray_xhttp_reality"),
            ("protocols", "mihomo"),
            ("protocols", "naiveproxy"),
        ],
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/clients")
    assert deleted == [88]
    assert calls == [True, False]


def test_naiveproxy_wrapper_still_forwards_stabilize_keyword():
    source = (
        __import__('pathlib').Path(__file__).resolve().parents[1]
        / "app"
        / "naiveproxy"
        / "integration.py"
    ).read_text(encoding="utf-8")

    assert "def apply_clients_runtime(*, stabilize: bool = False) -> dict:" in source
    assert "return original(stabilize=True)" in source
