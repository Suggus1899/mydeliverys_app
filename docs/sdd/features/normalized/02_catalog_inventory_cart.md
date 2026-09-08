# 🍔 Especificación Normalizada: Catálogo, Inventario y Carrito (EARS)

> **Versión normalizada** — Añade columnas de stock, reservas atómicas (15 min), interruptor comercial independiente, y unifica en EARS.

---

## 1. Contexto y Objetivo
*   **Problema:** El SDD original describe jerarquía de menú y modificadores pero **omite**: columnas de stock numérico en `products`/`modifiers`, reservas transaccionales con expiración, distinción entre "agotado por contador" vs "apagado por comerciante", y validación de stock en `POST /orders/draft`.
*   **Valor:** Evita sobreventa (race condition), permite productos ilimitados (bebidas), y da control operativo real al restaurante.
*   **Módulos:** Backend (Catálogo público, Admin menú, Checkout), Panel Restaurante (Kanban + Toggle stock), App Cliente (Carrito offline-first).

---

## 2. Actores
*   `CUSTOMER`: Explora, arma carrito, valida modificadores.
*   `RESTAURANT_ADMIN`: Gestiona categorías, productos, modificadores, **stock diario**, disponibilidad.
*   `SUPER_ADMIN`: Auditoría de catálogo global.

---

## 3. Modelo de Datos Extendido (Delta sobre Architecture §2.1)

### `products` — columnas añadidas
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `stock` | INTEGER | `NULL` | `NULL` = **ilimitado** (bebidas, salsas). `>=0` = unidades disponibles. |
| `track_stock` | BOOLEAN | `false` | Si `true`, el sistema decrementa `stock` y bloquea a 0. Si `false`, ignora contador. |

### `modifiers` — columnas añadidas
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `stock` | INTEGER | `NULL` | Igual semántica que productos. |
| `track_stock` | BOOLEAN | `false` | Igual semántica. |

### Nueva tabla: `order_reservations` (Reservas de inventario por cotización)
| Columna | Tipo | Restricciones | Descripción |
|---------|------|---------------|-------------|
| `id` | UUID | PK | Identificador |
| `order_id` | UUID | FK `orders.id`, NOT NULL, UNIQUE | Pedido al que pertenece la reserva |
| `reserved_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` | Momento de la reserva |
| `expires_at` | TIMESTAMPTZ | NOT NULL | `reserved_at + 15 min` (configurable) |
| `status` | VARCHAR(20) | NOT NULL, default `ACTIVE` | `ACTIVE`, `CONSUMED`, `EXPIRED`, `RELEASED` |
| `items` | JSONB | NOT NULL | `[{product_id, modifier_ids[], quantity, reserved_stock}]` snapshot |

---

## 4. Requisitos Funcionales (EARS)

### 4.1. Invariantes del Sistema (Ubícuos)
*   **RF-CAT-01:** EL SISTEMA expondrá `GET /restaurants/{id}/menu` con `is_available` calculado como: `is_available AND (NOT track_stock OR stock > 0)`.
*   **RF-CAT-02:** EL SISTEMA **nunca** confiará en precios, stock ni disponibilidad enviados por el cliente. `POST /orders/draft` recalcula **todo** en servidor.
*   **RF-CAT-03:** EL SISTEMA invalidará caché `cache:menu:{restaurant_id}` **inmediatamente** tras cualquier cambio en `is_available`, `track_stock`, `stock`, precios, o estructura de modificadores.

### 4.2. Dirigido por Eventos (CUANDO)

#### Gestión de Menú (Restaurant Admin)
*   **RF-CAT-04:** CUANDO `POST /admin/products` cree producto, EL SISTEMA validará `base_price >= 0`, `category_id` pertenezca al restaurante del operador, y persistirá con `track_stock=false, stock=NULL` por defecto.
*   **RF-CAT-05:** CUANDO `PATCH /admin/products/{id} {stock, track_stock, is_available}`, EL SISTEMA actualizará y **publicará evento** `menu.changed {restaurant_id}` en Redis Pub/Sub para invalidar caché.
*   **RF-CAT-06:** CUANDO `track_stock=true` y `stock` llegue a `0` por decremento, EL SISTEMA pondrá `is_available=false` **automáticamente** y emitirá evento de invalidación.

#### Reserva de Inventario (Checkout)
*   **RF-CAT-07:** CUANDO `POST /orders/draft` valide items, EL SISTEMA ejecutará **en una sola transacción**:
    1. Verificar restaurante `is_open=true, is_active=true`.
    2. Verificar cada producto: `is_available=true` Y (`track_stock=false` O `stock >= quantity`).
    3. Verificar cada modificador: `is_available=true` Y (`track_stock=false` O `stock >= quantity`).
    4. **Reservar** stock: `UPDATE products SET stock = stock - quantity WHERE id = :pid AND track_stock=true AND stock >= :quantity` (similar para modifiers).
    5. Insertar en `order_reservations` con `status=ACTIVE`, `expires_at = NOW() + 15 min`, snapshot JSONB.
    6. Calcular totales, distancia PostGIS, fees, división 50/50.
    7. Insertar `orders` en estado `PAYMENT_1_PENDING` con `reservation_id` (FK implícita vía `order_reservations.order_id`).
*   **RF-CAT-08:** CUANDO la reserva expire (`expires_at < NOW()`) y `status=ACTIVE`, **job Celery** cada 1 min ejecutará: `UPDATE order_reservations SET status=EXPIRED WHERE status=ACTIVE AND expires_at < NOW()` y **repondrá** stock: `UPDATE products SET stock = stock + reserved_qty FROM order_reservations ... WHERE status=EXPIRED`.

#### Verificación de Pago y Consumo de Reserva
*   **RF-CAT-09:** CUANDO `POST /admin/payments/{id}/verify` marque `VERIFIED` y transicione orden a `PREPARING`, EL SISTEMA actualizará `order_reservations SET status=CONSUMED WHERE order_id = :oid AND status=ACTIVE`. **No** vuelve a descontar stock (ya se descontó en reserva).
*   **RF-CAT-10:** CUANDO `POST /admin/payments/{id}/reject` rechace pago y orden vuelva a `PAYMENT_1_PENDING`, EL SISTEMA **mantendrá** reserva `ACTIVE` (no libera) mientras `expires_at > NOW()`. Cliente puede reintentar reporte dentro del plazo original.
*   **RF-CAT-11:** CUANDO orden sea `CANCELLED` (cliente desiste en `PAYMENT_1_PENDING`) O `CANCELLED_WITH_REFUND` (contingencia en `PREPARING`), EL SISTEMA pondrá `order_reservations.status=RELEASED` y **repondrá** stock **solo si** la orden **no** llegó a `PREPARING` (regla: "cancelaciones posteriores a preparación no reponen alimentos automáticamente").

### 4.3. Dirigido por Estados (MIENTRAS)
*   **RF-CAT-12:** MIENTRAS `order_reservations.status = ACTIVE`, EL SISTEMA **bloqueará** las unidades reservadas para otros pedidos (el `UPDATE ... WHERE stock >= qty` en RF-CAT-07 fallará para esos items).
*   **RF-CAT-13:** MIENTRAS carrito en app cliente, EL SISTEMA (Flutter) validará `min_selectable/max_selectable` localmente, pero **backend** revalidará en `POST /orders/draft` (RF-CAT-07.2-3).

### 4.4. Manejo de Errores (SI ... ENTONCES)
*   **RF-CAT-14:** SI `POST /orders/draft` falle reserva por stock insuficiente (race condition), ENTONCES `409 CONFLICT` con `error_code: "INSUFFICIENT_STOCK"`, `data: {product_id, available, requested}`. **No** crea orden parcial.
*   **RF-CAT-15:** SI cliente intente añadir producto de **otro restaurante** al carrito, ENTONCES Flutter mostrará modal de confirmación (vaciar carrito actual) **antes** de permitir la acción (política mono-restaurante).
*   **RF-CAT-16:** SI `PATCH /admin/products` intente poner `track_stock=true` con `stock=NULL` o negativo, ENTONCES `422 UNPROCESSABLE ENTITY` con `error_code: "INVALID_STOCK_CONFIG"`.

### 4.5. Opcional / Configuración (DONDE)
*   **RF-CAT-17:** DONDE `SUPER_ADMIN` configure `inventory.reservation_ttl_minutes` (default 15), EL SISTEMA usará ese valor para `expires_at` y job de expiración.

---

## 5. Requisitos No Funcionales
*   **Atomicidad:** RF-CAT-07 ejecuta en **transacción serializable** (o `SELECT ... FOR UPDATE` en productos/modificadores) para evitar sobreventa.
*   **Caché:** `GET /menu` servido 100% desde Redis (TTL 10 min + invalidación reactiva). `p95 < 50 ms`.
*   **Concurrencia:** Test obligatorio — 20 clientes compran 3 unidades → exactamente 3 éxitos, stock final 0, nunca negativo.

---

## 6. Casos Límite
*   Producto con `track_stock=false` + `stock=NULL`: siempre disponible, nunca se reserva ni decrementa.
*   Modificador opcional (`min_selectable=0`) con stock limitado: se reserva solo si cliente lo selecciona.
*   Reserva expira **mientras** cliente está en pantalla de pago: app detecta `409` al reintentar reporte y muestra "Tu reserva expiró, recalculando...".

---

## 7. Fuera de Alcance
*   Stock multi-sede / bodega central.
*   Alertas automáticas de reabastecimiento (solo toggle manual V1).
*   Productos compuestos (recetas con ingredientes compartidos).

---

## 8. Criterios de Finalización (DoD)
*   [ ] Migración Alembic crea columnas `stock`, `track_stock` en `products`/`modifiers` y tabla `order_reservations`.
*   [ ] `POST /orders/draft` reserva atómicamente + prueba concurrencia 20 hilos / 3 stock.
*   [ ] Job Celery `expire_reservations` repone stock y marca `EXPIRED`.
*   [ ] `POST /admin/payments/verify` consume reserva sin doble descuento.
*   [ ] `ruff`, `mypy`, `pytest -v tests/unit/test_inventory.py --cov=app.services.inventory --cov-report=term-missing` → 100%.