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
![Status](https://img.shields.io/badge/status-23.01--STABLE-22C55E)

> **Текущая стабильная линия — SG-Gateway 0.1.0-023.01.** Канал: `stable-02301`.

SG-Gateway 23.01 начинается с проверенной рабочей runtime-базы предыдущей линии, но ведётся в отдельном репозитории и с отдельным CI-контрактом. Текущий активный AmneziaWG runtime — **AWG 3.1**. AWG 2.0 и AWG 3.0 не являются активными профилями новой линии; их данные могут сохраняться только там, где это необходимо для безопасной миграции или восстановления старых backup.

Поддерживаемая база включает Xray Reality TCP, XHTTP Reality, XHTTP TLS, Hysteria2 с Salamander/Gecko, NaiveProxy, Mihomo/Mieru, Clients и subscriptions, Routing, Backup/Restore, Maintenance, диагностику и безопасный Update/rollback.

> [!IMPORTANT]
> **Прямой Update SG-Gateway 22.08 → 23.01 не поддерживается.**
> 23.01 использует другую транспортную архитектуру: публичный трафик сводится к Single Edge на 443, backend listeners становятся внутренними, а часть server runtime отличается от 22.08. Для перехода сохраните **Clients, Keys & HTTPS**, удалите 22.08 и выполните Clean Install 23.01. Команда Update ниже предназначена только для уже установленной 23.01.

## Быстрые команды

### Clean Install — только новый Ubuntu 24.04 сервер

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/install-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Clean Install блокируется, если SG-Gateway уже установлен. Для перехода с 22.08 не используйте Update: сначала сохраните переносимый backup клиентов/ключей/HTTPS, затем удалите 22.08 и установите 23.01 начисто.

### Update — только существующий SG-Gateway 23.01

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/update-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Обычный Update 23.01 — это **безопасное обновление панели и кода SG-Gateway**, а не повторный Clean Install. Он создаёт Safety Backup, проверяет candidate, применяет совместимые миграции и выполняет rollback при критической ошибке.

> [!NOTE]
> Обычный Update **не переустанавливает VPN cores и не заменяет существующий core runtime целиком**. Исправления, которые относятся именно к systemd-unit или низкоуровневому runtime отдельного ядра, могут требовать Clean Install либо отдельной процедуры обновления ядра. Например, актуальный Clean Install уже содержит исправленный Mihomo unit с доступом к `AF_NETLINK`.

### Full Uninstall

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/uninstall-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Подтверждение удаления: `DELETE SG-GATEWAY`.

Полный набор команд: **[deploy/GITHUB-COMMANDS.md](deploy/GITHUB-COMMANDS.md)**.


## Как выбрать способ обновления

| Исходное состояние | Что делать |
| --- | --- |
| Чистый Ubuntu 24.04 без SG-Gateway | **Clean Install 23.01** |
| Уже установлен SG-Gateway 23.01 | **Update 23.01** |
| SG-Gateway 22.08 | **Backup Clients, Keys & HTTPS → Full Uninstall → Clean Install 23.01 → Restore** |
| Нужно заменить VPN core/runtime, а не только код панели | Использовать отдельную core/runtime процедуру или Clean Install; обычный Update это намеренно не делает |

## Переход с 22.08 на 23.01

Для 22.08 используется только чистая миграция:

1. В старой панели откройте **Maintenance → Backups**.
2. В блоке **Clients, Keys & HTTPS** нажмите **«Создать Clients, Keys & HTTPS»**.
3. Скачайте полученный файл `SG-Gateway-CLIENTS-*.sgbackup` на свой компьютер. Эта копия переносит клиентов, устройства, ключи, UUID, пароли, персональные subscriptions и активную HTTPS-идентичность: домен, сертификат и private key.
4. Удалите 22.08 штатной командой Full Uninstall.
5. Установите 23.01 командой Clean Install.
6. В новой панели снова откройте **Maintenance → Backups**, выберите сохранённый `.sgbackup`, нажмите **«Проверить backup»**, затем **«Восстановить»**.
7. После Restore вручную включите нужные протоколы в **Connections** и проверьте клиентские подключения.

Важно: профиль **Clients, Keys & HTTPS** не переносит Routing, WARP, настройки протоколов, старые listener/ports и server runtime. Это намеренно: 23.01 строит новый Single Edge runtime заново, а клиентские credentials и HTTPS возвращаются из переносимого backup.

## Архитектурная линия 23.01

SG-Gateway 23.01 опубликован в стабильном канале `stable-02301`. Следующая архитектурная работа, включая Cascade, ведётся отдельно от стабильной версии.

Single Edge 23.01 использует общий публичный порт 443: TCP/443 маршрутизируется через L4/SNI edge, а UDP/443 — через отдельный SG-Gateway UDP edge к приватным backend. Внутренние listeners не публикуются напрямую наружу.

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

Clean Install и Update разделены намеренно. Update внутри 23.01 обновляет код SG-Gateway по безопасной транзакционной схеме, создаёт Safety Backup, проверяет candidate и итоговое состояние сервера, а при критической ошибке выполняет rollback.

Update не следует воспринимать как «переустановить всё». Он не должен самовольно заменять VPN cores, сертификаты или существующий низкоуровневый runtime. Это сохраняет рабочую серверную конфигурацию и снижает риск неожиданной поломки уже работающих протоколов.

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
