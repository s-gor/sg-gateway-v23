from __future__ import annotations

# Stable client-facing edge. Internal ports are never exported.
PUBLIC_TCP_PORT = 443
PUBLIC_UDP_PORT = 443

# TCP private backends.
REALITY_TCP_INTERNAL_PORT = 10443
XHTTP_REALITY_INTERNAL_PORT = 10444
XHTTP_TLS_INTERNAL_PORT = 10445
NAIVEPROXY_INTERNAL_PORT = 10447
MIERU_TCP_INTERNAL_PORT = 10448
ANYTLS_TCP_INTERNAL_PORT = 10449

# UDP private backends behind sg-gateway-udp-edge.service.
AWG31_UDP_INTERNAL_PORT = 10451
HYSTERIA2_UDP_INTERNAL_PORT = 10452
TUIC_UDP_INTERNAL_PORT = 10453

# Compatibility aliases describe public client ports, not backend binds.
AWG31_UDP_PORT = PUBLIC_UDP_PORT
HYSTERIA2_DEFAULT_PORT = PUBLIC_UDP_PORT

XHTTP_REALITY_DEFAULT_SNI = "www.cloudflare.com"
XHTTP_REALITY_DEFAULT_TARGET = "www.cloudflare.com:443"
ANYTLS_ALPN = "sg-anytls"
