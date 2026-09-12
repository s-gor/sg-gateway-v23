# SG-Gateway

**Лёгкая и быстрая веб-панель для личного и семейного VPN.**

> **Один сервер. Одна панель. Семейный VPN без серверной акробатики.**

![Версия](https://img.shields.io/badge/version-0.1.0--023.01-3b82f6)
![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04-E95420?logo=ubuntu&logoColor=white)
![Xray](https://img.shields.io/badge/Xray-supported-2563EB)
![AmneziaWG](https://img.shields.io/badge/AWG-3.1-6D5BD0)
![Mihomo](https://img.shields.io/badge/Mihomo-supported-8B5CF6)
![sing-box](https://img.shields.io/badge/sing--box-supported-0EA5E9)
![HTTPS](https://img.shields.io/badge/HTTPS-Let%27s_Encrypt-003A70?logo=letsencrypt&logoColor=white)
![Status](https://img.shields.io/badge/status-23.01--DEV-F59E0B)

> **Текущая линия разработки — SG-Gateway 0.1.0-023.01.** Канал: `dev-02301`.

SG-Gateway 23.01 начинается с проверенной рабочей runtime-базы предыдущей линии, но ведётся в отдельном репозитории и с отдельным CI-контрактом. Текущий активный AmneziaWG runtime — **AWG 3.1**. AWG 2.0 и AWG 3.0 не являются активными профилями новой линии; их данные могут сохраняться только там, где это необходимо для безопасной миграции или восстановления старых backup.

Поддерживаемая база включает Xray Reality TCP, XHTTP Reality, XHTTP TLS, Hysteria2 с Salamander/Gecko, NaiveProxy, Mihomo/Mieru, Clients и subscriptions, Routing, Backup/Restore, Maintenance, диагностику и безопасный Update/rollback.

## Быстрые команды

### Clean Install — только новый Ubuntu 24.04 сервер

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/install-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```

Clean Install блокируется, если SG-Gateway уже установлен. Для существующего сервера используйте отдельный Update.

### Update — существующий SG-Gateway 23.01

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/update-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```

### Full Uninstall

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/uninstall-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```

Подтверждение удаления: `DELETE SG-GATEWAY`.

Полный набор команд: **[deploy/GITHUB-COMMANDS.md](deploy/GITHUB-COMMANDS.md)**.

## Архитектурная линия 23.01

Чистый baseline 23.01 фиксируется до начала следующего архитектурного этапа. Работа над Single Edge 443 ведётся отдельно в `feat/2301-single-edge-443`; она не должна попадать в `main` до собственных тестов и проверки на тестовом сервере.

Целевое направление Single Edge: единая внешняя TCP-точка 443 с L4/SNI-маршрутизацией, passthrough для Reality и внутренними loopback listeners для совместимых TCP/TLS сервисов. UDP рассматривается отдельно: AWG 3.1 остаётся владельцем UDP 443, а Hysteria2 на первом этапе использует отдельный UDP-порт.

## Основные возможности

SG-Gateway устанавливается на один самостоятельный Ubuntu 24.04 VPS/EC2 и превращает его в готовый VPN-шлюз с веб-интерфейсом.

Панель управляет клиентами и устройствами, персональными subscriptions, QR/exports, Connections, Routing/GeoFiles, HTTPS/Let's Encrypt, backup/restore, diagnostics и безопасными обновлениями.

### Clients

Клиент может иметь несколько устройств. Для каждого устройства сохраняются собственные credentials, ссылки, QR-коды и персональная SG Client subscription.

### Routing и GeoFiles

Доступны прямой выход через SG-Gateway, WARP IPv4/IPv6, блокировка, готовые и пользовательские правила. GeoFiles можно проверять и обновлять из панели.

### HTTPS и безопасность

HTTPS включается из `Security`. Панель проверяет DNS, получает сертификат Let's Encrypt, валидирует Nginx и проверяет итоговый endpoint. Привилегированные операции выполняет отдельный HostD.

### Backup / Restore

Поддерживаются обычные и полные резервные копии. Перед критическими переключениями создаётся safety backup; при ошибке применяется rollback.

### Update

Clean Install и Update разделены. Update не запускает повторный полный installer, а обновляет исходники по безопасной транзакционной схеме и проверяет состояние сервера после переключения.

## Документация

- **[Техническое устройство SG-Gateway](docs/TECHNICAL.md)**
- **[Начало работы](docs/README.md)**
- **[Установка и обновление](docs/INSTALLATION.md)**
- **[Руководство пользователя](docs/USER-GUIDE.md)**
- **[Connections и клиентские профили](docs/CONNECTIONS.md)**
- **[Routing и GeoFiles](docs/ROUTING.md)**
- **[HTTPS и безопасность](docs/security.md)**
- **[Maintenance и диагностика](docs/MAINTENANCE.md)**
- **[Полное удаление](docs/UNINSTALL.md)**

**Один сервер. Одна панель. Нормальный выход в интернет.**
