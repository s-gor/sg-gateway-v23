from pathlib import Path

path = Path("tools/single_edge_apply.py")
text = path.read_text(encoding="utf-8")

helper = '''\n\ndef replace_first_of_two(path: str, old: str, new: str) -> None:\n    p = Path(path)\n    text = p.read_text(encoding="utf-8")\n    count = text.count(old)\n    if count != 2:\n        raise SystemExit(f"{path}: expected two occurrences before first replacement, got {count}: {old[:100]!r}")\n    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\\n")\n'''
marker = "\n\ndef regex_once(path: str, pattern: str, replacement: str, *, flags: int = 0) -> None:\n"
if marker not in text:
    raise SystemExit("patcher helper insertion marker missing")
text = text.replace(marker, helper + marker, 1)

for old, new in (
    (
        "replace_once(path, 'f\"    port: {settings[\\'mieru_port\\']}\"', 'f\"    port: {MIERU_TCP_INTERNAL_PORT}\"')",
        "replace_first_of_two(path, 'f\"    port: {settings[\\'mieru_port\\']}\"', 'f\"    port: {MIERU_TCP_INTERNAL_PORT}\"')",
    ),
    (
        "replace_once(path, 'f\"    port: {settings[\\'anytls_port\\']}\"', 'f\"    port: {ANYTLS_TCP_INTERNAL_PORT}\"')",
        "replace_first_of_two(path, 'f\"    port: {settings[\\'anytls_port\\']}\"', 'f\"    port: {ANYTLS_TCP_INTERNAL_PORT}\"')",
    ),
    (
        "replace_once(path, 'f\"    port: {settings[\\'tuic_port\\']}\"', 'f\"    port: {TUIC_UDP_INTERNAL_PORT}\"')",
        "replace_first_of_two(path, 'f\"    port: {settings[\\'tuic_port\\']}\"', 'f\"    port: {TUIC_UDP_INTERNAL_PORT}\"')",
    ),
):
    if text.count(old) != 1:
        raise SystemExit(f"patcher replacement marker count for {old!r}: {text.count(old)}")
    text = text.replace(old, new, 1)

# Scope the two sing-box listeners to the actual renderer, not the apply function.
text = text.replace(
    'start = text.index("def _apply_singbox()")',
    'start = text.index("def _render_singbox_config(")',
)
text = text.replace(
    'end = text.index("def apply_split_mihomo_singbox_runtime()")',
    'end = text.index("def _sync_singbox_client_configs(")',
)

path.write_text(text, encoding="utf-8", newline="\n")
