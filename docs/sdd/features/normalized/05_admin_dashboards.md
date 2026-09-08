# 💻 Especificación Normalizada: Paneles de Administración (Restaurante y Super Admin) (EARS)

> **Versión normalizada** — Unifica Kanban (3 columnas), corrige historial, completa conciliación, reembolsos, liquidaciones, auditoría, reasignación con custodia.

---

## 1. Contexto y Objetivo
*   **Problema:** SDD original define Kanban pero con columnas inconsistentes ("Nuevos / En preparación / Listos" vs estados financieros), omite: reconocimiento de cocina (`ACKNOWLEDGED` implícito), historial separado, toggle stock 1s, conciliación pagos con atajos teclado, mapa operaciones, reasignación con evidencia, y reglas de auditoría inmutables.
*   **Valor:** Operación diaria fluida para cocineros (tablet pared), control financiero total para Super Admin, trazabilidad legal.
*   **Módulos:** Panel Restaurante (Flutter Web + Android Tablet), Consola Super Admin (Flutter Web Desktop).

---

## 2. Actores
*   `RESTAURANT_ADMIN`: Cocina/gerente local. Tablet Android montada en pared o PC.
*   `SUPER_ADMIN`: Operador central. Navegador web desktop (2FA obligatorio).

---

## 3. Panel Restaurante — Kanban Corregido (3 Columnas + Historial)

### 3.1. Columnas (Estados Financieros → Operativos)
| Columna | Estados Incluidos | Descripción |
|---------|-------------------|-------------|
| **Nuevos (Pagados 50%)** | `PREPARING` | Pedidos con primer 50% verificado. **Alerta sonora 3 tonos** al entrar. Tarjeta parpadeante amarilla. |
| **En Preparación** | `PREPARING` (tras reconocimiento) | Cocinero toca **[Empezar]** → pasa a esta columna internamente (mismo estado `PREPARING`, flag `acknowledged_at` en `orders`). Lista ingredientes/modificadores **tipografía 20px** para lectura a 1m. |
| **Listos para Recoger** | `READY_FOR_PICKUP` | Botón verde **[Comida Lista]** (60px alto, touch-friendly). Al pulsar: transiciona a `READY_FOR_PICKUP`, notifica a drivers. |

### 3.2. Historial Separado (No columna Kanban)
*   **RF-ADM-01:** EL SISTEMA expondrá **pestaña/vista separada** "Historial del Día" con: `DELIVERED`, `CANCELLED`, `CANCELLED_WITH_REFUND`, `DELIVERY_FAILED` del día actual. **No** mezcla con columnas activas.
*   **RF-ADM-02:** EL SISTEMA permitirá filtrar historial por: estado, rango horario, monto, cliente.

### 3.3. Toggle de Stock Diario (1 segundo)
*   **RF-ADM-03:** EL SISTEMA expondrá `GET /admin/restaurant/menu` (lista plana productos + modificadores) con `is_available`, `track_stock`, `stock`.
*   **RF-ADM-04:** CUANDO operador toque interruptor `is_available` en UI, EL SISTEMA ejecutará `PATCH /admin/products/{id} {is_available}` → **respuesta < 200ms**, invalidación inmediata caché menú público.

### 3.4. Reconocimiento de Cocina (Implícito en PREPARING)
*   **RF-ADM-05:** CUANDO orden entra a `PREPARING` (verificación primer pago), EL SISTEMA la muestra en columna "Nuevos".
*   **RF-ADM-06:** CUANDO cocinero toque **[Empezar]** en tarjeta "Nuevos", EL SISTEMA actualizará `orders.acknowledged_at = NOW()` (nueva columna) y moverá visualmente a "En Preparación". **No** cambia estado financiero.
*   **RF-ADM-07:** EL SISTEMA **no** añadirá estado financiero intermedio ("Reconocido"). La distinción "Nuevos" vs "En Preparación" es **puramente operativa/visual** en el Kanban.

---

## 4. Consola Super Admin — Centro de Comando

### 4.1. Conciliación de Pagos Móviles (Bandeja Unificada)
*   **RF-ADM-08:** EL SISTEMA expondrá `GET /admin/payments/pending` con pagos `status=PENDING` de **ambas fases** (`FIRST_HALF`, `SECOND_HALF`).
*   **RF-ADM-09:** Vista dividida (split-pane):
    - **Izquierda:** Lista pagos pendientes — `order_number`, `phase`, `method`, `amount_usd`, `amount_ves`, `reference_number`, `origin_bank`, `created_at`, `customer_name`, `customer_phone`.
    - **Derecha:** Imagen comprobante ampliada (zoom/pan) + metadatos.
*   **RF-ADM-10:** Atajos de teclado globales (accesibilidad):
    - `A` → **Aprobar y Pasar a Preparación** (si `FIRST_HALF`) / **Aprobar y Entregar** (si `SECOND_HALF`).
    - `R` → **Rechazar (Exigir Nueva Referencia)** → abre modal con motivo obligatorio.
    - `Espacio` → Alternar vista previa imagen.
    - `Flechas` → Navegar lista.
*   **RF-ADM-11:** CUANDO `A` (aprobar), EL SISTEMA ejecuta `POST /admin/payments/{id}/verify` (ver RF-PAY-13, RF-PAY-17).
*   **RF-ADM-12:** CUANDO `R` (rechazar), EL SISTEMA ejecuta `POST /admin/payments/{id}/reject {reason}` → `payment.status=REJECTED`, orden vuelve a `PAYMENT_1_PENDING` (fase 1) O `ARRIVED_AT_CUSTOMER` (fase 2). Notifica a cliente/driver.

### 4.2. Gestión de Socios (Restaurantes y Repartidores)
*   **RF-ADM-13:** `POST /admin/restaurants` — Crea comercio: `name`, `phone`, `address`, `location` (lat/lng → PostGIS), `commission_rate`, `is_active=true`. Asigna coordenadas exactas para cálculo rutas.
*   **RF-ADM-14:** `POST /admin/restaurant-staff` — Crea operador: `restaurant_id`, `phone`, `full_name`, `temp_password`. Envía credenciales por WhatsApp (Celery).
*   **RF-ADM-15:** `POST /admin/drivers` — Crea repartidor: `phone`, `full_name`, `temp_password`, `vehicle_info` (placa, modelo). Genera credenciales temporales.

### 4.3. Mapa de Operaciones en Vivo
*   **RF-ADM-16:** EL SISTEMA mostrará mapa interactivo (Flutter `google_maps_flutter` web) con:
    - Pines **drivers activos** (colores: 🟢 `INACTIVE/ESPERANDO`, 🟡 `HACIA_RESTAURANTE`, 🟣 `ON_THE_WAY`, 🔴 `ARRIVED_AT_CUSTOMER`).
    - Pines **restaurantes** (azul).
    - Pines **órdenes activas** (número de orden).
    - Actualización **tiempo real** vía WebSocket `/ws/admin/map` (Redis Pub/Sub `admin:map:updates`).
*   **RF-ADM-17:** Herramienta **reasignación manual**: click en pin driver → click en orden → modal confirma `new_driver_id` + `evidence_image_url` (obligatorio si orden en `ON_THE_WAY`). Ejecuta `POST /admin/orders/{id}/reassign` (ver RF-TRK-12).

### 4.4. Salud de Tasa de Cambio (Observabilidad)
*   **RF-ADM-18:** EL SISTEMA expondrá `GET /admin/exchange-rate/health` con:
    - `last_valid_rate`, `last_valid_queried_at`, `last_valid_effective_date`.
    - `seconds_since_last_valid` (si > 6h → **ALERTA ROJA**).
    - `consecutive_failures` (fallos validación DolarAPI).
    - `is_blocking_new_orders` (boolean, derivado de >6h).
*   **RF-ADM-19:** SI `seconds_since_last_valid > 21600` (6h), EL SISTEMA mostrará banner rojo persistente en consola y bloqueará `POST /orders/draft` con `422 EXCHANGE_RATE_STALE`.

### 4.5. Incidencias, Reembolsos y Liquidaciones
*   **RF-ADM-20:** `GET /admin/incidents` — Lista órdenes en `CANCELLED_WITH_REFUND`, `DELIVERY_FAILED`, `REJECTED` (pago 2 rechazado). Filtros: fecha, tipo, restaurante, driver.
*   **RF-ADM-21:** `POST /admin/refunds` — Crea reembolso compensatorio (ver RF-PAY-18). Requiere: `order_id`, `type`, `reason`, `amount_usd`, `proof_image_url`. Crea `refunds` `status=PENDING`.
*   **RF-ADM-22:** `PATCH /admin/refunds/{id} {status: APPROVED|REJECTED, approved_by}` — Super Admin aprueba/rechaza. Si `APPROVED` → `status=EXECUTED`, registra `executed_at`, actualiza `payments.reconciliation_status=REFUNDED`.
*   **RF-ADM-23:** `POST /admin/settlements` — Genera liquidación (ver RF-PAY-21). `GET /admin/settlements` — Lista con filtros. `PATCH /admin/settlements/{id} {status: CONFIRMED|PAID, proof_image_url, confirmed_by}` — Flujo `DRAFT → CONFIRMED → PAID`.

### 4.6. Auditoría Inmutable
*   **RF-ADM-24:** EL SISTEMA **nunca** permitirá `DELETE` en `payments`, `orders`, `refunds`, `settlements`, `exchange_rates`, `audit_logs`.
*   **RF-ADM-25:** CUALQUIER acción en consola (`verify`, `reject`, `reassign`, `refund`, `settlement`, `toggle_restaurant`, `create_staff`) registrará en `audit_logs`: `admin_user_id`, `action`, `entity_name`, `entity_id`, `details` (JSONB: before/after), `ip_address`, `created_at`.

---

## 5. Requisitos No Funcionales
*   **Panel Restaurante:** Carga inicial < 2s en tablet Android (modo kiosco). Touch targets ≥ 56×56 dp.
*   **Consola Super Admin:** Dark mode industrial (`#0B0E14`), densa, sin scroll innecesario. Atajos teclado 100% funcionales.
*   **Seguridad:** 2FA obligatorio Super Admin. Sesión web máx 8h (config). CSRF en cookies.
*   **Rate Limiting:** Endpoints admin 120/min (authenticated), `reassign` 10/min.

---

## 6. Casos Límite
*   Restaurante apaga `is_open` mientras hay órdenes en `PREPARING` → órdenes continúan, **no** se cancelan automáticamente.
*   Driver reasignado en `ON_THE_WAY` sin evidencia → `400 BAD REQUEST` `error_code: "CUSTODY_EVIDENCE_REQUIRED"`.
*   Super Admin intenta aprobar pago ya verificado → `409 CONFLICT` `error_code: "PAYMENT_ALREADY_VERIFIED"`.
*   Liquidación con `net_amount < 0` → permitida (ajustes superan ingresos), pero requiere nota obligatoria en `notes`.

---

## 7. Fuera de Alcance (V1)
*   App nativa iOS para restaurante (solo Flutter Web + Android Tablet).
*   Reportes automáticos PDF/Excel programados (export manual CSV V1).
*   Notificaciones email automáticas (solo FCM + WhatsApp OTP).
*   Múltiples monedas en liquidación (solo USD o VES por liquidación).

---

## 8. Criterios de Finalización (DoD)
*   [ ] Kanban 3 columnas + Historial separado + Toggle stock 1s + Alerta sonora 3 tonos.
*   [ ] Conciliación: vista split + atajos `A`/`R` + zoom imagen + pagos ambas fases.
*   [ ] Mapa operaciones: pines coloreados por estado + WS tiempo real + reasignación con evidencia.
*   [ ] Salud tasa: banner rojo 6h + bloqueo draft.
*   [ ] Incidencias/Reembolsos/Liquidaciones: CRUD completo + auditoría inmutable.
*   [ ] `flutter analyze` (web), `pytest -v tests/integration/test_admin.py`, `tests/concurrency/test_reassign.py`.
*   [ ] Accesibilidad: WCAG 2.1 AA, contraste, áreas toque, indicadores no solo color.