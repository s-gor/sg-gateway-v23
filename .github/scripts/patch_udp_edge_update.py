from pathlib import Path

path = Path("deploy/update-from-github-core.sh")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match, got {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)


replace_once(
    'AWG31_UNIT="$(system_path /etc/systemd/system/sg-gateway-awg31.service)"\nAWG3_ROOT="$PREFIX/awg3"',
    'AWG31_UNIT="$(system_path /etc/systemd/system/sg-gateway-awg31.service)"\nUDP_EDGE_SERVICE="sg-gateway-udp-edge.service"\nUDP_EDGE_UNIT="$(system_path /etc/systemd/system/sg-gateway-udp-edge.service)"\nAWG3_ROOT="$PREFIX/awg3"',
)

replace_once(
    '    "$PANEL_UNIT"\n    "$HOSTD_UNIT"\n  )',
    '    "$PANEL_UNIT"\n    "$HOSTD_UNIT"\n    "$UDP_EDGE_UNIT"\n  )',
)

replace_once(
    '    etc/systemd/system/sg-gateway-awg3.service \\\n    etc/systemd/system/sg-gateway-awg31.service; do',
    '    etc/systemd/system/sg-gateway-awg3.service \\\n    etc/systemd/system/sg-gateway-awg31.service \\\n    etc/systemd/system/sg-gateway-udp-edge.service; do',
)

replace_once(
    '  systemctl stop "$PANEL_SERVICE" "$HOSTD_SERVICE" "$AWG3_SERVICE" "$AWG31_SERVICE" >/dev/null 2>&1 || true',
    '  systemctl stop "$PANEL_SERVICE" "$HOSTD_SERVICE" "$AWG3_SERVICE" "$AWG31_SERVICE" "$UDP_EDGE_SERVICE" >/dev/null 2>&1 || true',
)

replace_once(
    '    "$AWG3_UNIT" \\\n    "$AWG31_UNIT"; do',
    '    "$AWG3_UNIT" \\\n    "$AWG31_UNIT" \\\n    "$UDP_EDGE_UNIT"; do',
)

replace_once(
    '    sg-gateway-singbox.service "$NAIVE_SERVICE" "$HOSTD_SERVICE" "$PANEL_SERVICE"; do',
    '    sg-gateway-singbox.service "$NAIVE_SERVICE" "$UDP_EDGE_SERVICE" "$HOSTD_SERVICE" "$PANEL_SERVICE"; do',
)

replace_once(
    '  install -m 0644 "$PREFIX/deploy/sg-gateway-awg3.service" "$AWG3_UNIT"\n  systemctl daemon-reload',
    '  install -m 0644 "$PREFIX/deploy/sg-gateway-awg3.service" "$AWG3_UNIT"\n\n  [[ -f "$PREFIX/deploy/sg-gateway-udp-edge.service" ]] || \\\n    fail "deployed UDP edge systemd unit is missing"\n  install -m 0644 "$PREFIX/deploy/sg-gateway-udp-edge.service" "$UDP_EDGE_UNIT"\n  systemctl daemon-reload',
)

replace_once(
    '  cmp -s "$PREFIX/deploy/sg-gateway-awg3.service" "$AWG3_UNIT" || \\\n    fail "installed AWG3 systemd unit does not match deployed source"\n\n  verify_runtime_states_unchanged',
    '  cmp -s "$PREFIX/deploy/sg-gateway-awg3.service" "$AWG3_UNIT" || \\\n    fail "installed AWG3 systemd unit does not match deployed source"\n  cmp -s "$PREFIX/deploy/sg-gateway-udp-edge.service" "$UDP_EDGE_UNIT" || \\\n    fail "installed UDP edge systemd unit does not match deployed source"\n\n  verify_runtime_states_unchanged',
)

ensure_fn = r'''ensure_udp_edge_service() {
  [[ -f "$PREFIX/deploy/sg-gateway-udp-edge.service" ]] || \
    fail "deployed UDP edge systemd unit is missing"
  cmp -s "$PREFIX/deploy/sg-gateway-udp-edge.service" "$UDP_EDGE_UNIT" || \
    fail "installed UDP edge systemd unit does not match deployed source"

  systemctl daemon-reload
  systemctl enable --now "$UDP_EDGE_SERVICE"
  # enable --now does not restart an already-running dispatcher after source
  # replacement, so restart explicitly to guarantee the new Python code is live.
  systemctl restart "$UDP_EDGE_SERVICE"
  systemctl is-active --quiet "$UDP_EDGE_SERVICE" || \
    fail "UDP edge service failed to start"
}

'''
replace_once('main() {\n', ensure_fn + 'main() {\n')

replace_once(
    '  run_stage 8 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration\n\n  # Repair a runtime',
    '  run_stage 8 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration\n  run_stage 9 "UDP/443 edge service rollout" ensure_udp_edge_service\n\n  # Repair a runtime',
)

path.write_text(text, encoding="utf-8", newline="\n")
print("patched UDP edge update rollout")
