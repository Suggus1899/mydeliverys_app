# 🍳 Especificación Normalizada: Aplicación Restaurante (RESTAURANT_ADMIN) — Tablet Android + Web (EARS)

> **Versión normalizada** — Kanban 3 columnas + Historial separado, toggle stock 1s, alerta sonora 3 tonos, reconocimiento "Empezar", fidelidad Design System.

---

## 1. Contexto y Objetivo
*   **Problema:** SDD original define Kanban pero mezcla estados financieros con operativos, omite: historial separado, reconocimiento explícito "Empezar", alerta sonora distinta, tipografía 20px para lectura a 1m, botón "Comida Lista" 60px, y variante tablet (landscape, kiosco).
*   **Valor:** Operación manos-libres en cocina calurosa, ruido alto, tablet montada en pared. Cero ambigüedad visual.
*   **Módulos:** Flutter Web (desktop) + Flutter Android Tablet (landscape, kiosk mode), compartiendo `models`, `api_client`, `design_system`.

---

## 2. Actores
*   `RESTAURANT_ADMIN`: Cocinero/gerente en tablet Android (pared) o PC cocina.

---

## 3. Variante Tablet/Kiosco del Design System

| Aspecto | Especificación |
|---------|----------------|
| **Orientación** | Landscape forzado (tablet). Web: responsive ≥ 1024px. |
| **Modo Kiosco Android** | `SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky)` — oculta barra navegación/estado. |
| **Tipografía** | `Outfit` títulos, `Inter` cuerpo. **Mínimo 20px** en lista ingredientes/modificadores (lectura 1m). |
| **Touch Targets** | **Mínimo 60×60 dp** en botones Kanban (vs 48/56 general). |
| **Colores** | Paleta estándar (no solar). Badges estado: `PREPARING` → `warning-500 #F59E0B` (ámbar), `READY_FOR_PICKUP` → `success-500 #10B981` (verde). |
| **Sonido** | Alerta **3 tonos** (campana cocina) al entrar orden a "Nuevos". Archivo `assets/sounds/kitchen_bell_3tone.mp3`. |
| **Fondo** | `background-canvas #F8F9FA` (claro, limpio para fotos comida). |

---

## 4. Arquitectura Cliente (Riverpod + GoRouter + Hive + FCM)

### 4.1. Capas
```
lib/features/restaurant/
├── kanban/              # KanbanBoard (3 cols + Historial tab)
├── menu/                # Toggle stock diario (lista plana)
├── orders/              # Detalle orden, reconocimiento, comida lista
├── notifications/       # FCM handler (foreground/background)
└── settings/            # Impresora tickets (opcional V1), sonido
```

### 4.2. Hive Boxes Restaurant
| Box | Clave | Contenido |
|-----|-------|-----------|
| `auth_box` | `tokens` | Access/Refresh (Keystore/Web: HttpOnly cookie + CSRF) |
| `restaurant_box` | `current_restaurant` | `Restaurant` model (cache) |
| `restaurant_box` | `kanban_cache` | `KanbanState` (para恢复 rápido) |

### 4.3. FCM + Sonido
*   **RF-RES-01:** LA APP registrará token FCM en login `POST /restaurant/fcm-token {token}`.
*   **RF-RES-02:** CUANDO Push `NEW_ORDER_PREPARING` llegue (app en foreground/background/killed), LA APP reproducirá **alerta sonora 3 tonos** (`kitchen_bell_3tone.mp3`) a volumen máximo canal `Notification`/`Alarm` (Android). **No** usar canal `Media`.

---

## 5. Requisitos Funcionales (EARS)

### 5.1. Invariantes del Sistema (Ubícuos)
*   **RF-RES-03:** LA APP usará **Design System estándar** (no solar). Landscape tablet / Web responsive.
*   **RF-RES-04:** LA APP mantendrá **WebSocket** `/ws/restaurant/orders` para actualizaciones Kanban en tiempo real (Push FCM como fallback).
*   **RF-RES-05:** LA APP **nunca** calculará precios ni totales. Solo mostrará datos del backend.

### 5.2. Kanban — 3 Columnas Operativas + Historial Separado
*   **RF-RES-06:** LA APP renderizará **KanbanBoard** con 4 pestañas superiores: **[Nuevos] [En Preparación] [Listos para Recoger] [Historial]**.
*   **RF-RES-07:** Columna **"Nuevos (Pagados 50%)"** — Órdenes en `PREPARING` **SIN** `acknowledged_at` (recién verificadas). Tarjeta:
    - Fondo `warning-100 #FEF3C7`, borde `warning-500`.
    - Parpadeo suave (animación 1s infinite) **solo primeros 30s**.
    - Info: `order_number`, `cliente`, `distancia`, `items` (nombre + modificadores), `first_half` (método, verificado).
    - Botón principal: **[Empezar]** (60px alto, `primary-500`, `Label Large`).
*   **RF-RES-08:** Columna **"En Preparación"** — Órdenes `PREPARING` **CON** `acknowledged_at`. Tarjeta:
    - Fondo `surface-card #FFFFFF`.
    - Lista ingredientes/modificadores **`Inter` 20px, `FontWeight.w500`** (lectura 1m).
    - Badge tiempo transcurrido desde `acknowledged_at` (ej. "12 min").
    - Botón: **[Comida Lista]** (60px alto, `success-500`, `Label Large`).
*   **RF-RES-09:** Columna **"Listos para Recoger"** — Órdenes `READY_FOR_PICKUP`. Tarjeta:
    - Fondo `success-100 #D1FAE5`, borde `success-500`.
    - Info: `order_number`, `driver` (nombre/placa si asignado), `tiempo_en_espera`.
    - **Sin botones de acción** (esperando driver).
*   **RF-RES-10:** Pestaña **"Historial del Día"** — Órdenes `DELIVERED`, `CANCELLED`, `CANCELLED_WITH_REFUND`, `DELIVERY_FAILED` de **hoy** (timezone local). Filtros: estado, hora, monto. **No** columnas Kanban.

### 5.3. Reconocimiento y Transiciones (Operativo, No Financiero)
*   **RF-RES-11:** CUANDO cocinero toque **[Empezar]** en "Nuevos", LA APP llamará `POST /restaurant/orders/{id}/acknowledge` → backend: `orders.acknowledged_at = NOW()` (nueva columna). **No** cambia `status` (sigue `PREPARING`). LA APP mueve tarjeta visualmente a "En Preparación".
*   **RF-RES-12:** CUANDO cocinero toque **[Comida Lista]** en "En Preparación", LA APP llamará `POST /restaurant/orders/{id}/ready` → backend: `transition(PREPARING, READY_FOR_PICKUP)` + notifica drivers. LA APP mueve tarjeta a "Listos para Recoger".

### 5.4. Detalle de Orden (Modal/BottomSheet)
*   **RF-RES-13:** CUANDO toque tarjeta (cualquier columna), LA APP abrirá **Detalle Orden** (BottomSheet 90% altura tablet, modal centrado web):
    - Header: `order_number`, `estado` (badge color), `hora_creacion`.
    - Cliente: nombre, teléfono (tap → llama), dirección + referencia.
    - Items: nombre, cantidad, **modificadores con precio extra**, subtotal línea.
    - Totales: `subtotal`, `delivery_fee`, `platform_fee`, `total`, `first_half` (método, ref, verificado), `second_half` (pendiente).
    - Tasa cambio usada (USD→VES).
    - Botones según columna: "Empezar" / "Comida Lista" / "Reimprimir" (opcional).

### 5.5. Toggle Stock Diario (1 Segundo)
*   **RF-RES-14:** LA APP expondrá **Gestión de Menú** (pestaña/menú lateral): lista plana **Productos + Modificadores** con columnas: `nombre`, `categoría`, `precio`, `stock` (si `track_stock`), `is_available` (**Switch grande 56dp**).
*   **RF-RES-15:** CUANDO operador toque switch `is_available`, LA APP llamará `PATCH /admin/products/{id} {is_available}` (o modifiers) → **respuesta < 200ms** → actualiza UI local inmediatamente + invalida caché menú público (backend publica evento).
*   **RF-RES-16:** SI `track_stock=true` y `stock=0`, LA APP **deshabilitará** switch (gris) y mostrará badge **"Agotado (stock 0)"**. Operador debe reponer stock en backend para reactivar.

### 5.5. Impresión de Ticket (Opcional V1 - Preparado)
*   **RF-RES-17:** LA APP tendrá acción **[Imprimir Ticket]** en detalle orden (cuando impresora Bluetooth/USB conectada). Formato: 58mm/80mm térmica. Contenido: items, modificadores, mesa/cliente, hora. **No bloqueante** si falla impresora.

### 5.6. Reconexión y Recuperación
*   **RF-RES-18:** SI app reinicia (crash, actualización, tablet reiniciada), LA APP:
    1. Carga `kanban_cache` de Hive (último estado conocido).
    2. Llama `GET /restaurant/orders/kanban` (estado actual servidor).
    3. Hace **merge inteligente**: servidor gana, pero conserva scroll/posición local.
    3. Reproduce sonido si hay órdenes nuevas en "Nuevos" desde último cache.

### 5.7. Configuración y Sesión
*   **RF-RES-19:** LA APP permitirá: **Volumen alerta** (slider 0-100%), **Test sonido** (botón reproduce campana), **Modo kiosco** (toggle, persiste en Hive).
*   **RF-RES-20:** Sesión web: `refresh_token` en cookie `HttpOnly, Secure, SameSite=Lax` + CSRF. **No** Hive en navegador. Máx 8h (config `auth.session_max_hours_web`).

---

## 6. Requisitos No Funcionales
*   **Arranque en frío (tablet):** < 3s a Kanban (tokens válidos).
*   **Memoria:** < 200 MB RAM (tablet Android Go edition compatible).
*   **Latencia UI:** Tap → respuesta visual < 100ms (60fps scroll Kanban).
*   **Accesibilidad:** WCAG 2.1 AA. Contraste 4.5:1. TalkBack: labels semánticos en tarjetas/botones.
*   **Robustez cocina:** Resistente a grasa/humedad (tablet con funda). Touch funciona con guantes (área 60dp).

---

## 7. Casos Límite
*   Orden en "Nuevos" > 30s → para parpadeo, queda fondo ámbar fijo.
*   Driver llega mientras orden en "En Preparación" → Kanban muestra "Conductor en puerta" (badge azul `info-prep #2563EB`) en tarjeta.
*   Restaurante cierra (`is_open=false`) con órdenes en `PREPARING` → órdenes continúan normal, **no** se cancelan. Nuevas cotizaciones bloqueadas en backend.
*   Múltiples operadores mismo restaurante: WebSocket sincroniza Kanban en tiempo real (optimistic UI + server reconciliation).

---

## 8. Fuera de Alcance (V1)
*   Impresión automática al recibir orden (solo manual botón).
*   Gestión de mesas / comensales (solo delivery).
*   Reportes de ventas gráficos (solo historial lista).
*   Modo oscuro.

---

## 9. Criterios de Finalización (DoD)
*   [ ] `flutter analyze` 0 warnings (web + android).
*   [ ] Kanban 4 pestañas: 3 columnas operativas + Historial separado.
*   [ ] Alerta sonora 3 tonos + volumen configurable + test botón.
*   [ ] "Empezar" → `acknowledged_at` + mueve a "En Preparación" (sin cambio estado financiero).
*   [ ] "Comida Lista" 60px → `READY_FOR_PICKUP` + notifica drivers.
*   [ ] Toggle stock 1s + respuesta < 200ms + invalida caché público.
*   [ ] Modo kiosco Android: inmersivo, landscape forzado, persiste.
*   [ ] Tipografía 20px ingredientes/modificadores + Outfit/Inter + tabular figures montos.
*   [ ] `flutter test` + `integration_test` (tablet emulator + web Chrome).
*   [ ] Commits `feat(restaurant): ...` Conventional Commits.