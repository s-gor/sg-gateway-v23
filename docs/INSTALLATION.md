# Установка и обновление SG-Gateway 23.01

## Требования

- чистая Ubuntu Server 24.04;
- root-доступ через `sudo`;
- публичный IPv4.

SG-Gateway устанавливается нативно и не требует Docker.

## Clean Install 23.01

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/install-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Clean Install предназначен только для сервера без установленного SG-Gateway.

## Update внутри линии 23.01

Для уже установленной 23.01:

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/update-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Updater создаёт Safety Backup, проверяет candidate и выполняет rollback при критической ошибке.

### Что именно обновляет Update

Update внутри линии 23.01 предназначен для безопасного обновления кода SG-Gateway и совместимых миграций. Он не запускает полный installer повторно и не должен автоматически переустанавливать VPN cores или полностью заменять уже работающий core runtime.

Это означает:

- код панели и SG-Gateway обновляется;
- перед изменением создаётся Safety Backup;
- candidate и итоговое состояние проверяются;
- при критической ошибке выполняется rollback;
- Xray/Mihomo/sing-box/AWG не считаются автоматически «обновлёнными» только потому, что выполнена команда Update;
- изменения низкоуровневого systemd/runtime отдельного ядра могут требовать отдельной процедуры либо Clean Install.

Актуальный Clean Install 23.01 уже включает Mihomo systemd unit с `AF_NETLINK`, необходимым для route lookup. Обычный Update намеренно не подменяет существующий Mihomo runtime только ради такого изменения.

## Переход 22.08 → 23.01

**Прямой in-place Update с 22.08 на 23.01 не поддерживается.**

Причина — архитектурный переход на Single Edge 443: публичные TCP/UDP подключения переводятся на общий edge, а backend listeners и часть server runtime становятся внутренними. Кроме того, ранние установки 22.08 могли содержать другой вариант Mihomo runtime. Чтобы не переносить старую runtime-схему в 23.01, используйте чистую миграцию.

### 1. Сохранить клиентов, ключи и HTTPS

В 22.08 откройте **Maintenance → Backups → Clients, Keys & HTTPS** и создайте переносимый backup. Скачайте файл `SG-Gateway-CLIENTS-*.sgbackup` на локальный компьютер до удаления сервера.

Этот профиль сохраняет:

- клиентов и устройства;
- credentials, ключи, UUID и пароли;
- SG/Router subscription-данные;
- активный HTTPS-домен;
- сертификат и private key.

Он не переносит Routing, WARP, настройки протоколов, старые listener/ports и server runtime.

### 2. Удалить 22.08

Используйте штатную Full Uninstall команду именно вашей установленной линии 22.08. Перед подтверждением убедитесь, что `.sgbackup` уже скачан с сервера на ваш компьютер.

### 3. Установить 23.01

После полного удаления выполните Clean Install 23.01 командой выше.

### 4. Вернуть клиентов и сертификаты

В новой панели 23.01 откройте **Maintenance → Backups → Clients, Keys & HTTPS**:

1. выберите сохранённый `.sgbackup`;
2. нажмите **«Проверить backup»**;
3. после успешной проверки нажмите **«Восстановить»**.

Restore возвращает клиентов, их реквизиты и активную HTTPS-идентичность. Перед изменением новая система создаёт страховочную копию.

### 5. Включить протоколы заново

После Restore откройте **Connections**, включите необходимые протоколы и примените конфигурацию. Проверьте subscriptions и реальные подключения клиентов. Routing/WARP и другие server-side настройки настраиваются заново.

## Full Uninstall 23.01

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/uninstall-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Подтверждение:

```text
DELETE SG-GATEWAY
```
