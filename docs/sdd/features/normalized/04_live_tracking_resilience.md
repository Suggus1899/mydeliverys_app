# 🛵 Especificación Normalizada: Seguimiento en Vivo, Geolocalización y Resiliencia (EARS)

> **Versión normalizada** — Completa perfiles GPS, búfer FIFO, reconexión, geo-cercas, y SLAs de WebSocket.

---

## 1. Contexto y Objetivo
*   **Problema:** SDD original define arquitectura WS + Redis Pub/Sub pero omite: perfiles de batería por estado, umbrales exactos de geo-cerca (100m), llegada manual documentada, atenuación a 45s, y recuperación de histórico tras reconexión.
*   **Valor:** Experiencia confiable en red inestable (San Juan de los Morros), batería duradera para drivers, y trazabilidad completa para auditoría.
*   **Módulos:** Backend (WS `/ws/driver/track`, Redis Pub/Sub, Celery persistencia), App Driver (geolocator, búfer local, reconexión), App Cliente (mapa en vivo, aviso 45s), Consola Super Admin (mapa operaciones).

---

## 2. Actores
*   `DRIVER`: Transmite GPS, usa deslizadores de seguridad, gestiona batería.
*   `CUSTOMER`: Visualiza posición en mapa, recibe notificación llegada.
*   `SUPER_ADMIN`: Monitorea flota en tiempo real, reasigna manualmente.

---

## 3. Modelo de Datos (Confirmado + Delta)

### `delivery_tracking` (Historial persistente — Architecture §2.1)
*   Se inserta **cada 3 minutos** O en **cambio de estado** (hito).
*   **No** se inserta por cada ping WS (eso va a Redis efímero).

### Nueva tabla: `driver_location_ephemeral` (Redis — TTL 10 min)
*   Clave: `driver:location:{order_id}` → `{lat, lng, heading, battery, updated_at}` (JSON).
*   TTL: 10 min desde último ping. Expiración = driver offline.

### Nueva tabla: `geofence_events` (Auditoría de geo-cercas)
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `order_id` | UUID | FK `orders.id` |
| `driver_id` | UUID | FK `users.id` |
| `event_type` | VARCHAR(30) | `RESTAURANT_APPROACH`, `CUSTOMER_ARRIVAL` |
| `triggered_by` | VARCHAR(20) | `AUTO_GPS` o `MANUAL_DRIVER` |
| `distance_m` | NUMERIC(10,2) | Distancia al momento del evento |
| `accuracy_m` | NUMERIC(10,2) | Precisión GPS reportada |
| `created_at` | TIMESTAMPTZ | Default `NOW()` |

---

## 4. Requisitos Funcionales (EARS)

### 4.1. Invariantes del Sistema (Ubícuos)
*   **RF-TRK-01:** EL SISTEMA usará **Redis Pub/Sub** (`order:{order_id}:location`) para distribución WS entre instancias FastAPI. **Ningún** worker mantiene estado WS en memoria local.
*   **RF-TRK-02:** EL SISTEMA persistirá en `delivery_tracking` **cada 3 minutos** O en **hito de estado** (`PREPARING→READY_FOR_PICKUP`, `READY_FOR_PICKUP→ON_THE_WAY`, `ON_THE_WAY→ARRIVED_AT_CUSTOMER`, `ARRIVED_AT_CUSTOMER→PAYMENT_2_VERIFYING`, `DELIVERED`).
*   **RF-TRK-03:** EL SISTEMA mantendrá `driver_location_ephemeral` en Redis con **TTL 10 min**. Expiración = driver considerado offline.

### 4.2. Perfiles de Consumo GPS (geolocator)
*   **RF-TRK-04:** EL SISTEMA (App Driver) aplicará perfiles según estado del driver:
    | Estado | Precisión | Frecuencia | Filtro distancia mínima |
    |--------|-----------|------------|-------------------------|
    | `INACTIVE` / Esperando asignación | `LocationAccuracy.low` | 60 s | 100 m |
    | `HACIA_RESTAURANTE` (`READY_FOR_PICKUP` asignado, aún no `ON_THE_WAY`) | `LocationAccuracy.medium` | 15 s | 30 m |
    | `ON_THE_WAY` (en ruta a cliente) | `LocationAccuracy.high` | 5-10 s | 15 m |
*   **RF-TRK-05:** EL SISTEMA mostrará **notificación visible** (foreground service Android) mientras GPS activo, con permisos `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `FOREGROUND_SERVICE_LOCATION`.

### 4.3. Geo-Cercas (Radio 100 metros)
*   **RF-TRK-06:** CUANDO driver esté a **< 100 m** de `restaurants.location` (cálculo Haversine local en app O `ST_DistanceSphere` en backend), EL SISTEMA:
    1. Resaltará botón **[He llegado al Local]** en app driver.
    2. Mostrará en Kanban restaurante: "Conductor en puerta".
    3. Registrará `geofence_events {event_type: RESTAURANT_APPROACH, triggered_by: AUTO_GPS}`.
*   **RF-TRK-07:** CUANDO driver esté a **< 100 m** de `user_addresses.location` **Y** precisión GPS `accuracy <= 50 m`, EL SISTEMA (backend):
    1. Transiciona orden a `ARRIVED_AT_CUSTOMER` (atómico, idempotente).
    2. Dispara Push FCM prioritaria al cliente: *"🛵 Tu repartidor está llegando... Ten a la mano el pago restante si aplica."*
    3. Desbloquea interfaz de cobro 50% final en app driver.
    4. Registra `geofence_events {event_type: CUSTOMER_ARRIVAL, triggered_by: AUTO_GPS}`.
*   **RF-TRK-08:** SI GPS falla (precisión > 50m O sin fix 60s), EL SISTEMA permitirá **llegada manual documentada**: driver desliza **[Confirmar Llegada Manual]** → backend valida `order_id`, `driver_id`, registra `geofence_events {triggered_by: MANUAL_DRIVER}`, y transiciona a `ARRIVED_AT_CUSTOMER`.

### 4.4. Resiliencia de Red — Búfer FIFO y Reconexión (App Driver)
*   **RF-TRK-09:** CUANDO WebSocket pierda conexión O red celular caiga, EL SISTEMA (Flutter Driver):
    1. Continuará leyendo GPS (`geolocator` background).
    2. Encolará puntos en **búfer FIFO en memoria** (máx **50 puntos** más recientes).
    3. Mantendrá `driver_location_ephemeral` actualizado en Redis (si hay red intermitente).
*   **RF-TRK-10:** CUANDO conectividad se restablezca, EL SISTEMA (Flutter Driver):
    1. Enviará **primero** el punto más reciente por WS (posición actual).
    2. Enviará **lote comprimido** de puntos históricos (últimos 50) para persistir en `delivery_tracking`.
    3. **Los puntos históricos NO activarán geo-cercas** (solo punto actual).

### 4.5. Experiencia del Cliente ante Caída de Señal
*   **RF-TRK-11:** SI app cliente no recibe ping de ubicación por **> 45 segundos**, EL SISTEMA (Flutter Customer):
    1. Mantendrá último marcador visible en **tono atenuado** (opacity 0.5).
    2. Mostrará aviso no intrusivo (Snackbar/Toast): *"Actualizando ubicación del repartidor..."*.
    3. **Nunca** arrojará error bloqueante ni cerrará vista de seguimiento.

### 4.6. Reasignación Administrativa (Super Admin)
*   **RF-TRK-12:** CUANDO `SUPER_ADMIN` reasigne orden `POST /admin/orders/{id}/reassign {new_driver_id}`, EL SISTEMA (transacción atómica):
    1. Valida orden en `READY_FOR_PICKUP` O `ON_THE_WAY`.
    2. Si `ON_THE_WAY` (ya recogió): **exige** `evidence_image_url` (foto de transferencia de custodia: comida en manos del nuevo driver).
    3. Actualiza `orders.driver_id = new_driver_id`, `updated_at = NOW()`.
    4. **Revoca inmediatamente** permisos del driver anterior: invalida su WS, borra `driver_location_ephemeral` de esa orden, envía Push `ORDER_REASSIGNED` al driver anterior.
    5. Notifica a nuevo driver (Push + WS).
    6. Registra en `audit_logs` con `action: REASSIGN_ORDER`, `details: {old_driver_id, new_driver_id, evidence_url?, reason}`.

---

## 5. Requisitos No Funcionales
*   **Latencia WS distribución:** `p95 < 50 ms` (Redis Pub/Sub → WS push).
*   **Throughput:** 8.000 drivers concurrentes → 8.000 pings/5s = 1.600 msg/s en Redis Pub/Sub (soportado).
*   **Batería:** Perfil `INACTIVE` consume < 5% batería/hora en Android típico.
*   **Precisión llegada:** `accuracy <= 50 m` requerido para auto-llegada; si no, manual.

---

## 6. Casos Límite y Concurrencia
*   **Driver entra/sale geo-cerca rápidamente:** Backend usa `SELECT ... FOR UPDATE` en `orders` para transición atómica a `ARRIVED_AT_CUSTOMER` (evita flip-flop).
*   **Dos admins reasignan mismo pedido:** `UPDATE orders SET driver_id = :new WHERE id = :id AND driver_id = :current` → solo 1 éxito.
*   **Búfer lleno (50 pts) y sigue sin red:** Descarta el más antiguo (FIFO). Al reconectar, envía los 50 disponibles.
*   **Puntos históricos no disparan geo-cercas:** Backend ignora `geofence` para inserts masivos de `delivery_tracking` (flag `is_historical=true`).

---

## 7. Fuera de Alcance
*   Navegación paso-a-paso (turn-by-turn) — usa Google Maps / Waze externo.
*   Predicción ETA (no se muestra ETA ficticio por constitución).
*   Geocercas poligonales (solo radio circular 100m V1).

---

## 8. Criterios de Finalización (DoD)
*   [ ] WS `/ws/driver/track` + Redis Pub/Sub distribuido entre 3+ workers.
*   [ ] App Driver: perfiles GPS, foreground service, búfer 50 pts, reconexión con histórico.
*   [ ] Geo-cerca 100m auto + manual documentada + auditoría `geofence_events`.
*   [ ] Cliente: atenuación 45s + aviso no bloqueante.
*   [ ] Reasignación atómica con evidencia de custodia + revocación inmediata.
*   [ ] `pytest -v tests/integration/test_tracking.py` + `tests/concurrency/test_reassign.py`.
*   [ ] `ruff`, `mypy`, `flutter analyze` (driver app) pasan.