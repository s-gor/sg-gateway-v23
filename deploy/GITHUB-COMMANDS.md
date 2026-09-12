# SG-Gateway 0.1.0-022.08 · команды GitHub

Канал: `dev-02301`. Поддерживается Ubuntu 24.04.

Проверенный production source: `d87663737746b91237098342f9c6c1d37856c88c`.

## Чистая установка

Только для нового сервера без установленного SG-Gateway. Clean Install закреплён на точный проверенный source commit:

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/d87663737746b91237098342f9c6c1d37856c88c/deploy/install-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 SG_GATEWAY_SOURCE_COMMIT=d87663737746b91237098342f9c6c1d37856c88c bash
```

## Обновление

Для уже установленного SG-Gateway 22.08. Перед переключением кода Update создаёт Safety Backup и проверяет panel, HostD, HTTPS/Nginx, Clients/credentials и runtime. При критической ошибке выполняется rollback.

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/update-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```

## Полное удаление

Удаляются приложение, конфигурация, база, резервные копии, SG-службы и установленные SG runtime. Системные пакеты Ubuntu остаются установленными.

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/uninstall-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```

Для подтверждения необходимо ввести точно:

```text
DELETE SG-GATEWAY
```

## Текущий AmneziaWG runtime в 22.08

Активный AmneziaWG-профиль текущей линии — **AWG 3.1**. Legacy runtime AWG 2.0 и AWG 3.0 выведен из эксплуатации и очищается штатной maintenance/update логикой. Сохранённые legacy database records и credentials не удаляются этим runtime cleanup вслепую.