# 🔗 Matriz de Trazabilidad — Requisito → API / Datos / UI → Prueba

> Entregable de Fase 0. Cada requisito EARS de `docs/sdd/features/normalized/` enlaza con su endpoint, tablas, pantalla y evidencia de aceptación. Si un RF no tiene prueba, el criterio de salida de Fase 0 no se cumple.

Leyenda de estado: ✅ implementado y verificado · 🟡 implementado sin evidencia E2E/carga · ⬜ pendiente.

## 01 — Autenticación y sesiones (`01_auth_and_sessions.md`)

| RF | API | Datos | UI | Prueba | Estado |
|---|---|---|---|---|---|
| RF-AUTH-01 normalizar E.164 | `POST /auth/request-otp`, `POST /auth/login` | `users.phone_number` | Login/OTP (cliente, driver) | `test_pricing.py::TestNormalizePhone` | ✅ |
| RF-AUTH-02 nombre en primer registro | `PATCH /users/me` | `users.full_name` | Modal nombre (cliente) | manual | 🟡 |
| RF-AUTH-03 Argon2id solo roles admin/driver | `POST /auth/login`, `POST /auth/change-password` | `users.password_hash` | Login socios | integración `test_models.py` | 🟡 |
| RF-AUTH-04 tabla sesiones | `POST /auth/refresh`, `/logout`, `/logout-all` | `user_sessions` | — | integración pendiente | 🟡 |
| RF-AUTH-05 revocación total | `POST /auth/logout-all`, cambio clave | `user_sessions.revoked_at` | — | integración pendiente | 🟡 |
| RF-AUTH-06 OTP 6 dígitos TTL 180s | `POST /auth/request-otp` | Redis `otp:{phone}` | Pantalla OTP | manual + Celery dev-log | 🟡 |
| RF-AUTH-07 verify → upsert + tokens | `POST /auth/verify-otp` | `users`, `user_sessions` | Home cliente | integración pendiente | 🟡 |
| RF-AUTH-08 bloqueo teléfono 3 fallos/10min | `POST /auth/verify-otp` | Redis `otp_attempts`, `otp_blocked` | Aviso bloqueo | integración pendiente | 🟡 |
| RF-AUTH-09 bloqueo IP 5/3min | `POST /auth/request-otp` | Redis `otp_ip_*` | — | integración pendiente | 🟡 |
| RF-AUTH-10 login password + 2FA super admin | `POST /auth/login`, `/2fa/*` | `users` | Login socios, 2FA | manual | 🟡 |
| RF-AUTH-11 TOTP setup + 8 recovery | `POST /auth/2fa/setup`, `/2fa/confirm` | Redis `totp:*` | Consola admin | manual | 🟡 |
| RF-AUTH-12 recovery un solo uso | `POST /auth/2fa/recovery` | Redis `totp:recovery:*` | Consola admin | manual | 🟡 |
| RF-AUTH-13 alta operador + N:1 | `POST /admin/restaurant-staff` | `users`, `restaurant_staff` | Consola admin | integración pendiente | 🟡 |
| RF-AUTH-14 cambio clave forzado primer login | `POST /auth/change-password` | `users`, `user_sessions` | Login operador | manual | 🟡 |
| RF-AUTH-15 refresh rotativo | `POST /auth/refresh` | `user_sessions` (`SELECT FOR UPDATE`) | interceptor ApiClient | integración pendiente | 🟡 |
| RF-AUTH-16 cookie HttpOnly+CSRF web | — (infra) | — | Paneles web | manual | 🟡 |
| RF-AUTH-17 Keystore Android | — (cliente) | Hive `auth_box` | Apps Android | manual | 🟡 |
| RF-AUTH-18 401 SESSION_EXPIRED | global | `user_sessions` | re-login | manual | 🟡 |
| RF-AUTH-19 bloqueo 2FA 5/15min | `POST /auth/2fa/verify` | Redis `totp_fail:*` | Consola admin | manual | 🟡 |
| RF-AUTH-20 ownership restaurante | `require_restaurant_ownership` | `restaurant_staff` | — | integración pendiente | 🟡 |
| RF-AUTH-21 ADDRESS_NOT_OWNED | `POST /orders/draft` | `user_addresses` | Checkout | integración pendiente | 🟡 |
| RF-AUTH-22 sesión web máx 8h | config `WEB_SESSION_MAX_HOURS` | — | Paneles web | manual | 🟡 |

## 02 — Catálogo, inventario y carrito (`02_catalog_inventory_cart.md`)

| RF | API | Datos | UI | Prueba | Estado |
|---|---|---|---|---|---|
| RF-CAT-01 `is_available` calculado | `GET /restaurants/{id}/menu` | `products`, `modifiers` | Menú cliente | integración pendiente | 🟡 |
| RF-CAT-02 servidor recalcula todo | `POST /orders/draft` | — | — | `test_models.py` | 🟡 |
| RF-CAT-03 invalidación caché | `PATCH /restaurants/products/{id}` | Redis `cache:menu:*` | Toggle stock | manual | 🟡 |
| RF-CAT-04 crear producto | (admin menú) | `products` | Gestión menú | integración pendiente | 🟡 |
| RF-CAT-05 patch + evento | `PATCH /restaurants/products/{id}` | `products` | Toggle stock | manual | 🟡 |
| RF-CAT-06 auto-apagado stock 0 | `POST /orders/draft` | `products.is_available` | Menú | `test_race_conditions.py` | 🟡 |
| RF-CAT-07 reserva atómica 15min | `POST /orders/draft` | `order_reservations`, `products.stock` | Checkout | `test_race_conditions.py::TestInventoryRaceCondition` | 🟡 |
| RF-CAT-08 job expiración + reposición | Celery `expire_reservations` c/1min | `order_reservations` | — | integración pendiente | 🟡 |
| RF-CAT-09 verify consume reserva | `POST /admin/payments/{id}/verify` | `order_reservations.status=CONSUMED` | Conciliación | integración pendiente | 🟡 |
| RF-CAT-10 reject mantiene reserva | `POST /admin/payments/{id}/reject` | `order_reservations` | Conciliación | integración pendiente | 🟡 |
| RF-CAT-11 cancel libera / post-PREPARING no repone | `POST /orders/{id}/cancel` | `order_reservations` | Historial | integración pendiente | 🟡 |
| RF-CAT-12 bloqueo unidades reservadas | `POST /orders/draft` (`WHERE stock>=qty`) | `products.stock` | — | `test_race_conditions.py` | 🟡 |
| RF-CAT-13 validación min/max servidor | `POST /orders/draft` | `modifier_groups` | BottomSheet | `testing_strategy` L1 | 🟡 |
| RF-CAT-14 409 INSUFFICIENT_STOCK | `POST /orders/draft` | — | Error + recarga menú | `test_race_conditions.py` | 🟡 |
| RF-CAT-15 modal mono-restaurante | — (cliente) | Hive `cart_box` | Modal confirmación | widget pendiente | ⬜ |
| RF-CAT-16 422 INVALID_STOCK_CONFIG | `PATCH /restaurants/products/{id}` | `products` | Gestión menú | manual | 🟡 |
| RF-CAT-17 TTL configurable | config `RESERVATION_TTL_MINUTES` | — | — | — | ✅ |

## 03 — Checkout, pagos y ledger (`03_checkout_payments_ledger.md`)

| RF | API | Datos | UI | Prueba | Estado |
|---|---|---|---|---|---|
| RF-PAY-01 Decimal/Numeric, sin float | todos financieros | `NUMERIC(10,2)` | `Money` (enteros) + tabular | `test_financial_ledger.py` 100% | ✅ |
| RF-PAY-02 split 50/50 centavo arriba | `POST /orders/draft` | `orders.first/second_half` | Barra 50/50 | `test_financial_ledger.py`, `money_test.dart` | ✅ |
| RF-PAY-03 snapshot congelado | `POST /orders/draft` | `orders.quote_snapshot` | Comprobante | `test_models.py` | 🟡 |
| RF-PAY-04 X-Idempotency-Key obligatorio | middleware + endpoints | `idempotency_keys` | ApiClient auto-key | `test_race_conditions.py::TestIdempotency` | 🟡 |
| RF-PAY-05 doble capa Redis+PG | middleware + `services/idempotency.py` | Redis + `idempotency_keys` | — | `test_race_conditions.py` | 🟡 |
| RF-PAY-06 fetch DolarAPI c/30min + validación | Celery `fetch_exchange_rate` | `exchange_rates` | — | manual (requiere red) | 🟡 |
| RF-PAY-07 última válida en draft | `POST /orders/draft` | `exchange_rates` | — | integración pendiente | 🟡 |
| RF-PAY-08 bloqueo >6h sin fallback | `POST /orders/draft` → 422 | `exchange_rates` | Banner admin + aviso cliente | manual | 🟡 |
| RF-PAY-09 distancia PostGIS/haversine | `POST /orders/draft` | `restaurants.location` | — | `test_tracking.py` | ✅ |
| RF-PAY-10 tramos límite superior incluido | `POST /orders/draft` | `delivery_fee_tiers` | — | integración pendiente | 🟡 |
| RF-PAY-11 fuera de cobertura 422 | `POST /orders/draft` | `delivery_fee_tiers` | Aviso cliente | integración pendiente | 🟡 |
| RF-PAY-12 reporte pago 1 | `POST /payments/{id}/report` | `payments` PENDING | Pantalla pago | integración pendiente | 🟡 |
| RF-PAY-13 verify pago 1 → PREPARING + campana | `POST /admin/payments/{id}/verify` | `payments`, `orders` | Kanban + FCM | integración pendiente | 🟡 |
| RF-PAY-14 llegada → ARRIVED + cobro | `POST /driver/orders/{id}/arrived` | `orders` | Pantalla cobro | integración pendiente | 🟡 |
| RF-PAY-15 cobro efectivo atómico | `POST /driver/orders/{id}/collect-cash` | `payments` VERIFIED | Deslizador | integración pendiente | 🟡 |
| RF-PAY-16 Pago Móvil en sitio → PENDING | `POST /driver/orders/{id}/confirm-digital` | `payments` PENDING | Formulario ref | integración pendiente | 🟡 |
| RF-PAY-17 verify pago 2 → DELIVERED | `POST /admin/payments/{id}/verify` | `payments`, `orders` | Conciliación | integración pendiente | 🟡 |
| RF-PAY-18 rechazo cocina → refund | `POST /admin/refunds` | `refunds` | Incidencias | `finance_ops` manual | 🟡 |
| RF-PAY-19 cliente ausente 15min | `POST /driver/orders/{id}/report-absent` (valida 15min + sin pago 2 PENDING) | `orders.DELIVERY_FAILED` | Driver | unit pendiente E2E / lógica verificada en revisión | 🟡 |
| RF-PAY-20 pago 2 rechazado → ARRIVED | `POST /admin/payments/{id}/reject` | `orders` | Conciliación | integración pendiente | 🟡 |
| RF-PAY-21 liquidaciones manuales | `POST /admin/settlements` | `settlements` | Consola admin | `finance_ops` manual | 🟡 |
| RF-PAY-22 sin transferencias automáticas | — (política) | — | — | revisión | ✅ |
| Conciliación: discrepancias reportado vs esperado | `POST /admin/payments/{id}/flag-discrepancy` | `payments.reconciliation_status` | Conciliación | `TestDiscrepancy` 3/3 ✅ | ✅ |

## 04 — Tracking y resiliencia (`04_live_tracking_resilience.md`)

| RF | API | Datos | UI | Prueba | Estado |
|---|---|---|---|---|---|
| RF-TRK-01 Redis Pub/Sub sin estado local | `WS /ws/*` | Redis canales | — | manual | 🟡 |
| RF-TRK-02 historial 3min/hito | `POST /tracking/location` | `delivery_tracking` | — | manual | 🟡 |
| RF-TRK-03 efímero TTL 10min | `POST /tracking/location` | Redis `driver:location:*` | — | `test_tracking.py` | ✅ |
| RF-TRK-04 perfiles GPS | — (driver) | — | Foreground service | manual dispositivo | ⬜ |
| RF-TRK-05 notificación visible + permisos | — (driver) | — | Foreground service | manual dispositivo | ⬜ |
| RF-TRK-06 geo-cerca restaurante 100m | `WS` + Kanban | `geofence_events` | Botón llegada local | manual | 🟡 |
| RF-TRK-07 llegada cliente + push + cobro | `POST /driver/orders/{id}/arrived` | `orders`, `geofence_events` | Pantalla cobro | integración pendiente | 🟡 |
| RF-TRK-08 llegada manual documentada | `POST /driver/orders/{id}/arrived {manual}` | `geofence_events` | Cámara + botón | integración pendiente | 🟡 |
| RF-TRK-09 búfer FIFO 50 | — (driver) | Hive `location_buffer` | — | widget pendiente | ⬜ |
| RF-TRK-10 reconexión: reciente primero | `POST /tracking/location-batch` | `delivery_tracking` histórico | — | manual | 🟡 |
| RF-TRK-11 aviso 45s atenuado | `WS /ws/customer/track` | — | Mapa cliente | widget pendiente | ⬜ |
| RF-TRK-12 reasignación atómica + custodia | `POST /admin/orders/{id}/reassign` | `orders`, `audit_logs` | Mapa admin | `test_race_conditions.py` | 🟡 |

## 05 — Paneles admin (`05_admin_dashboards.md`)

| RF | API | Datos | UI | Prueba | Estado |
|---|---|---|---|---|---|
| RF-ADM-01 historial separado | `GET /restaurant/history` (+ filtros status/since/until) | `orders` | Pestaña Historial | manual | 🟡 |
| RF-ADM-02 filtros historial | `GET /restaurant/history?status=&since=&until=` | `orders` | Filtros | manual | 🟡 |
| RF-ADM-03 lista menú plana | `GET /restaurants/admin/menu` | `products`, `modifiers` | Gestión menú | manual | 🟡 |
| RF-ADM-04 toggle <200ms | `PATCH /restaurants/products/{id}` | + invalidación caché | Switch 56dp | manual | 🟡 |
| RF-ADM-05/06/07 reconocimiento operativo | `POST /restaurant/orders/{id}/acknowledge` | `orders.acknowledged_at` | Kanban | manual | 🟡 |
| RF-ADM-08 bandeja ambas fases | `GET /admin/payments/pending` | `payments` | Split-pane | manual | 🟡 |
| RF-ADM-09/10 split + atajos A/R | `admin_web` ReconciliationScreen | — | Consola (`admin_web/`, atajos A/R/flechas, misma paleta app) | `app_colors_test.dart` ✅ | 🟡 |
| RF-ADM-11/12 aprobar/rechazar | `POST /admin/payments/{id}/verify|reject` | `payments` | Botones + atajos | integración pendiente | 🟡 |
| RF-ADM-13/14/15 alta socios | `POST /admin/restaurants|restaurant-staff|drivers` | `restaurants`, `users` | Formularios | integración pendiente | 🟡 |
| RF-ADM-16 mapa operativo por estado | `WS /ws/admin/map` | Redis | Vista de posiciones reales; cartografía requiere clave operativa | manual | 🟡 |
| RF-ADM-17 reasignación con evidencia | `POST /admin/orders/{id}/reassign` | `orders`, `audit_logs` | Modal | integración pendiente | 🟡 |
| RF-ADM-18/19 salud tasa + banner 6h | `GET /admin/exchange-rate/health` | `exchange_rates` | Banner rojo | manual | 🟡 |
| RF-ADM-20 incidencias | `GET /admin/incidents` (órdenes + pagos rechazados) | `orders`, `payments` | Incidencias | manual | 🟡 |
| RF-ADM-21/22/23 reembolsos/liquidaciones | `POST /admin/refunds|settlements` | `refunds`, `settlements` | Formularios | manual | 🟡 |
| RF-ADM-24/25 inmutabilidad + auditoría | global | `audit_logs` (sin DELETE) | — | revisión código | ✅ |

## 06/07/08 — Apps (cliente, driver, restaurante)

| RF | UI | Prueba | Estado |
|---|---|---|---|
| RF-CLI-01..05 Riverpod/GoRouter/enteros/tabular sin cálculo | base `mobile/` | `money_test.dart` ✅ / resto ⬜ | 🟡 |
| RF-CLI-06..12 OTP | pantallas auth | ⬜ | ⬜ |
| RF-CLI-13..16 perfil/direcciones | perfil | ⬜ | ⬜ |
| RF-CLI-17..25 catálogo/modificadores | menú + BottomSheet | ⬜ | ⬜ |
| RF-CLI-26..29 carrito Hive mono-restaurante | `cart_controller.dart` | `cart_test.dart` 5/5 ✅ | ✅ |
| RF-CLI-30..38 checkout + reporte pago 1 | checkout | ⬜ (requiere backend vivo) | ⬜ |
| RF-CLI-39..45 tracking/entrega/comprobante | mapa + comprobante | ⬜ | ⬜ |
| RF-CLI-46..50 historial/reintentos/offline | historial + banner | ⬜ | ⬜ |
| RF-DRV-01..30 variante solar, foreground, deslizadores, cobro | app driver | ⬜ (tokens + contratos listos) | ⬜ |
| RF-DRV-23..25 ausencia 15min / incidencia en ruta | `POST /driver/orders/{id}/report-absent|report-incident` | `orders.DELIVERY_FAILED` / `CANCELLED_WITH_REFUND` + `audit_logs` | Driver | manual (requiere backend vivo) | 🟡 |
| RF-RES-01..20 kiosco, campana 3 tonos, Kanban tablet | app restaurante | ⬜ | ⬜ |

## Brechas que bloquean el cierre de Fase 0

1. ~~Matriz inexistente~~ → creada en este archivo (pendiente: marcar E2E/carga al ejecutarlas).
2. SLAs arquitectura vs testing → unificados (`architecture.md` §4.1 referencia a `testing_strategy.md` §5.3).
3. `DRAFT` como estado backend → corregido en `catalog_and_cart.md`, `checkout_and_5050.md` (backend crea `PAYMENT_1_PENDING`).
4. Kanban 3.ª columna → corregido en `admin_dashboards.md` (Listos + historial separado).
5. Medios de pago → contrato limitado a Pago Móvil, transferencia y efectivo USD/VES.
