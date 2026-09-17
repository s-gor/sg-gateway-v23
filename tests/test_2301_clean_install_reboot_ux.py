from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_quiet_function() -> str:
    source = (ROOT / "deploy" / "install-from-github.sh").read_text(encoding="utf-8")
    marker = "run_quiet() {"
    start = source.index(marker)
    end = source.index("\nrequire_supported_ubuntu() {", start)
    return source[start:end]


def test_reboot_required_is_an_expected_handoff_not_an_error(tmp_path: Path) -> None:
    bootstrap_log = tmp_path / "bootstrap.log"
    function_source = _run_quiet_function()
    harness = f'''#!/usr/bin/env bash
GREEN=""
RED=""
YELLOW=""
RESET=""
BOOTSTRAP_LOG={bootstrap_log!s!r}
CURRENT_BOOTSTRAP_LABEL=""
{function_source}
if run_quiet "Подготовка 4/6 · Обновление Ubuntu" bash -c 'printf "APT-NOISE\\n"; exit 10'; then
  rc=0
else
  rc=$?
fi
printf '__RC__=%s\\n' "$rc"
'''

    completed = subprocess.run(
        ["bash", "-c", harness],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0
    assert "__RC__=10" in output
    assert "[SG-Gateway] [НУЖНА ПЕРЕЗАГРУЗКА] Подготовка 4/6 · Обновление Ubuntu" in output
    assert "sudo reboot" in output
    assert "После перезагрузки снова войдите на сервер и запустите ту же команду установки." in output
    assert "[ОШИБКА]" not in output
    assert "Причина:" not in output
    assert "APT-NOISE" not in output
