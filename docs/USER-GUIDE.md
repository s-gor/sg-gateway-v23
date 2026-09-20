# Руководство пользователя SG-Gateway

Это краткий маршрут по панели в том же порядке, что и встроенная справка.

## System

Показывает ресурсы сервера, версии и состояние основных служб. С этой страницы удобно начинать проверку после установки или изменений.

![System](screenshots/system.png)

## Clients

Клиент — логическая запись пользователя. Устройство — отдельный набор реквизитов доступа.

Рабочий порядок:

1. создать клиента;
2. добавить устройство;
3. выбрать доступные подключения;
4. применить изменения;
5. получить ссылку, QR-код, файл конфигурации или SG Client subscription;
6. при необходимости временно отключить устройство или клиента.

| Список клиентов | Карточка клиента |
| --- | --- |
| ![Список клиентов](screenshots/clients.png) | ![Карточка клиента](screenshots/client-card.png) |

| Добавление устройства | Выбор подключений |
| --- | --- |
| ![Добавление устройства](screenshots/add-device.png) | ![Выбор подключений](screenshots/device-connections.png) |

## Connections

Здесь настраиваются серверные подключения AmneziaWG, Xray и дополнительные протоколы.

![Connections](screenshots/connections.png)

### Xray

Поддерживаются VLESS Reality TCP, VLESS XHTTP Reality, VLESS XHTTP TLS и Hysteria 2.

![Xray](screenshots/xray-settings.png)

### AmneziaWG

AmneziaWG использует отдельный профиль сервера и индивидуальные реквизиты устройств.

![AmneziaWG](screenshots/amneziawg.png)

### Mieru, AnyTLS и TUIC v5

Mieru обслуживается Mihomo, AnyTLS и TUIC v5 — sing-box.

![Дополнительные протоколы](screenshots/extra-protocols.png)

## Outbounds

Outbounds определяют, **куда сервер может отправить трафик**. В 23.01 доступны SG-Gateway IPv4/IPv6, WARP IPv4/IPv6, Block, а также внешние SOCKS5 и HTTP CONNECT.

Внешний proxy добавляется в **Outbounds → External outbounds**. После успешной Xray-проверки он появляется как вариант действия в Routing.

Из двух и более внешних proxy можно создать группу:
- **Round Robin** — распределение соединений по очереди;
- **Random** — случайный выбор;
- **Failover** — основной + резервный выход через Xray Observatory/fallback.

![WARP](screenshots/warp-outbound.png)

## Routing и GeoFiles

Routing определяет, **какой трафик через какой outbound пойдёт**. Основные правила включают локальную сеть, заблокированные ресурсы, рекламу и финальное действие для остального трафика.

Рабочий порядок один и тот же: **изменить → Проверить → изучить Фактические правила candidate → Применить → проверить реальный трафик**.

IPv4 и IPv6 не имеют скрытого fallback. SG-Gateway IPv4, SG-Gateway IPv6, WARP IPv4 и WARP IPv6 считаются независимыми действиями.

GeoFiles всегда применяются связанной парой `geoip.dat` + `geosite.dat`. Обычное обновление: **выберите источник → Проверить источник → Обновить GeoFiles**. SG-Gateway сам проверит категории, полный будущий Xray config, создаст backup и выполнит rollback при ошибке.

![Routing и GeoFiles](screenshots/routing.png)

Подробная инструкция с примерами внешних proxy, групп, Failover, пользовательских доменов/IP, приоритетов правил, диагностики и GeoFiles находится в [Routing, Outbounds и GeoFiles](ROUTING.md).

## Maintenance

Здесь находятся резервные копии, журналы, диагностика и независимые обновления панели и runtime-компонентов.

| Maintenance | Обновления |
| --- | --- |
| ![Maintenance](screenshots/maintenance.png) | ![Обновления](screenshots/updates.png) |

## Security

Раздел отвечает за режим доступа к панели, домен и сертификат Let’s Encrypt.

| Security | Сертификат |
| --- | --- |
| ![Security](screenshots/security.png) | ![Сертификат](screenshots/certificate-status.png) |

## Help

Встроенная справка повторяет структуру панели и даёт короткие инструкции по типовым операциям.

![Help](screenshots/help.png)
