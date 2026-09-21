# SG-Gateway 23.01 — GitHub commands

Stable channel: `stable-02301`.

> **Важно: прямое обновление 22.08 → 23.01 временно не поддерживается.**
> Из-за перехода 23.01 на Single Edge 443 и различий старых server runtime, включая ранние варианты Mihomo в 22.08, переход выполняется через переносимый **Clients, Keys & HTTPS** backup и чистую установку. Команда Update ниже предназначена только для серверов, на которых уже установлена 23.01.

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
