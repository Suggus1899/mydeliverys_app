# 🍔 Especificación de Catálogo, Menú y Carrito

Este documento define la estructura jerárquica del menú de los restaurantes, la lógica estricta para la gestión de modificadores (extras y restricciones) y las reglas operativas del carrito de compras en el lado del cliente.

---

## 1. Estructura Jerárquica del Menú

Para garantizar que la interfaz de Flutter pueda renderizar el catálogo de forma fluida y estructurada, el backend expone los datos bajo la siguiente jerarquía de relaciones:

```text
Restaurant (1) ──> (N) Categories (ej. Hamburguesas, Bebidas, Promociones)
                       └──> (N) Products (ej. Hamburguesa Especial San Juan)
                              └──> (N) Modifier Groups (ej. Tipo de Queso, Extras)
                                     └──> (N) Modifiers (ej. Queso Cheddar, Tocineta Extra)
```

---

## 2. Lógica de Modificadores (Opciones y Extras)

Los modificadores permiten personalizar cada plato. Cada producto puede tener múltiples grupos de modificadores configurados con reglas estrictas de validación.

### 2.1. Reglas de Validación de Grupos (`modifier_groups`)
*   **`min_selectable` (Mínimo de opciones):**
    *   Si `min_selectable >= 1`, el grupo es **Obligatorio** (`is_required = true`). La app de Flutter no permite agregar el plato al carrito sin seleccionar el mínimo requerido (ej. "Término de la carne: 3/4").
    *   Si `min_selectable == 0`, el grupo es **Opcional** (ej. "Añadir salsas extras").
*   **`max_selectable` (Máximo de opciones):**
    *   Si `max_selectable == 1`, la UI en Flutter se comporta como un *Radio Button* (selección única exclusiva).
    *   Si `max_selectable > 1`, la UI se comporta como *Checkboxes* con límite numérico. Al alcanzar el máximo, las demás opciones se deshabilitan visualmente.
*   **Precios Aditivos (`extra_price`):**
    *   Cada modificador puede tener un `extra_price >= 0.00`.
    *   El costo total de la línea de producto es: 
      $$\text{item\_total} = (\text{product\_base\_price} + \sum \text{modifier\_extra\_price}) \times \text{quantity}$$

### 2.2. Validación de Seguridad en Servidor
El cliente Flutter valida en vivo para guiar al usuario, pero **el backend de FastAPI valida obligatoriamente al recibir el `POST /orders/draft`**:
1. Que los modificadores pertenezcan efectivamente a los grupos asignados a ese producto.
2. Que la cantidad de elecciones por grupo cumpla con `min_selectable <= seleccionados <= max_selectable`.
3. Que ningún modificador tenga estado `is_available = false`.

---

## 3. Reglas Operativas del Carrito de Compras

### 3.1. Política de Mono-Restaurante por Pedido
Para garantizar la frescura de los alimentos y la logística viable de los repartidores en moto en San Juan de los Morros:
*   Un pedido **solo puede contener productos de un único restaurante a la vez**.
*   **Comportamiento ante conflicto:** Si el usuario tiene ítems de "Pizzería Roma" e intenta añadir un producto de "Burger Express", la app móvil intercepta la acción mostrando un diálogo modal:
    > *"Tu carrito ya contiene productos de 'Pizzería Roma'. ¿Deseas vaciar el carrito actual para comenzar a ordenar de 'Burger Express'?"*
*   El carrito anterior solo se borra si el usuario confirma explícitamente.

### 3.2. Resiliencia de Red y Persistencia Local (Offline-First)
*   **Almacenamiento Local (Hive / Isar):** El carrito activo se persiste inmediatamente en el almacenamiento local del dispositivo del cliente.
*   **Tolerancia a Fallas de Conexión:** Si el usuario pierde la señal móvil mientras explora o arma su pedido, el carrito permanece intacto sin reiniciarse ni perder modificadores seleccionados.

### 3.3. Transición a Checkout y Generación de `DRAFT`
Cuando el usuario pulsa el botón **"Continuar al Pago"**:
1.  Flutter envía el payload de items y modificadores junto con el `address_id` seleccionado al endpoint `POST /orders/draft`.
2.  **Validaciones del Backend:**
    *   El restaurante está abierto (`is_open = true`) y activo (`is_active = true`).
    *   Todos los productos y modificadores están disponibles en stock (`is_available = true`).
    *   Calcula la distancia exacta en metros usando PostGIS entre el restaurante y la dirección seleccionada.
    *   Calcula el `delivery_fee` basado en la distancia por tramos de kilometraje.
    *   Calcula el total oficial y la división 50/50 (`FIRST_HALF_AMOUNT` y `SECOND_HALF_AMOUNT`).
3.  El pedido se registra en estado `DRAFT` con un **tiempo de expiración de 15 minutos**. Pasado ese tiempo sin reporte de pago, el borrador expira y se libera.