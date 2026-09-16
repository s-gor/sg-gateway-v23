# Connections и клиентские профили

## Single Edge 23.01

Все клиентские подключения SG-Gateway 23.01 используют внешний порт `443`. Внутренние runtime-порты служат только backend-слою и не выдаются клиентам. Панель управления остаётся отдельно на TCP `63443`.

TCP `443` разделяют Reality, XHTTP/Reality, XHTTP/TLS, NaiveProxy, AnyTLS и Mieru/TCP. UDP `443` принимает `sg-gateway-udp-edge` и направляет трафик во внутренние backend-ы AWG3.1, Hysteria2 и TUIC v5.

Для совместной работы Hysteria2 и TUIC на одном UDP `443` Hysteria2 использует управляемый Salamander (или явно выбранный Gecko). Plain QUIC остаётся за TUIC, поэтому dispatcher может маршрутизировать оба протокола детерминированно.

## AmneziaWG 3.1

AWG3.1 выдаётся клиентам на внешнем UDP `443`. Серверный runtime работает за UDP edge на отдельном внутреннем backend-порту. Настройки включают адрес, DNS, ключи и параметры HeaderProtection; для каждого устройства создаётся отдельная клиентская конфигурация.

## Xray

### VLESS Reality TCP

TCP/Reality-профиль с XTLS Vision. Клиентский endpoint использует внешний TCP `443`.

### VLESS XHTTP Reality

Клиентская ссылка содержит XHTTP mode, VLESS Encryption и XMUX для РФ. Внешний endpoint использует TCP `443`; внутренний Xray listener клиенту не показывается.

### VLESS XHTTP TLS

Требует готового HTTPS-домена. Клиентская ссылка содержит XHTTP mode, VLESS Encryption и XMUX-профиль. Внешний endpoint использует TCP `443`.

### Hysteria 2

Использует внешний UDP `443` через общий UDP edge. При активном Single Edge Hysteria2 нормализуется в managed Salamander, если obfs не задан; Gecko сохраняется, если выбран явно. Секрет obfs хранится согласованно между серверным runtime и клиентским экспортом.

## XMUX для РФ

Профиль применяется к обоим XHTTP-профилям:

```json
{
  "maxConcurrency": 0,
  "maxConnections": 6,
  "cMaxReuseTimes": 0,
  "hMaxRequestTimes": "600-900",
  "hMaxReusableSecs": "1800-3000",
  "hKeepAlivePeriod": 0
}
```

Эти значения добавляются в `extra.xmux` клиентских ссылок и не записываются в серверный inbound.

## Mihomo и sing-box

- Mieru обслуживается Mihomo;
- AnyTLS и TUIC v5 обслуживаются отдельным sing-box;
- клиентские endpoints используют внешний порт `443`, а runtime listeners остаются внутренними.

Каждый движок имеет собственное runtime-состояние, а панель объединяет их результаты в одном интерфейсе. Выключенный профиль не выдаётся клиентам как доступный, при этом сохранённые реквизиты остаются в базе для повторного включения.
