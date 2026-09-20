from __future__ import annotations

import inspect

import app.main as main


def test_global_template_context_uses_cached_health_only():
    source = inspect.getsource(main.create_app)
    start = source.index("@app.context_processor")
    end = source.index("@app.get", start)
    block = source[start:end]

    assert "panel_health = cached_health_summary()" in block
    assert "panel_health = health_summary()" not in block
