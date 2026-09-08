# 📱 Especificación Normalizada: Aplicación Cliente (CUSTOMER) — Offline-First (EARS)

> **Versión normalizada** — Completa flujo OTP, perfil, direcciones, catálogo, modificadores, carrito persistente (Hive), checkout, comprobantes, estados, historial. Fidelidad total al Design System.

---

## 1. Contexto y Objetivo
*   **Problema:** SDD original define carrito offline y catálogo pero omite: persistencia Hive completa (carrito + tokens + preferencias), manejo de reconexión, cambio de restaurante con confirmación, comprobantes PDF/imagen, historial con filtros, y fidelidad estricta a tokens de diseño (Outfit/Inter, tabular figures, paleta "Apetito Cálido").
*   **Valor:** Experiencia fluida sin red, confianza financiera (ver 50/50 siempre), y UI consistente.
*   **Módulos:** Flutter App (Android), compartiendo `models`, `api_client`, `design_system` con Driver/Restaurant/Admin.

---

## 2. Actores
*   `CUSTOMER`: Usuario final en Android (teléfono con WhatsApp).

---

## 3. Arquitectura Cliente (Riverpod + GoRouter + Hive)

### 3.1. Capas
```
lib/
├── core/
│   ├── config/          # Env, constants, design_system tokens
│   ├── network/         # Dio client, interceptors (auth, idempotency, retry)
│   ├── storage/         # Hive boxes: cart, auth_tokens, user_prefs, addresses_cache
│   └── utils/           # Decimal math (int minor units), formatters
├── features/
│   ├── auth/            # OTP flow, token management, auto-refresh
│   ├── catalog/         # Restaurants, menu, search, cache
│   ├── cart/            # CartController (Riverpod), Hive persistence
│   ├── checkout/        # Draft, payment report, 50/50 display
│   ├── tracking/        # Live map, WebSocket, 45s fallback
│   ├── orders/          # History, receipts, details
│   └── profile/         # Addresses, notifications, settings
└── shared/
    ├── models/          # Freezed/JSON serializable
    ├── widgets/         # Design System components
    └── providers/       # Riverpod providers globales
```

### 3.2. Hive Boxes (Persistencia Local)
| Box | Clave | Contenido | TTL / Limpieza |
|-----|-------|-----------|----------------|
| `cart_box` | `active_cart` | `CartState` (items, restaurant_id, address_id, quote_snapshot?) | Hasta checkout exitoso o logout |
| `auth_box` | `tokens` | `{access, refresh, expires_at, user_id, role}` | Refresh 30d, Access 15m |
| `auth_box` | `user_profile` | `User` model | Hasta logout |
| `address_box` | `addresses:{user_id}` | `List<UserAddress>` | Cache 24h, refresh on demand |
| `catalog_box` | `menu:{restaurant_id}` | `MenuResponse` | TTL 10 min (coincide con backend) |
| `catalog_box` | `restaurants_list` | `List<RestaurantSummary>` | TTL 10 min |

---

## 4. Requisitos Funcionales (EARS)

### 4.1. Invariantes del Sistema (Ubícuos)
*   **RF-CLI-01:** LA APP usará **Riverpod** para todo estado global. **Prohibido** `setState` para lógica de negocio, `GetX`, `Provider` antiguo.
*   **RF-CLI-02:** LA APP usará **GoRouter** para navegación + Deep Linking (`myapp://order/123`, `myapp://payment/verify`).
*   **RF-CLI-03:** LA APP representará **montos como enteros de unidades menores** (centavos USD / centésimas VES) en Dart. Conversión `Decimal` ↔ `int` solo en bordes (API client, UI formatters).
*   **RF-CLI-04:** LA APP aplicará **Design System estricto**:
    - Colores: `primary-500 #FF5A36`, `text-primary #1E2229`, `background-canvas #F8F9FA`, `surface-card #FFFFFF`, `success-500 #10B981`, `warning-500 #F59E0B`, `error-500 #DC2626`.
    - Tipografía: `Outfit` (títulos), `Inter` (cuerpo). **Todo monto**: `fontFeatures: [FontFeature.tabularFigures()]`.
    - Radios: Cards 16px, BottomSheets 24px (top), Buttons 12px, Badges 999px.
    - Sombras: Nivel 1 (cards), Nivel 2 (modales), Nivel 3 (FAB carrito).
*   **RF-CLI-05:** LA APP **nunca** calculará precios, totales, ni división 50/50. Solo mostrará valores del backend (`quote_snapshot`, `order` response).

### 4.2. Autenticación (OTP WhatsApp)
*   **RF-CLI-06:** CUANDO app inicie y no haya `auth_tokens` válidos, EL SISTEMA mostrará pantalla **Bienvenida** → botón **"Entrar con WhatsApp"**.
*   **RF-CLI-07:** CUANDO usuario ingrese teléfono, LA APP normalizará a E.164 (`+58414...`) y llamará `POST /auth/request-otp`.
*   **RF-CLI-08:** CUANDO OTP enviado, LA APP mostrará pantalla **Código de 6 dígitos** (6 inputs individuales, auto-focus, paste detection). Botón **"Reenviar"** deshabilitado 60s (cuenta regresiva).
*   **RF-CLI-09:** CUANDO usuario ingrese OTP, LA APP llamará `POST /auth/verify-otp` con `X-Idempotency-Key` (UUIDv4 generado localmente).
*   **RF-CLI-10:** SI OTP correcto, LA APP guardará tokens en `auth_box` (Keystore/EncryptedSharedPreferences), navegará a **Home**.
*   **RF-CLI-11:** SI OTP incorrecto/expirado, LA APP mostrará error inline + contador intentos. **Al 3er fallo**: muestra "Teléfono bloqueado 10 min" (info de backend).
*   **RF-CLI-12:** LA APP interceptará `401 UNAUTHENTICATED` en cualquier request → intentará `POST /auth/refresh` (rotación) **una vez**. Si falla → limpia tokens → navega a Login.

### 4.3. Perfil y Direcciones
*   **RF-CLI-13:** CUANDO usuario complete primer registro (backend crea usuario), LA APP solicitará **Nombre completo** (modal obligatorio) → `PATCH /auth/profile {full_name}`.
*   **RF-CLI-14:** LA APP expondrá **Direcciones** (CRUD): `GET /addresses`, `POST /addresses`, `PATCH /addresses/{id}`, `DELETE /addresses/{id}`.
*   **RF-CLI-15:** CUANDO usuario añada dirección, LA APP usará **Place Picker** (Google Maps) + campo "Referencia" (ej. "Frente a la plaza, portón verde"). Backend guarda `location` (PostGIS Point).
*   **RF-CLI-16:** LA APP cacheará direcciones en `address_box` 24h. `is_default` sincronizado con backend.

### 4.4. Catálogo y Exploración
*   **RF-CLI-17:** LA APP mostrará **Lista de Restaurantes** (`GET /restaurants?open=true`). Tarjeta: imagen 16:9, badge "Abierto"/"Cerrado" (verde/gris), metadatos: ⭐ rating, 🛵 distancia PostGIS (km, 1 decimal), ⏱️ tiempo estimado.
*   **RF-CLI-18:** LA APP cacheará lista 10 min (`catalog_box`). Pull-to-refresh invalida caché.
*   **RF-CLI-19:** CUANDO usuario toque restaurante, LA APP navegará a **Menú** (`GET /restaurants/{id}/menu`). Cache 10 min por restaurante.
*   **RF-CLI-20:** LA APP renderizará jerarquía: Categorías (tabs horizontal) → Productos (grid/list) → Modificadores (BottomSheet 75% pantalla).

### 4.5. Selector de Modificadores (BottomSheet)
*   **RF-CLI-21:** CUANDO usuario toque producto, LA APP abrirá `ModifierBottomSheet` (75% pantalla, modal).
*   **RF-CLI-22:** LA APP mostrará grupos: obligatorios (`min_selectable >= 1`) con chip `* Obligatorio · Elige N`, opcionales sin chip.
*   **RF-CLI-23:** UI: `max_selectable=1` → Radio buttons. `>1` → Checkboxes con contador visual. Al alcanzar máx, deshabilita resto.
*   **RF-CLI-24:** Precio extra visible a la derecha: `+ $1.50`. **Tabular figures**.
*   **RF-CLI-25:** Botón inferior **[Agregar al Carrito - $XX.XX]** (monto total línea) **deshabilitado (opacity 50%)** hasta que **todos** grupos obligatorios cumplan `min_selectable`.

### 4.6. Carrito Mono-Restaurante + Persistencia Offline
*   **RF-CLI-26:** LA APP mantendrá `CartState` en `cart_box` **inmediatamente** tras cada mutación (add, remove, qty, clear).
*   **RF-CLI-27:** CUANDO usuario intente añadir producto de **otro restaurante** (distinto `restaurant_id` al carrito actual), LA APP mostrará **Modal de Confirmación**:
    > *"Tu carrito ya contiene productos de 'Pizzería Roma'. ¿Deseas vaciar el carrito actual para comenzar a ordenar de 'Burger Express'?"*
    - **Sí** → limpia `cart_box`, añade nuevo item.
    - **No** → mantiene carrito actual, no añade.
*   **RF-CLI-28:** SI app se cierra/reinicia (offline), LA APP reconstruirá carrito desde `cart_box` en < 200ms. Usuario ve items, modificadores, cantidades intactos.
*   **RF-CLI-29:** LA APP mostrará **Barra Flotante Carrito** (bottom persistent) cuando `cart.items.notEmpty`:
    ```
    ┌────────────────────────────────────────────────────────┐
    │  🛒 3 ítems · Total: $15.01                            │
    │  Pagas hoy: $7.51 (50%)  │  Al recibir: $7.50 (50%)    │  [ Ver Carrito → ]
    └────────────────────────────────────────────────────────┘
    ```
    - Montos con **tabular figures**.
    - Colores: `first_half` en `warning-500` (ámbar), `second_half` en `text-secondary`.

### 4.7. Checkout y Cotización (POST /orders/draft)
*   **RF-CLI-30:** CUANDO usuario pulse **"Continuar al Pago"**, LA APP:
    1. Valida carrito no vacío + `address_id` seleccionado.
    2. Genera `X-Idempotency-Key` (UUIDv4).
    3. Envía `POST /orders/draft {items:[{product_id, quantity, modifier_ids}], address_id}`.
*   **RF-CLI-31:** SI `409 INSUFFICIENT_STOCK`, LA APP mostrará error específico por producto + botón "Actualizar carrito" (recarga menú).
*   **RF-CLI-32:** SI `422 DELIVERY_OUT_OF_COVERAGE`, LA APP mostrará: *"Lo sentimos, no cubrimos esa dirección aún."*
*   **RF-CLI-33:** SI `422 EXCHANGE_RATE_STALE`, LA APP mostrará: *"No hay tasa de cambio válida. Intenta más tarde."*
*   **RF-CLI-34:** EN ÉXITO (`201` con `order` en `PAYMENT_1_PENDING`), LA APP:
    1. Guarda `order.quote_snapshot` en `cart_box` (para mostrar comprobante offline).
    2. Navega a **Pantalla de Pago Inicial** mostrando **solo** `first_half_amount` (USD + VES congelado).
    3. Instrucciones: "Realiza Pago Móvil a nuestras cuentas. Ingresa referencia."

### 4.8. Reporte de Pago Inicial (50%)
*   **RF-CLI-35:** Pantalla Pago Inicial: campos `Banco Origen` (dropdown BDV, Banesco, Mercantil, Provincial, BNC, Tesoro, Otros), `Referencia` (últimos 4-6 dígitos), `Comprobante` (opcional: cámara/galería → sube a storage, devuelve URL).
*   **RF-CLI-36:** CUANDO usuario pulse **"He Pagado"**, LA APP llama `POST /payments/{order_id}/report {phase: FIRST_HALF, method: PAGO_MOVIL, reference_number, origin_bank, proof_image_url?}` con `X-Idempotency-Key`.
*   **RF-CLI-37:** SI `200` → navega a **Espera de Verificación** (estado `PAYMENT_1_VERIFYING`). Muestra: *"Tu pago está en revisión. Te notificaremos cuando la cocina empiece."*
*   **RF-CLI-38:** SI `409 ORDER_EXPIRED` (reserva vencida), LA APP muestra: *"Tu reserva expiró. Recalculando..."* → reintenta `POST /orders/draft` automáticamente (máx 1 vez).

### 4.9. Seguimiento y Estados (Push + WebSocket)
*   **RF-CLI-39:** LA APP recibirá **Push FCM** en transiciones clave: `PREPARING` (cocina empieza), `READY_FOR_PICKUP`, `ON_THE_WAY`, `ARRIVED_AT_CUSTOMER`, `DELIVERED`.
*   **RF-CLI-40:** EN `ON_THE_WAY`, LA APP conectará WebSocket `/ws/customer/track/{order_id}` → muestra marcador driver en mapa (Google Maps), actualiza en tiempo real.
*   **RF-CLI-41:** SI sin ping > 45s, LA APP aplica **RF-TRK-11** (marcador atenuado + aviso "Actualizando ubicación...").
*   **RF-CLI-42:** EN `ARRIVED_AT_CUSTOMER`, LA APP muestra botón **"El repartidor llegó"** (informativo) + monto pendiente `second_half` (USD + VES).

### 4.10. Pago Final y Comprobante
*   **RF-CLI-43:** SI pago final **efectivo**: driver confirma en su app → Push `DELIVERED` → LA APP muestra **"¡Pedido Entregado! 🎉"** + botón **"Ver Comprobante"**.
*   **RF-CLI-44:** SI pago final **Pago Móvil en sitio**: cliente hace pago → muestra comprobante a driver → driver confirma en su app → igual que arriba.
*   **RF-CLI-45:** Comprobante final (PDF/imagen generado por backend o renderizado local): `order_number`, `fecha`, `restaurante`, `items` (con modificadores), `subtotal`, `delivery_fee`, `platform_fee`, `total`, `first_half` (método, ref, verificado), `second_half` (método, ref/efectivo, verificado), `tasa_cambio`, `dirección_entrega`.

### 4.11. Historial de Pedidos
*   **RF-CLI-46:** LA APP expondrá **Historial** (`GET /orders?page=1&limit=20`) con filtros: estado, rango fechas, restaurante.
*   **RF-CLI-47:** Cada entrada: `order_number`, `fecha`, `restaurante`, `total`, `estado` (badge color Design System), `acción` (Ver detalle / Reordenar / Comprobante).
*   **RF-CLI-48:** **Reordenar**: clona items al carrito (valida stock/precios actuales vía `POST /orders/draft`).

### 4.12. Reconexión y Resiliencia
*   **RF-CLI-49:** LA APP implementará **reintentos exponenciales** (max 3, base 2s) en fallos de red 5xx / timeout. `X-Idempotency-Key` persistido por operación para seguridad.
*   **RF-CLI-50:** LA APP detectará conectividad (`connectivity_plus`) → mostrará banner superior **"Sin conexión. Los cambios se sincronizarán al volver."** (no bloqueante).

---

## 5. Requisitos No Funcionales
*   **Arranque en frío:** < 2s a Home (tokens válidos).
*   **Memoria:** < 150 MB RAM típico.
*   **Batería:** Sin GPS activo en cliente (solo driver).
*   **Accesibilidad:** WCAG 2.1 AA, contraste 4.5:1, touch targets ≥ 48×48 dp, etiquetas semánticas, talkback/voiceover.

---

## 6. Casos Límite
*   Carrito con items → usuario cambia de restaurante → confirma vaciar → nuevo item añadido → offline → online → `POST /orders/draft` usa nuevo restaurante.
*   OTP llega tarde (WhatsApp retraso): usuario pulsa "Reenviar" tras 60s → nuevo OTP invalida anterior (Redis GETDEL).
*   Pago inicial reportado → usuario cierra app → Push `PREPARING` llega → app abre en detalle orden.
*   Historial vacío → estado empty ilustrado + CTA "Explorar restaurantes".

---

## 7. Fuera de Alcance (V1)
*   Calificaciones / reseñas restaurantes.
*   Favoritos / listas de deseos.
*   Cupones / descuentos / promociones.
*   Chat con driver/restaurante.
*   Modo oscuro (Light Theme First V1).

---

## 8. Criterios de Finalización (DoD)
*   [ ] `flutter analyze` 0 warnings.
*   [ ] `flutter test` (unit + widget) > 90% cobertura features.
*   [ ] `flutter drive` (integration) flujo completo: OTP → catálogo → carrito → draft → pago 1 → tracking → entrega → comprobante.
*   [ ] Offline: kill app con carrito → reabre → carrito intacto.
*   [ ] Cambio restaurante: modal confirmación → carrito limpio → nuevo item.
*   [ ] Design System: tokens exactos, tabular figures en TODOS los montos, Outfit/Inter cargados.
*   [ ] Commits `feat(client): ...` Conventional Commits.