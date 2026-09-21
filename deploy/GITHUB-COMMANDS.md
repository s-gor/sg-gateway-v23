# SG-Gateway 23.01 — GitHub commands

Stable channel: `stable-02301`.

> **Важно: прямой Update 22.08 → 23.01 не поддерживается.**
> Из-за перехода 23.01 на Single Edge 443 и различий server runtime переход выполняется через переносимый **Clients, Keys & HTTPS** backup и чистую установку. Команда Update ниже предназначена только для серверов, на которых уже установлена 23.01.

## Clean Install

Только для чистого сервера:

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/install-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

## Update

Только для существующей установки SG-Gateway 23.01:

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/update-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Не используйте эту команду для прямого перехода с 22.08.

### Что делает обычный Update 23.01

Update внутри линии 23.01 обновляет код SG-Gateway без повторного запуска полного installer. Перед изменением создаётся Safety Backup, candidate проходит проверки, после применения проверяется состояние панели и управляемых компонентов; при критической ошибке выполняется rollback.

Обычный Update **не является обновлением всех VPN cores** и не должен самовольно заменять существующий низкоуровневый runtime. Он не переустанавливает Xray/Mihomo/sing-box/AWG как полный Clean Install.

Если исправление относится именно к core binary, systemd-unit или другому runtime-компоненту, используйте отдельную процедуру core/runtime update либо Clean Install. Актуальный Clean Install 23.01 уже содержит Mihomo service с разрешённым `AF_NETLINK`, необходимым для корректного route lookup.

### Быстрый выбор

- новый чистый Ubuntu 24.04 → **Clean Install**;
- уже установленная 23.01 → **Update**;
- 22.08 → **Clients, Keys & HTTPS backup → Full Uninstall → Clean Install 23.01 → Restore**;
- требуется заменить core/runtime → **не обычный Update**.

## Full Uninstall

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/stable-02301/deploy/uninstall-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=stable-02301 bash
```

Подтверждение:

```text
DELETE SG-GATEWAY
```

## Как перейти с 22.08 на 23.01

1. На 22.08 откройте **Maintenance → Backups**.
2. В блоке **Clients, Keys & HTTPS** создайте переносимый backup.
3. Скачайте файл `SG-Gateway-CLIENTS-*.sgbackup` на свой компьютер.
4. Удалите 22.08 штатным Full Uninstall.
5. Выполните Clean Install 23.01.
6. В 23.01 откройте **Maintenance → Backups**, выберите сохранённый файл, нажмите **«Проверить backup»**, затем **«Восстановить»**.
7. В **Connections** заново включите требуемые протоколы и проверьте подключения.

Переносимый backup сохраняет клиентов, устройства, credentials, UUID, пароли, subscription-данные и активный HTTPS: домен, сертификат и private key. Он намеренно не переносит Routing, WARP, настройки протоколов, старые listener/ports и server runtime.
