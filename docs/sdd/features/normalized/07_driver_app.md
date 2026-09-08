# 🛵 Especificación Normalizada: Aplicación Repartidor (DRIVER) — Alto Contraste Solar (EARS)

> **Versión normalizada** — Completa disponibilidad, aceptación atómica, deslizadores de seguridad, recogida, llegada (auto + manual), cobro efectivo/Pago Móvil, incidencias, y variante solar del Design System.

---

## 1. Contexto y Objetivo
*   **Problema:** SDD original define deslizadores y geo-cercas pero omite: modo solar explícito (blanco puro #FFFFFF, negro #000000, naranja fluorescente), foreground service Android, permisos/notificación visible, batería por perfiles, reasignación con revocación inmediata, y cifras tabulares en cobro.
*   **Valor:** Uso seguro en moto (lluvia, vibración, guantes, sol llanero), batería duradera, cero doble asignación, cobro exacto.
*   **Módulos:** Flutter App (Android), compartiendo `models`, `api_client`, `design_system` (variante solar) con Cliente/Restaurant/Admin.

---

## 2. Actores
*   `DRIVER`: Repartidor en motocicleta, condiciones adversas (sol, lluvia, vibración).

---

## 3. Variante Solar del Design System (Exclusiva Driver)

| Token | Valor | Uso |
|-------|-------|-----|
| `solar-background` | `#FFFFFF` (blanco puro) | Fondo pantalla completa |
| `solar-text-primary` | `#000000` (negro absoluto) | Textos principales, montos |
| `solar-text-secondary` | `#333333` | Metadatos secundarios |
| `solar-accent` | `#FF5A36` (primario) / `#FF8C00` (fluorescente) | Botones CTA, deslizadores, alertas |
| `solar-success` | `#10B981` | Cobro confirmado, entrega |
| `solar-warning` | `#F59E0B` | Pendiente, en verificación |
| `solar-error` | `#DC2626` | Error, rechazado |

**Reglas Solar:**
- **Todo** fondo `#FFFFFF`, **todo** texto primario `#000000`.
- **Áreas de toque mínimas: 56×56 dp** (vs 48×48 general).
- **Deslizadores (Swipe to Confirm)** obligatorios en acciones críticas (llegada, cobro).
- **Foreground Service** visible permanente con notificación "MyDeliveryS Driver - Activo".
- **Tipografía:** `Outfit`/`Inter` + **tabular figures** en montos.

---

## 4. Arquitectura Cliente (Riverpod + GoRouter + Hive + Geolocator)

### 4.1. Capas Específicas Driver
```
lib/features/driver/
├── availability/        # Toggle Disponible/No Disponible + ubicación pasiva
├── orders/              # Lista asignados, detalle, acciones
├── tracking/            # GPS profiles, buffer, WS, reconexión
├── pickup/              # Llegada restaurante, recogida (deslizador)
├── delivery/            # Llegada cliente (auto/manual), cobro (deslizador)
├── incidents/           # Cliente ausente, accidente, reasignación
└── earnings/            # Resumen día/semana (solo lectura)
```

### 4.2. Hive Boxes Driver
| Box | Clave | Contenido |
|-----|-------|-----------|
| `auth_box` | `tokens` | Access/Refresh (Keystore) |
| `driver_box` | `current_order` | `Order` completo (para offline) |
| `driver_box` | `location_buffer` | `List<GpsPoint>` (max 50, FIFO) |
| `driver_box` | `availability` | `bool` (persiste toggle) |

### 4.3. Foreground Service + Geolocator Config
*   **RF-DRV-01:** LA APP iniciará **Foreground Service** al loguearse (permiso `FOREGROUND_SERVICE_LOCATION`). Notificación permanente: *"MyDeliveryS Driver - Compartiendo ubicación"* (no descartable).
*   **RF-DRV-02:** LA APP solicitará permisos `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `ACCESS_BACKGROUND_LOCATION` en primer uso. Explicación clara: *"Necesario para recibir pedidos y navegar"*.
*   **RF-DRV-03:** LA APP aplicará **perfiles GPS** (RF-TRK-04) según estado:
    - `DISPONIBLE` (sin orden) → `low`, 60s, 100m.
    - `HACIA_RESTAURANTE` → `medium`, 15s, 30m.
    - `ON_THE_WAY` → `high`, 5-10s, 15m.

---

## 5. Requisitos Funcionales (EARS)

### 5.1. Invariantes del Sistema (Ubícuos)
*   **RF-DRV-04:** LA APP usará **variante Solar** del Design System (RF-DRV-01 a RF-DRV-03). **Nunca** tema claro estándar.
*   **RF-DRV-05:** LA APP mantendrá **WebSocket** `/ws/driver/track` **solo** cuando tenga orden activa (`READY_FOR_PICKUP` → `DELIVERED`). Sin orden → WS cerrado, GPS pasivo.
*   **RF-DRV-06:** LA APP enviará `X-Idempotency-Key` (UUIDv4) en **todas** mutaciones: `accept`, `pickup`, `arrived`, `collect-cash`, `confirm-digital`, `report-incident`.

### 5.2. Disponibilidad y Lista de Pedidos
*   **RF-DRV-07:** LA APP expondrá **Toggle principal** (switch grande 56dp) **"Disponible / No Disponible"**. Estado persistido en Hive + sincronizado `PATCH /driver/availability {is_available: bool}`.
*   **RF-DRV-08:** CUANDO `is_available=true` y hay órdenes `READY_FOR_PICKUP` sin driver, BACKEND enviará Push FCM `NEW_ORDER_AVAILABLE` + datos orden.
*   **RF-DRV-09:** LA APP mostrará **Lista de Pedidos Disponibles** (solo si `is_available=true`): `order_number`, `restaurante`, `distancia` (km), `monto_total`, `first_half` (ya pagado). **No** muestra `second_half` aún.
*   **RF-DRV-10:** CUANDO driver toque **"Aceptar"** en orden, LA APP llamará `POST /driver/orders/{id}/accept` con `X-Idempotency-Key`.
*   **RF-DRV-11:** SI `200` → LA APP navega a **Detalle Orden Asignada** conservando `READY_FOR_PICKUP`, inicia GPS perfil `HACIA_RESTAURANTE` y abre el canal de tracking. Solo la recogida cambia a `ON_THE_WAY`.
*   **RF-DRV-12:** SI `409 ORDER_ALREADY_ASSIGNED` → LA APP muestra toast **"Otro conductor lo tomó"** + refresca lista.

### 5.3. Recogida en Restaurante (Llegada + Deslizador)
*   **RF-DRV-13:** CUANDO driver se acerque **< 100m** a restaurante (geo-cerca auto, RF-TRK-06), LA APP resaltará botón **[He llegado al Local]**.
*   **RF-DRV-14:** CUANDO driver pulse **[He llegado al Local]**, LA APP llamará `POST /driver/orders/{id}/arrive-restaurant` → backend valida geo-cerca O permite manual → transiciona internamente (orden sigue `READY_FOR_PICKUP`, registra `arrived_at_restaurant_at`).
*   **RF-DRV-15:** CUANDO restaurante tenga comida lista (Kanban "Listos para Recoger"), LA APP mostrará **Deslizador de Seguridad** (obligatorio):
    ```
    ┌────────────────────────────────────────────────────────┐
    │  [ 🍔 »»» Desliza para confirmar RECOGIDA ]           │
    └────────────────────────────────────────────────────────┘
    ```
    - Fondo `#FFFFFF`, track `#E9ECEF`, thumb `#FF5A36` con icono moto.
    - Completar deslizamiento → `POST /driver/orders/{id}/pickup` → backend: `UPDATE orders SET status=ON_THE_WAY, driver_id=... WHERE id=... AND status=READY_FOR_PICKUP AND driver_id=:me` (atómico).
*   **RF-DRV-16:** SI `200` → LA APP cambia a **Modo Entrega**: GPS perfil `ON_THE_WAY`, WS activo, navega a pantalla **En Ruta**.

### 5.4. Entrega al Cliente (Llegada Auto + Manual + Cobro)
*   **RF-DRV-17:** CUANDO GPS detecte **< 100m** a `user_addresses.location` **Y** `accuracy <= 50m`, BACKEND transiciona a `ARRIVED_AT_CUSTOMER` (RF-TRK-07). LA APP recibe Push/WS → muestra **Pantalla Cobro**.
*   **RF-DRV-18:** SI GPS falla (precisión > 50m O sin fix 60s), LA APP permite **Llegada Manual Documentada**: botón **[Confirmar Llegada Manual]** → abre cámara → foto obligatoria (puerta/cliente) → `POST /driver/orders/{id}/arrive-customer {evidence_image_url, manual: true}` → backend valida + transiciona.
*   **RF-DRV-19:** EN `ARRIVED_AT_CUSTOMER`, LA APP muestra **Pantalla de Cobro**:
    - Monto exacto `second_half_amount` **USD** (grande, `Display Large`, tabular figures).
    - Equivalente **VES** (congelado en orden, `Body Large`, tabular figures, color `text-secondary`).
    - Selector método: **Efectivo USD** / **Efectivo VES** / **Pago Móvil en Sitio**.
*   **RF-DRV-20:** SI **Efectivo USD**: LA APP muestra **Deslizador**:
    ```
    ┌────────────────────────────────────────────────────────┐
    │  [ 💵 »»» Desliza para confirmar cobro de $7.50 ]     │
    └────────────────────────────────────────────────────────┘
    ```
    Completar → `POST /driver/orders/{id}/collect-cash {amount_usd: 7.50, amount_ves: null}` → `200` → `DELIVERED`.
*   **RF-DRV-21:** SI **Efectivo VES**: Igual deslizador con monto VES. Backend valida `amount_ves == second_half_ves` (congelado).
*   **RF-DRV-22:** SI **Pago Móvil en Sitio**: LA APP muestra campos `Banco`, `Referencia` (dato de búsqueda) → **[Confirmar Pago Móvil]** → `POST /driver/orders/{id}/confirm-digital {reference_number, origin_bank, proof_image_url?}` → orden queda `PAYMENT_2_VERIFYING`. La verificación del Super Admin habilita `POST /driver/orders/{id}/complete-delivery`; únicamente esta confirmación física cambia a `DELIVERED`.

### 5.5. Incidencias y Cliente Ausente
*   **RF-DRV-23:** CUANDO en `ARRIVED_AT_CUSTOMER` cliente no responda **15 min** (timer visible en app, inicia en `ARRIVED_AT_CUSTOMER`), LA APP habilita **[Reportar Cliente Ausente]**.
*   **RF-DRV-24:** CUANDO driver reporte ausente, LA APP exigirá: **foto evidencia** (puerta/entorno) + **nota voz/texto** → `POST /driver/orders/{id}/report-absent {evidence_image_url, notes}` → backend: valida `no pagos phase=SECOND_HALF pending` → transiciona a `DELIVERY_FAILED` (RF-PAY-19). **Primer 50% se conserva**.
*   **RF-DRV-25:** CUANDO accidente/avería en `ON_THE_WAY`, LA APP: **[Reportar Incidencia]** → `POST /driver/orders/{id}/report-incident {type: ACCIDENT|BREAKDOWN, evidence_image_url?, notes}` → backend transiciona a `CANCELLED_WITH_REFUND` + alerta Super Admin.

### 5.6. Reasignación (Recibida de Admin)
*   **RF-DRV-26:** SI `SUPER_ADMIN` reasigna orden (RF-TRK-12), LA APP recibe Push `ORDER_REASSIGNED` → **inmediatamente**:
    1. Cierra WS de esa orden.
    2. Limpia `current_order` en Hive.
    3. Muestra toast **"Pedido reasignado a otro conductor"**.
    4. Vuelve a lista disponibilidad (si `is_available=true`).

### 5.7. Ganancias (Solo Lectura)
*   **RF-DRV-27:** LA APP expondrá `GET /driver/earnings?period=today|week|month` → muestra: `órdenes_completadas`, `total_efectivo_usd`, `total_efectivo_ves`, `total_pago_movil`, `comisiones_plataforma`, `neto`. **Solo lectura**, no editable.

### 5.8. Reconexión y Búfer GPS (RF-TRK-09, RF-TRK-10)
*   **RF-DRV-28:** LA APP mantendrá **búfer FIFO 50 puntos** en memoria + Hive (`location_buffer`) cuando WS caiga.
*   **RF-DRV-29:** AL reconectar: envía **último punto** → WS → luego **lote histórico** (endpoint `POST /driver/orders/{id}/location-batch`).
*   **RF-DRV-30:** Puntos históricos **no** disparan geo-cercas (backend ignora).

---

## 6. Requisitos No Funcionales
*   **Arranque GPS:** < 3s primer fix (perfil `high`).
*   **Batería:** Turno 8h con perfil mixto > 70% batería restante (test real dispositivo).
*   **Touch targets:** Mínimo 56×56 dp en **todos** botones/deslizadores.
*   **Visibilidad solar:** Contraste 7:1 mínimo (blanco/negro). Test en exterior mediodía.
*   **Foreground Service:** Notificación persistente, no consumible por usuario.

---

## 7. Casos Límite
*   Driver acepta orden → app crashea → reabre → consulta su pedido activo al servidor → restaura `READY_FOR_PICKUP` sin simular la recogida → reconecta tracking.
*   Dos drivers tocan "Aceptar" mismo ms → backend atómico → uno `200`, otro `409` → app maneja toast.
*   Llegada manual: driver toma foto → sube → backend valida → `ARRIVED_AT_CUSTOMER` → cobro normal.
*   Pago Móvil en sitio rechazado por admin → app muestra *"Referencia rechazada. Pide al cliente que reintente."* → vuelve a `ARRIVED_AT_CUSTOMER`.

---

## 8. Fuera de Alcance (V1)
*   Navegación integrada (usa Google Maps/Waze externo via intent).
*   Chat con cliente.
*   Calificaciones mutuas.
*   Múltiples órdenes simultáneas (batch/multi-drop).

---

## 9. Criterios de Finalización (DoD)
*   [ ] `flutter analyze` 0 warnings.
*   [ ] Variante Solar implementada: tokens exactos, deslizadores, foreground service.
*   [ ] Flujo completo: Disponible → Aceptar (atómico) → Llegada restaurante → Recogida (deslizador) → En ruta (GPS high) → Llegada cliente (auto/manual) → Cobro (deslizador efectivo / Pago Móvil) → Entregado.
*   [ ] Cliente ausente 15 min → `DELIVERY_FAILED` + evidencia + primer 50% conservado.
*   [ ] Reasignación: revocación inmediata WS + limpieza Hive + toast.
*   [ ] Búfer GPS 50 pts + reconexión con histórico (puntos no disparan geo-cerca).
*   [ ] `flutter test` + `integration_test` en dispositivo real Android.
*   [ ] Commits `feat(driver): ...` Conventional Commits.
