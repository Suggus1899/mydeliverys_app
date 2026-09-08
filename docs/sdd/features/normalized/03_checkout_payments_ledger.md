# 💰 Especificación Normalizada: Checkout, Pagos 50/50 y Ledger Financiero (EARS)

> **Versión normalizada** — Unifica máquina de estados y completa modelos de tasa, reembolsos, liquidaciones, idempotencia persistente y compensación.

---

## 1. Contexto y Objetivo
*   **Problema:** SDD original tiene estados contradictorios (`DRAFT` vs `PAYMENT_1_PENDING`), omite snapshots inmutables de cotización, no modela tasa de cambio versionada, carece de idempotencia persistente (solo Redis), y no define reembolsos/liquidaciones como movimientos compensatorios auditados.
*   **Valor:** Integridad financiera absoluta, trazabilidad completa, conciliación manual auditada, y cero doble cobro/asignación.
*   **Módulos:** Backend (Checkout, Pagos, Admin Finanzas, Ledger), App Cliente (Reporte pago), App Driver (Cobro en puerta), Consola Super Admin (Conciliación, Liquidaciones).

---

## 2. Actores
*   `CUSTOMER`: Reporte pago inicial (Pago Móvil), pago final en puerta (efectivo/Pago Móvil).
*   `DRIVER`: Confirmar llegada, cobrar efectivo, confirmar Pago Móvil en sitio.
*   `SUPER_ADMIN`: Verificar pagos digitales (ambas mitades), gestionar reembolsos, liquidaciones, auditoría.
*   `RESTAURANT_ADMIN`: Recibe notificación sonora al pasar a `PREPARING` (solo lectura financiera).

---

## 3. Máquina de Estados Unificada (Corregida)

```text
Carrito local (Flutter)
    → POST /orders/draft
    → PAYMENT_1_PENDING (cotización persistida, reserva 15 min, snapshot inmutable)
        → Cliente reporta pago 1 (POST /payments/{order_id}/report)
        → PAYMENT_1_VERIFYING
            → Super Admin verifica (POST /admin/payments/{id}/verify)
            → PREPARING (notificación sonora a cocina)
            → READY_FOR_PICKUP (cocina marca "Listo")
                → Driver acepta (atómico WHERE driver_id IS NULL)
                → ON_THE_WAY (GPS activo)
                    → Geo-cerca <100m cliente / Driver confirma llegada
                    → ARRIVED_AT_CUSTOMER
                        → Driver solicita cobro 50% final
                        → PAYMENT_2_VERIFYING
                            → Driver confirma efectivo (POST /driver/orders/{id}/collect-cash)
                            → SUPER_ADMIN verifica Pago Móvil reportado (POST /admin/payments/{id}/verify)
                            → DELIVERED
```

**Estados terminales (nunca se reactivan):** `DELIVERED`, `CANCELLED`, `REJECTED`, `CANCELLED_WITH_REFUND`, `DELIVERY_FAILED`.

---

## 4. Modelo de Datos Extendido (Delta)

### `orders` — columnas añadidas (snapshot inmutable de cotización)
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `quote_snapshot` | JSONB | `{items:[{product_id, name, base_price, modifiers:[{id,name,extra_price}], quantity}], delivery_fee, platform_fee, exchange_rate, exchange_rate_source, exchange_rate_effective_at, exchange_rate_queried_at, total_amount, first_half, second_half, delivery_distance_m, tier_id}` |
| `reservation_id` | UUID | FK implícita a `order_reservations.id` |
| `quote_expires_at` | TIMESTAMPTZ | `created_at + 15 min` |

### `payments` — columnas añadidas
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `idempotency_key` | VARCHAR(64) | UNIQUE, índice. Clave provista por cliente (`X-Idempotency-Key`). |
| `idempotency_scope` | VARCHAR(50) | `actor:operation` ej. `customer:payment1_report`, `driver:payment2_cash`, `admin:payment_verify`. |
| `ves_amount` | NUMERIC(14,2) | Monto en VES calculado a tasa de la orden (para pagos en bolívares). |
| `exchange_rate_used` | NUMERIC(14,6) | Tasa USD→VES usada en este pago (copia de `orders.quote_snapshot.exchange_rate`). |
| `reconciliation_status` | VARCHAR(20) | `PENDING`, `MATCHED`, `DISCREPANCY`, `REFUNDED`, `ADJUSTED`. Default `PENDING`. |
| `discrepancy_amount` | NUMERIC(10,2) | Diferencia reportada vs verificada (positivo = exceso, negativo = falta). |

### Nueva tabla: `exchange_rates` (Historial de tasas DolarAPI)
| Columna | Tipo | Restricciones | Descripción |
|---------|------|---------------|-------------|
| `id` | UUID | PK | |
| `rate` | NUMERIC(14,6) | NOT NULL | Valor decimal (ej. 36.452100) |
| `source` | VARCHAR(30) | NOT NULL, default `'dolarapi_oficial'` | Proveedor |
| `reported_date` | DATE | NOT NULL | Fecha que reporta el proveedor |
| `effective_date` | DATE | NOT NULL | Fecha de vigencia (puede = reported_date o lunes siguiente si fin de semana) |
| `queried_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` | Momento consulta nuestra |
| `is_valid` | BOOLEAN | NOT NULL, default `true` | Validación automática (ver RF-PAY-18) |

### Nueva tabla: `delivery_fee_tiers` (Tramos de envío configurables)
| Columna | Tipo | Restricciones | Descripción |
|---------|------|---------------|-------------|
| `id` | UUID | PK | |
| `name` | VARCHAR(50) | NOT NULL | Ej. "Casco Central", "Los Rosales" |
| `min_distance_m` | NUMERIC(10,2) | NOT NULL, default `0` | Incluido |
| `max_distance_m` | NUMERIC(10,2) | NOT NULL | **Incluido** (límite superior cerrado) |
| `fee_usd` | NUMERIC(10,2) | NOT NULL | Tarifa fija en USD |
| `is_active` | BOOLEAN | NOT NULL, default `true` | |
| **Constraint** | | `min_distance_m < max_distance_m`, **sin solapamientos** entre tiers activos. |

### Nueva tabla: `platform_fee_config` (Tarifa de plataforma única)
| Columna | Tipo | Restricciones | Descripción |
|---------|------|---------------|-------------|
| `id` | UUID | PK | Solo **una fila activa** (enforced por partial unique index `WHERE is_active`). |
| `fee_usd` | NUMERIC(10,2) | NOT NULL | Tarifa fija de servicio en USD |
| `is_active` | BOOLEAN | NOT NULL, default `true` | |

### Nueva tabla: `settlements` (Liquidaciones manuales auditadas)
| Columna | Tipo | Restricciones | Descripción |
|---------|------|---------------|-------------|
| `id` | UUID | PK | |
| `entity_type` | VARCHAR(20) | NOT NULL | `RESTAURANT` o `DRIVER` |
| `entity_id` | UUID | NOT NULL | FK a `restaurants.id` o `users.id` (role=DRIVER) |
| `period_start` | DATE | NOT NULL | Inicio período |
| `period_end` | DATE | NOT NULL | Fin período (inclusive) |
| `currency` | VARCHAR(3) | NOT NULL | `USD` o `VES` |
| `gross_amount` | NUMERIC(12,2) | NOT NULL | Bruto antes de comisiones/fees |
| `commission_amount` | NUMERIC(12,2) | NOT NULL | Comisión plataforma (restaurantes) |
| `delivery_fees_collected` | NUMERIC(12,2) | NOT NULL | Envíos cobrados (drivers) |
| `platform_fees_collected` | NUMERIC(12,2) | NOT NULL | Fees plataforma |
| `adjustments` | NUMERIC(12,2) | NOT NULL, default `0` | Ajustes manuales (reembolsos, incidencias) |
| `net_amount` | NUMERIC(12,2) | NOT NULL | `gross - commission + delivery_fees - platform_fees + adjustments` |
| `status` | VARCHAR(20) | NOT NULL, default `DRAFT` | `DRAFT`, `CONFIRMED`, `PAID`, `CANCELLED` |
| `proof_image_url` | TEXT | NULLABLE | Comprobante de transferencia/pago |
| `notes` | TEXT | NULLABLE | Observaciones de conciliación |
| `created_by` | UUID | FK `users.id` (SUPER_ADMIN) | Quién generó |
| `confirmed_by` | UUID | FK `users.id` (SUPER_ADMIN) | Quién aprobó |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` | |
| `confirmed_at` | TIMESTAMPTZ | NULLABLE | |

### Nueva tabla: `refunds` (Movimientos compensatorios auditados)
| Columna | Tipo | Restricciones | Descripción |
|---------|------|---------------|-------------|
| `id` | UUID | PK | |
| `order_id` | UUID | FK `orders.id`, NOT NULL | Pedido original |
| `payment_id` | UUID | FK `payments.id`, NOT NULL | Pago original a compensar |
| `type` | VARCHAR(20) | NOT NULL | `FULL`, `PARTIAL`, `ADJUSTMENT` |
| `amount_usd` | NUMERIC(10,2) | NOT NULL | Monto en USD a reembolsar |
| `amount_ves` | NUMERIC(14,2) | NOT NULL | Monto en VES a tasa de la orden |
| `reason` | VARCHAR(50) | NOT NULL | `CANCELLED_PREPARING`, `CANCELLED_ON_THE_WAY`, `CUSTOMER_ABSENT`, `DISPUTE`, `ADMIN_ADJUSTMENT` |
| `reference_number` | VARCHAR(50) | NULLABLE | Ref. bancaria del reembolso |
| `proof_image_url` | TEXT | NULLABLE | Captura del reembolso |
| `status` | VARCHAR(20) | NOT NULL, default `PENDING` | `PENDING`, `APPROVED`, `EXECUTED`, `REJECTED` |
| `requested_by` | UUID | FK `users.id` | Quién solicitó |
| `approved_by` | UUID | FK `users.id` (SUPER_ADMIN) | Quién aprobó |
| `executed_at` | TIMESTAMPTZ | NULLABLE | Momento ejecución |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` | |

### Nueva tabla: `idempotency_keys` (Idempotencia persistente + Redis)
| Columna | Tipo | Restricciones | Descripción |
|---------|------|---------------|-------------|
| `key` | VARCHAR(64) | PK | Valor de `X-Idempotency-Key` |
| `scope` | VARCHAR(50) | NOT NULL | `actor:operation` |
| `request_hash` | VARCHAR(64) | NOT NULL | SHA256 del body canónico (para detectar conflicto de contenido) |
| `response_status` | INTEGER | NOT NULL | HTTP status de la respuesta original |
| `response_body` | JSONB | NOT NULL | Cuerpo de respuesta original |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` | |
| `expires_at` | TIMESTAMPTZ | NOT NULL | `created_at + 24h` (configurable) |
| **Índice único** | | `(key, scope)` | Evita reuso cross-scope |

---

## 5. Requisitos Funcionales (EARS)

### 5.1. Invariantes del Sistema (Ubícuos)
*   **RF-PAY-01:** EL SISTEMA calculará **todo** con `Decimal` (Python) / `Numeric(10,2)` (PG). **Prohibido** `float`/`double`.
*   **RF-PAY-02:** EL SISTEMA aplicará división 50/50 asimétrica: `FIRST_HALF = ceil(total/2 * 100)/100`, `SECOND_HALF = total - FIRST_HALF`. Ejemplos: `$15.01→$7.51+$7.50`, `$20.00→$10.00+$10.00`, `$0.01→$0.01+$0.00`.
*   **RF-PAY-03:** EL SISTEMA **congelará** en `orders.quote_snapshot`: precios, cantidades, modificadores, dirección, distancia, fees, comisión, **tasa de cambio**, total USD, mitades USD, mitades VES (redondeadas a centavos, segunda por diferencia).
*   **RF-PAY-04:** EL SISTEMA exigirá cabecera `X-Idempotency-Key` (UUIDv4) en **todas** las mutaciones financieras: `POST /orders/draft`, `POST /payments/{order_id}/report`, `POST /driver/orders/{id}/collect-cash`, `POST /driver/orders/{id}/confirm-digital`, `POST /admin/payments/{id}/verify`, `POST /admin/payments/{id}/reject`, `POST /admin/refunds`.
*   **RF-PAY-05:** EL SISTEMA verificará idempotencia en **dos capas**:
    1. Redis `SET idemp:{scope}:{key} "PROCESSING" EX 120 NX` (rápido, evita procesamiento duplicado en vuelo).
    2. Tabla `idempotency_keys` (persistente): si `(key, scope)` existe:
       - Mismo `request_hash` → devuelve `response_body` guardado (200 OK o error original).
       - Distinto `request_hash` → `409 CONFLICT` `error_code: "IDEMPOTENCY_KEY_REUSED_DIFFERENT_PAYLOAD"`.

### 5.2. Tasa de Cambio (DolarAPI Venezuela — Endpoint Oficial)
*   **RF-PAY-06:** CUANDO job Celery `fetch_exchange_rate` se ejecute **cada 30 min**, EL SISTEMA consultará `GET https://ve.dolarapi.com/v1/dolares/oficial`, validará:
    - `moneda === "USD"`, `fuente === "oficial"`, `valor > 0`.
    - `fecha_reporte` no futura, no regresión > 24h vs último válido.
    - Si válido: inserta en `exchange_rates` con `is_valid=true`.
    - Si inválido: registra con `is_valid=false`, alerta a `SUPER_ADMIN` vía `audit_logs`.
*   **RF-PAY-07:** CUANDO `POST /orders/draft` necesite tasa, EL SISTEMA usará **la última `exchange_rates` con `is_valid=true` y `effective_date <= today`**.
*   **RF-PAY-08:** SI no hay tasa válida en **últimas 6 horas** (desde `queried_at` de la última válida), EL SISTEMA **bloqueará** nuevas cotizaciones (`422 PRECONDITION_FAILED` `error_code: "EXCHANGE_RATE_STALE"`) y alertará. Pedidos existentes conservan su tasa congelada. **No** hay fallback automático a otra fuente.

### 5.3. Cálculo de Envío (PostGIS + Tramos)
*   **RF-PAY-09:** CUANDO `POST /orders/draft` calcule distancia, EL SISTEMA usará `ST_DistanceSphere(restaurant.location, address.location)` → metros.
*   **RF-PAY-10:** EL SISTEMA buscará `delivery_fee_tiers` activo donde `min_distance_m <= distancia <= max_distance_m`. **Límite superior incluido**. Sin solapamientos garantizado por constraint.
*   **RF-PAY-11:** SI distancia no cae en ningún tramo activo, EL SISTEMA responderá `422 UNPROCESSABLE ENTITY` `error_code: "DELIVERY_OUT_OF_COVERAGE"`. **No** se permite checkout sin cobertura.

### 5.4. Primer Pago (50% Inicial)
*   **RF-PAY-12:** CUANDO `POST /payments/{order_id}/report {phase: FIRST_HALF, method, reference_number, origin_bank, proof_image_url?}` con `X-Idempotency-Key`, EL SISTEMA:
    1. Valida orden en `PAYMENT_1_PENDING` y reserva `ACTIVE` no expirada.
    2. Inserta `payments` con `phase=FIRST_HALF`, `status=PENDING`, `amount=first_half_usd`, `ves_amount=first_half_ves` (si method es VES), `idempotency_key`, `scope=customer:payment1_report`.
    3. Transiciona orden a `PAYMENT_1_VERIFYING`.
*   **RF-PAY-13:** CUANDO `POST /admin/payments/{id}/verify` (SUPER_ADMIN), EL SISTEMA:
    1. Valida `payment.status = PENDING`, `phase = FIRST_HALF`.
    2. Actualiza `payment.status = VERIFIED`, `verified_by = admin_id`, `verified_at = NOW()`, `reconciliation_status = MATCHED`.
    3. Transiciona orden a `PREPARING` (llama `transition(current, PREPARING, first_verified=true)`).
    4. Actualiza `order_reservations SET status=CONSUMED` (RF-CAT-09).
    5. Emite notificación **sonora** (FCM `priority=high` + `sound=oven_timer`) a app restaurante.

### 5.5. Segundo Pago (50% Final Contra Entrega)
*   **RF-PAY-14:** CUANDO `POST /driver/orders/{id}/arrived` (driver en geo-cerca <100m O confirmación manual documentada), EL SISTEMA transiciona a `ARRIVED_AT_CUSTOMER` y **desbloquea** interfaz de cobro en app driver.
*   **RF-PAY-15:** CUANDO `POST /driver/orders/{id}/collect-cash {amount_usd, amount_ves?}` con `X-Idempotency-Key`, EL SISTEMA (en transacción):
    1. Valida orden en `ARRIVED_AT_CUSTOMER` O `PAYMENT_2_VERIFYING`, `driver_id = current_driver`.
    2. Si `amount_usd > 0`: verifica `amount_usd == second_half_usd` (permite redondeo centavo por diferencia de cambio). Si `amount_ves > 0`: verifica `amount_ves == second_half_ves` (congelado en quote).
    3. Inserta `payments` `phase=SECOND_HALF`, `method=CASH_USD` o `CASH_VES`, `status=VERIFIED`, `verified_by=driver_id`, `verified_at=NOW()`, `reconciliation_status=MATCHED`.
    4. Transiciona orden a `DELIVERED` (`transition(..., DELIVERED, second_verified=true)`).
*   **RF-PAY-16:** CUANDO `POST /driver/orders/{id}/confirm-digital {reference_number, origin_bank, proof_image_url}` (Pago Móvil en sitio), EL SISTEMA inserta `payments` `phase=SECOND_HALF`, `method=PAGO_MOVIL`, `status=PENDING`, `scope=driver:payment2_digital_report`. **Orden permanece en `PAYMENT_2_VERIFYING`** hasta verificación admin.
*   **RF-PAY-17:** CUANDO `POST /admin/payments/{id}/verify` para `phase=SECOND_HALF` (SUPER_ADMIN), EL SISTEMA marca `VERIFIED`, `reconciliation_status=MATCHED`, y transiciona orden a `DELIVERED`.

### 5.6. Casos de Contingencia y Reembolsos
*   **RF-PAY-18:** CUANDO restaurante rechace en `PREPARING` (corte eléctrico, sin insumos), EL SISTEMA transiciona a `CANCELLED_WITH_REFUND`. **Alerta prioritaria** a `SUPER_ADMIN` (FCM + email + `audit_logs`). Super Admin gestiona reembolso vía `POST /admin/refunds {order_id, type: FULL, reason: CANCELLED_PREPARING}` → crea `refunds` `status=PENDING` → tras aprobar `status=EXECUTED` y registra comprobante.
*   **RF-PAY-19:** CUANDO driver reporte `DELIVERY_FAILED` (cliente ausente 15 min documentados desde `ARRIVED_AT_CUSTOMER`), EL SISTEMA:
    1. Valida que **no** exista `payments` `phase=SECOND_HALF` en `PENDING`/`VERIFYING` (regla: "no aplicarlo mientras exista segundo pago pendiente de revisión").
    2. Transiciona a `DELIVERY_FAILED` con `cancellation_reason` y evidencia (foto/gps).
    3. **Conserva** primer 50% (cubre costo alimentos + desplazamiento). Registra distribución manual en `settlements` o `audit_logs`.
*   **RF-PAY-20:** CUANDO segundo pago digital sea `REJECTED` (referencia falsa), EL SISTEMA mantiene orden en `ARRIVED_AT_CUSTOMER` (permite reintento desde ahí). **Nunca** vuelve a `PREPARING`.

### 5.7. Liquidaciones Manuales (Super Admin)
*   **RF-PAY-21:** CUANDO `SUPER_ADMIN` genere liquidación `POST /admin/settlements {entity_type, entity_id, period_start, period_end, currency}`, EL SISTEMA calculará agregando:
    - `gross_amount`: suma `payments.amount` (verified) del período para esa entidad.
    - `commission_amount`: para restaurantes, `sum(order.subtotal * restaurant.commission_rate / 100)`.
    - `delivery_fees_collected`: para drivers, suma `orders.delivery_fee` de sus órdenes `DELIVERED`.
    - `platform_fees_collected`: suma `orders.platform_fee`.
    - `adjustments`: suma `refunds.amount_usd` (negativo) + ajustes manuales.
    - `net_amount = gross - commission + delivery_fees - platform_fees + adjustments`.
    - Crea `settlements` `status=DRAFT`. Super Admin revisa, adjunta comprobante, marca `CONFIRMED` → `PAID` tras transferencia real.
*   **RF-PAY-22:** EL SISTEMA **nunca** automatizará transferencias ni inventará regla de reparto para incidencias. Todo es manual y auditado.

---

## 6. Requisitos No Funcionales y SLAs
*   **Cobertura 100%** líneas y ramas en `app.domain.financial`, `app.domain.states`, `app.services.ledger`.
*   **Concurrencia:** Test 50 drivers aceptan misma orden → 1 éxito `200`, 49 `409 ORDER_ALREADY_ASSIGNED`.
*   **Idempotencia:** Test 10 requests mismo `X-Idempotency-Key` → 1 inserción en `payments`, misma respuesta.
*   **Latencia p95:** `POST /orders/draft < 300ms`, `POST /payments/report < 200ms`, `POST /admin/payments/verify < 150ms`.
*   **Rate Limiting** (Architecture §5.2): `draft` 10/min, `payment_report` 5/min, `admin_verify` 30/min.

---

## 7. Casos Límite
*   `$0.01` total → `$0.01 + $0.00` (primer pago absorbe centavo).
*   Pago final en VES: usa tasa **congelada en la orden** (quote_snapshot), no la actual.
*   Diferencia de centavo en cobro efectivo: driver cobra `second_half_usd` exacto; si cliente da más, driver gestiona vuelto (no es responsabilidad del sistema).
*   Tasa DolarAPI fin de semana: `effective_date` puede ser lunes; `reported_date` viernes. Validación acepta esto.
*   Idempotencia cross-actor: `customer:payment1_report` y `driver:payment2_cash` pueden usar misma key (scope distinto).

---

## 8. Fuera de Alcance (Out of Scope)
*   Integración automática con APIs bancarias (conciliación es manual V1).
*   Liquidaciones automáticas / transferencias programadas.
*   Split de comisiones entre múltiples restaurantes en un pedido (mono-restaurante).

---

## 9. Criterios de Finalización (DoD)
*   [ ] Migración Alembic crea todas las tablas/columnas delta.
*   [ ] `split_payment` + `to_ves` + `settlement` — 100% cobertura, pruebas `$15.01`, `$20.00`, `$0.01`.
*   [ ] Máquina de estados: todas las transiciones válidas + inválidas lanzan `InvalidStateTransitionError`.
*   [ ] Idempotencia: Redis + PG, mismo hash = replay, distinto hash = 409.
*   [ ] Job `fetch_exchange_rate` cada 30 min + validación + alerta 6h stale.
*   [ ] `POST /orders/draft` snapshot inmutable + reserva atómica + fee por tramos.
*   [ ] `ruff`, `mypy`, `pytest -v --cov=app.services.ledger --cov-report=term-missing` → 100%.
*   [ ] Pruebas de carga Locust 1.500 CCU pasan SLAs.
