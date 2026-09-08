# 🎨 Sistema de Diseño Visual (Design System) — mydeliverys_app

Este documento define la identidad visual, tokens de diseño, tipografía, componentes reutilizables y patrones de interfaz de usuario (UI/UX) para las aplicaciones de **Cliente, Repartidor, Restaurante** y la **Consola de Super Admin**.

---

## 1. Filosofía y Principios de Diseño

1.  **Calidez Llanera y Modernidad:** Estética contemporánea inspirada en los tonos cálidos del atardecer llanero y la vitalidad de San Juan de los Morros, alejándose de interfaces genéricas o frías.
2.  **Transparencia Financiera Inmediata:** La división del pago 50/50 debe ser visualmente intuitiva. El usuario siempre debe saber qué paga ahora y qué pagará al repartidor al recibir.
3.  **Resiliencia Sensorial en Entornos Reales:**
    *   *Repartidores en Moto:* Interfaz de alto contraste legible bajo la intensa luz solar del mediodía y operable con guantes mediante gestos deslizantes (*Swipe-to-Action*).
    *   *Cocinas en Hora Pico:* Interfaz táctil de gran formato para tablets con alertas acústicas y códigos de color de alta visibilidad.

---

## 2. Tokens de Color (Color Palette)

### 2.1. Colores de Marca y Acento
| Token | Código HEX | Rol Semántico |
| :--- | :--- | :--- |
| `primary-500` | `#FF5722` | **Naranja San Juan:** Color primario, llamadas a la acción principales, marca. |
| `primary-600` | `#E64A19` | Estado presionado / hover del primario. |
| `primary-100` | `#FFCCBC` | Fondos de alertas primarias y chips seleccionados. |
| `secondary-500`| `#10B981` | **Verde Esmeralda:** Éxito, pagos verificados, entregas completadas y frescura. |
| `secondary-600`| `#059669` | Estado presionado del secundario. |
| `secondary-100`| `#D1FAE5` | Fondos de badges de éxito. |

### 2.2. Superficies y Neutros (Modo Claro vs Modo Oscuro)

```text
Modo Claro (Light Theme)               Modo Oscuro (Dark Theme)
┌──────────────────────────────┐       ┌──────────────────────────────┐
│ Background: #F8F9FA          │       │ Background: #121214          │
│ Surface (Cards): #FFFFFF     │       │ Surface (Cards): #1E1E24     │
│ Border / Divider: #E5E7EB    │       │ Border / Divider: #2C2C34    │
│ Text Primary: #1F2937        │       │ Text Primary: #F9FAFB        │
│ Text Secondary: #6B7280      │       │ Text Secondary: #9CA3AF      │
└──────────────────────────────┘       └──────────────────────────────┘
```

### 2.3. Semáforo Funcional de Estados del Pedido (`OrderStatus`)
Cada estado de la orden tiene asignado un color inmutable en badges y barras de progreso:

| Estado | Color HEX | Significado Visual |
| :--- | :--- | :--- |
| `DRAFT` | `#6B7280` | Gris Neutro: Cotización en proceso |
| `PAYMENT_1_PENDING` | `#F59E0B` | Ámbar Dorado: Esperando pago del 50% |
| `PAYMENT_1_VERIFYING`| `#8B5CF6` | Violeta Eléctrico: Verificando referencia bancaria |
| `PREPARING` | `#3B82F6` | Azul Cobalto: Cocina preparando alimentos |
| `READY_FOR_PICKUP` | `#06B6D4` | Cian: Esperando recolección del repartidor |
| `ON_THE_WAY` | `#F97316` | Naranja Dinámico: Pedido en tránsito GPS en vivo |
| `ARRIVED_AT_CUSTOMER`| `#EC4899`| Rosa / Magenta: Repartidor en puerta |
| `PAYMENT_2_VERIFYING`| `#F59E0B`| Ámbar Dorado: Cobro del 50% contra entrega |
| `DELIVERED` | `#10B981` | Verde Esmeralda: Pedido completado con éxito |
| `CANCELLED` / `REJECTED` | `#EF4444` | Rojo Carmesí: Cancelado o reembolsado |

---

## 3. Tipografía (Google Fonts)

*   **Tipografía de Títulos y Pantallas:** **`Outfit`** (Geométrica, moderna, cálida y con excelente legibilidad en pantallas AMOLED).
*   **Tipografía de Contenido y Datos:** **`Inter`** (Estándar de legibilidad de alta densidad).
*   **Regla Financiera de Números Tabulares:** En Flutter, toda visualización de montos (`$7.51`, `$7.50`, saldos) DEBE utilizar la variante de números tabulares para evitar que los decimales oscilen al cambiar dígitos:
    ```dart
    fontFeatures: [const FontFeature.tabularFigures()]
    ```

### 3.1. Escala Tipográfica
| Estilo | Fuente | Tamaño | Peso | Uso Principal |
| :--- | :--- | :--- | :--- | :--- |
| `Display Large` | Outfit | 32 px | Bold (700) | Títulos de bienvenida, total en checkout |
| `Headline Medium`| Outfit | 22 px | SemiBold (600) | Nombres de restaurantes, títulos de sección |
| `Title Medium` | Outfit | 18 px | SemiBold (600) | Títulos de platos, encabezados de tarjetas |
| `Body Large` | Inter | 16 px | Regular (400) | Descripciones de platos, notas |
| `Body Medium` | Inter | 14 px | Regular (400) | Textos informativos secundarios |
| `Label Large` | Inter | 15 px | Medium (500) | Botones de acción principal |
| `Financial Split`| Inter | 16 px | Bold (700) | Indicador del desglose 50% / 50% |

---

## 4. Componentes Base y Geometría

*   **Radios de Borde (`BorderRadius`):**
    *   Tarjetas (`Cards`): `16 px`
    *   Hojas inferiores (`BottomSheets`): `24 px` (solo esquinas superiores)
    *   Botones de acción (`Buttons`): `12 px`
    *   Badges y Chips: `999 px` (Pill shape)
*   **Elevaciones y Sombras:**
    *   Nivel 1 (Tarjetas en reposo): `BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 10, offset: Offset(0, 4))`
    *   Nivel 2 (Modales y BottomSheets): `BoxShadow(color: Colors.black.withOpacity(0.12), blurRadius: 24, offset: Offset(0, -4))`
    *   Nivel 3 (Botón flotante de carrito): `BoxShadow(color: Color(0xFFFF5722).withOpacity(0.35), blurRadius: 16, offset: Offset(0, 6))`

---

## 5. Patrones de Interfaz y Experiencia de Usuario por Rol

### 5.1. Aplicación del Cliente (`CUSTOMER`)

#### 1. Tarjeta de Restaurante (`RestaurantCard`)
*   Imagen de portada con relación de aspecto 16:9 con esquinas redondeadas.
*   Badge flotante de estado: *"Abierto"* (Verde) o *"Cerrado"* (Gris).
*   Metadatos en fila inferior: Calificación ⭐ 4.8 · Distancia 🛵 1.8 km (calculada con PostGIS) · Tiempo estimado ⏱️ 25-35 min.

#### 2. Selector de Modificadores (`ModifierBottomSheet`)
*   Se abre como un BottomSheet modal que cubre el 75% de la pantalla.
*   Grupos obligatorios señalizados con chip: `* Obligatorio · Elige 1`.
*   Opciones con precio aditivo visible a la derecha: `+ $1.50`.
*   Validación reactiva: El botón inferior **[Agregar al Carrito - $12.50]** permanece deshabilitado en tono opaco hasta que se cumplan todos los `min_selectable` obligatorios.

#### 3. Barra Flotante del Carrito con Desglose 50/50
Ubicada en la parte inferior sobre el contenido:
```text
┌────────────────────────────────────────────────────────┐
│  🛒 3 ítems · Total: $15.01                            │
│  Pagas hoy: $7.51 (50%)  │  Al recibir: $7.50 (50%)    │  [ Ver Carrito → ]
└────────────────────────────────────────────────────────┘
```

---

### 5.2. Aplicación de Cocina para Restaurantes (`RESTAURANT_ADMIN`)
Diseñada para tablets táctiles montadas en la pared de la cocina:
*   **Kanban de 3 Columnas Horizontales:**
    1.  *Nuevos (Pagados 50%):* Tarjeta amarilla parpadeante. Al ingresar, el dispositivo emite un sonido distintivo de campana de cocina de 3 tonos.
    2.  *En Preparación:* Lista de ingredientes y modificadores en tipografía grande (20px) para lectura a 1 metro de distancia.
    3.  *Listos para Recoger:* Botón verde de confirmación de 60px de altura mínima para pulsación rápida con un solo dedo.
*   **Toggle de Stock Diario:** Interruptor deslizante grande junto a cada producto para marcar agotado en 1 segundo.

---

### 5.3. Aplicación del Repartidor (`DRIVER`)
Diseñada para uso en motocicleta y condiciones ambientales adversas:
*   **Modo Alto Contraste Solar:** Fondo blanco puro (`#FFFFFF`) con textos en negro absoluto (`#000000`) y acentos de advertencia en naranja fluorescente.
*   **Deslizador de Seguridad (*Swipe to Confirm*):**
    Para evitar pulsaciones accidentales producidas por lluvia, vibración de la moto o guantes, las acciones críticas sustituyen el botón de clic por un componente deslizante:
    ```text
    ┌────────────────────────────────────────────────────────┐
    │  [ 🛵 »»» Desliza para confirmar llegada al local ]   │
    └────────────────────────────────────────────────────────┘
    ```
    ```text
    ┌────────────────────────────────────────────────────────┐
    │  [ 💵 »»» Desliza para confirmar cobro de $7.50 ]     │
    └────────────────────────────────────────────────────────┘
    ```
*   **Pantalla de Cobro en Puerta:** Muestra el monto exacto del segundo 50% en divisas y su equivalente en bolívares calculados a la tasa de la orden.

---

### 5.4. Consola Web del Super Administrador (`SUPER_ADMIN`)
*   **Estética:** Dark Mode industrial elegante (`#0B0E14`), maximizando el espacio para visualización densa de datos sin scroll innecesario.
*   **Mapa de Operaciones en Tiempo Real:** Mapa interactivo con pines de colores según el estado del conductor (Libre, Recogiendo, En Camino).
*   **Bandeja de Conciliación Rápida:** Vista dividida: a la izquierda, lista de pagos pendientes; a la derecha, imagen ampliada del comprobante de Pago Móvil con botones rápidos de atajo de teclado: `[A] Aprobar` o `[R] Rechazar`.

---

## 6. Accesibilidad y Estándares WCAG 2.1 AA

1.  **Ratio de Contraste Mínimo:** Todo texto sobre cualquier fondo cumple un ratio de contraste de al menos `4.5:1` para texto estándar y `3.0:1` para textos grandes y elementos gráficos interactivos.
2.  **Área de Toque Mínima:** Ningún elemento interactivo o botón en las aplicaciones móviles mide menos de `48 x 48 dp` (en app de driver: mínimo `56 x 56 dp`).
3.  **Indicadores No Exclusivos por Color:** Todo estado que use color (ej. rojo para cancelado, verde para entregado) está acompañado de un icono representativo y un texto descriptivo para usuarios con daltonismo.
