from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any

from app.connections.settings import get_connection_settings, update_connection_settings
from app.security.tls import overview as tls_overview
from app.single_edge import (
    HYSTERIA2_DEFAULT_PORT,
    REALITY_TCP_INTERNAL_PORT,
    XHTTP_REALITY_DEFAULT_SNI,
    XHTTP_REALITY_DEFAULT_TARGET,
    XHTTP_REALITY_INTERNAL_PORT,
    XHTTP_TLS_INTERNAL_PORT,
)
from app.xray.encryption import client_value_ready
from app.xray.salamander import (
    GECKO_MINIMUM_VERSION,
    GECKO_MODE,
    SALAMANDER_MINIMUM_VERSION,
    SALAMANDER_MODE,
    SALAMANDER_MODE_NONE,
    SalamanderError,
    ensure_base_has_no_salamander,
    generate_password,
    minimum_version_for_mode,
    normalise_mode,
    password_ready,
    safe_status,
    validate_password,
    version_supported as salamander_version_supported,
)
from app.xray.settings_transactions import (
    SettingsTransaction,
    begin as begin_settings_transaction,
    commit as commit_settings_transaction,
    pending as pending_settings_transaction,
    rollback as rollback_settings_transaction,
)
