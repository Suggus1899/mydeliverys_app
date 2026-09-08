# 🎨 Sistema de Diseño Visual (Design System) — mydeliverys_app

Este documento define la identidad visual, tokens de diseño, tipografía, componentes reutilizables y patrones de interfaz de usuario (UI/UX) para las aplicaciones de **Cliente, Repartidor, Restaurante** y la **Consola de Super Admin**.

---

## 1. Filosofía y Principios de Diseño

1.  **Concepto de Marca: "Apetito Cálido y Confiable":**
    *   **Psicología del Color y Apetito:** Los tonos cálidos (naranja coral y bermellón) estimulan fisiológicamente el apetito y transmiten agilidad y cercanía sin resultar agresivos.
    *   **Regla de Moderación del Primario (Acción Principal Única):** Si todo es naranja, nada destaca. El color primario se reserva estrictamente para la acción principal de cada pantalla (ej. botones "Pedir Ahora", "Confirmar Pago", precio final y badge del estado activo).
2.  **Enfoque de Implementación: Light Theme First (V1):**
    *   La versión 1 prioriza un **Tema Claro pulcro y luminoso**. El fondo actúa como un lienzo blanco/gris claro donde las fotografías de hamburguesas, empanadas, pizzas y comida local son las verdaderas protagonistas.
    *   El modo oscuro queda planificado para fases posteriores (ej. optimización de batería nocturna para repartidores).
3.  **Tipografía Amigable y Precisión Financiera:**
    *   Titulares en `Outfit` para cercanía y modernidad.
    *   Textos y montos en `Inter` con cifras tabulares fijas para que la división 50/50 (`$7.51` y `$7.50`) nunca oscile visualmente.

---

## 2. Paleta Oficial: "Apetito Cálido y Confiable"

### 2.1. Color Primario (El Sello de la Marca)
*   **Tono:** **Naranja Coral / Rojo Bermellón Suave** (`#FF5A36`).
*   **Sensación:** Energía, rapidez, hambre, cercanía y calidez.
*   **Tokens:**
    *   `primary-500` (`#FF5A36`): Color principal para botones primarios ("Pedir Ahora", "Confirmar Pago"), logos y acentos destacados.
    *   `primary-600` (`#E04422`): Estado presionado / active.
    *   `primary-100` (`#FFEBE6`): Fondos sutiles para chips seleccionados y avisos primarios.

### 2.2. Color Secundario y Textos (Gris Carbón Profundo)
*   **Tono:** **Gris Carbón Profundo** (`#1E2229` y `#2A2F3A`).
*   **Justificación Ergonómica:** El negro puro (`#000000`) genera fatiga visual en pantallas OLED/LCD móviles. Un gris carbón muy oscuro proporciona máxima nitidez tipográfica, excelente contraste (cumpliendo WCAG 2.1 AAA) y elegancia moderna.
*   **Tokens:**
    *   `text-primary` (`#1E2229`): Títulos principales, nombres de restaurantes, precios.
    *   `text-secondary` (`#5A6270`): Descripciones de platos, dirección, metadatos secundarios.
    *   `text-tertiary` (`#8C95A6`): Placeholders, subtítulos menores y separadores.

### 2.3. Fondo de Pantalla y Superficies (El Lienzo Claro)
*   **Tono:** **Blanco Marfil / Gris Muy Claro** (`#F8F9FA` y `#FFFFFF`).
*   **Justificación:** Las fotografías de comida necesitan respirar. Un fondo claro y luminoso hace que los colores de los ingredientes resalten de forma llamativa.
*   **Tokens:**
    *   `background-canvas` (`#F8F9FA`): Fondo general de la aplicación.
    *   `surface-card` (`#FFFFFF`): Superficie de tarjetas de restaurantes, productos y bottom sheets.
    *   `border-subtle` (`#E9ECEF`): Divisores y bordes sutiles entre secciones.

### 2.4. Colores Funcionales (Estados de la App y Pagos)
*   **Éxito / Pagos Verificados (50% Aprobado):**
    *   Token: `success-500` (`#10B981` / Verde Esmeralda Menta).
    *   Fondo suave: `success-100` (`#D1FAE5`).
    *   Uso: Primer 50% verificado, pedido entregado con éxito, saldo conciliado. Transmite seguridad financiera y tranquilidad.
*   **Alerta / Pendiente (Esperando Comprobante / En Revisión):**
    *   Token: `warning-500` (`#F59E0B` / Ámbar Dorado Cálido).
    *   Fondo suave: `warning-100` (`#FEF3C7`).
    *   Uso: Esperando que el cliente cargue la referencia o en espera de validación bancaria.
*   **Error / Rechazo / Cancelado:**
    *   Token: `error-500` (`#DC2626` / Rojo Coral Oscuro).
    *   Fondo suave: `error-100` (`#FEE2E2`).
    *   Uso: Referencia bancaria rechazada, restaurante no disponible, pedido cancelado.
*   **Flujo Operativo (Cocina y En Ruta):**
    *   `info-prep` (`#2563EB` / Azul Cobalto): Cocina preparando alimentos (`PREPARING`).
    *   `info-transit` (`#7C3AED` / Violeta Dinámico): Repartidor en ruta GPS (`ON_THE_WAY`).
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
    *   Nivel 3 (Botón flotante de carrito): `BoxShadow(color: Color(0xFFFF5A36).withOpacity(0.35), blurRadius: 16, offset: Offset(0, 6))`

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
