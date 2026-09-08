# 💻 Especificación de Paneles de Control (Restaurantes y Super Admin)

Este documento define las interfaces operativas, los permisos de visualización y las acciones críticas disponibles para los socios comerciales (Restaurantes) y los operadores del sistema (Super Admin).

## 1. Panel de Control del Restaurante (`RESTAURANT_ADMIN`)

El panel del restaurante está diseñado para ser ultrarrápido y funcional, accesible desde una tablet Android o un navegador web en PC. Su objetivo principal es la gestión de pedidos entrantes y el control de inventario básico.

### 1.1. Vistas y Secciones Clave
*   **Kanban de Pedidos en Tiempo Real:** Los pedidos se organizan en columnas según la máquina de estados:
    1.  *Nuevos (Ya pagados - 50% inicial verificado):* Aquí aparecen los pedidos que acaban de pasar a estado `PREPARING` sin reconocimiento de cocina (`acknowledged_at IS NULL`). El sistema emite una alerta sonora distintiva en la app para llamar la atención del cocinero.
    2.  *En Preparación:* Pedidos en `PREPARING` ya reconocidos por cocina (`acknowledged_at NOT NULL`). El administrador puede hacer clic en "Comida Lista" (`READY_FOR_PICKUP`).
    3.  *Listos para Recoger:* Pedidos en `READY_FOR_PICKUP` esperando al repartidor.
*   **Historial del Día (vista separada, no columna Kanban):** Listado de pedidos `DELIVERED`, `CANCELLED`, `CANCELLED_WITH_REFUND` y `DELIVERY_FAILED` durante la jornada para auditoría interna del local.

*   **Gestión Rápida de Menú (Toggle de Stock):**
    *   Una vista simplificada de lista donde el administrador puede encender o apagar rápidamente la disponibilidad (`is_available`) de los platos o modificadores si se agotaron los ingredientes en el día.

---

## 2. Consola del Super Administrador (`SUPER_ADMIN`)

Es el centro de comando global de la plataforma, accesible exclusivamente mediante navegador web de escritorio con autenticación de doble factor (2FA).

### 2.1. Secciones de Control Global
*   **Conciliación de Pagos Móviles (Finanzas):**
    *   Una bandeja de entrada con todos los pagos en estado `PENDING` (tanto del primer 50% como del segundo si aplica digitalmente).
    *   Muestra el número de referencia, el banco de origen, el monto reportado y el comprobante visual (imagen).
    *   Botones de acción rápida: **[Aprobar y Pasar a Preparación]** o **[Rechazar (Exigir Nueva Referencia)]**.
*   **Gestión de Socios (Restaurantes y Repartidores):**
    *   Formularios para dar de alta nuevos comercios, asignar sus coordenadas geográficas exactas (o coordenadas de PostGIS) y definir sus comisiones porcentuales.
    *   Creación manual de cuentas para nuevos repartidores con generación de credenciales temporales.
*   **Mapa de Operaciones en Vivo (Monitoreo):**
    *   Una vista general con un mapa interactivo (basado en WebSockets y Redis) donde el Super Admin puede ver en tiempo real la posición de todos los repartidores activos y el estado actual de las entregas en curso en San Juan de los Morros.
    *   Herramienta de reasignación manual de repartidores en caso de incidencias o averías reportadas.

---

## 3. Reglas de Seguridad y Auditoría de Acciones Admin

1.  **Inmutabilidad de Registros Financieros:** Ningún `SUPER_ADMIN` puede eliminar un registro de la tabla `payments` o `order_financials`. Si ocurre un error humano en la validación de un pago, el sistema obliga a crear una transacción compensatoria o un ajuste documentado, protegiendo la auditoría de caja.
2.  **Registro de Actividad (Audit Trail):** Toda acción ejecutada en el panel de administración (aprobar pagos, bloquear usuarios, encender/apagar restaurantes) debe registrarse en una tabla de logs (`audit_logs`) guardando el `admin_user_id`, la acción realizada, la marca de tiempo y la dirección IP.