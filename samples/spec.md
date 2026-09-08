# 📋 Plantilla de Especificación SDD — mydeliverys_app (San Juan de los Morros)

> **Uso:** Copia esta plantilla para cada nueva funcionalidad o módulo dentro de una carpeta en `specs/NNN-<nombre-funcionalidad>/spec.md` o en `docs/sdd/features/`. Todas las especificaciones deben redactarse en **Español** y modelar el comportamiento exacto antes de escribir código.

---

# Spec NNN — [Nombre de la Funcionalidad en Español]

## 1. Contexto y Objetivo
*   **Problema que resuelve:** [Explicar en 1-2 párrafos la necesidad operativa o de negocio en San Juan de los Morros].
*   **Valor para el usuario / negocio:** [Por qué es indispensable para el flujo de delivery, el modelo financiero 50/50 o la logística local].
*   **Módulos impactados:** [Backend FastAPI / App Cliente Flutter / App Driver / App Restaurante / Consola Admin].

---

## 2. Usuarios y Actores Involucrados
Identificar los roles específicos de la matriz RBAC que interactúan con esta funcionalidad:
*   [ ] `CUSTOMER` (Cliente final vía App móvil Flutter con WhatsApp OTP).
*   [ ] `DRIVER` (Repartidor en moto con interfaz de alto contraste y geolocalización).
*   [ ] `RESTAURANT_ADMIN` (Cocina / Comercio con panel Kanban táctil para tablet).
*   [ ] `SUPER_ADMIN` (Operador central en consola web de monitoreo y conciliación).

---

## 3. Historias de Usuario
*   **H1:** Como `[Rol]` quiero `[acción específica]` para `[beneficio medible]`.
*   **H2:** Como `[Rol]` quiero `[acción específica]` para `[beneficio medible]`.

---

## 4. Requisitos Funcionales (Criterios de Aceptación en Notación EARS)
> Utiliza estrictamente la sintaxis formal de **EARS (Easy Approach to Requirements Syntax)**. Cada requisito debe ser atómico, verificable y con un ID único (`RF-x`).

### 4.1. Comportamiento Ubicuo (Invariantes del Sistema)
*   **RF-1:** EL SISTEMA deberá calcular todos los valores monetarios utilizando tipos `Decimal` en backend y `Numeric(10, 2)` en PostgreSQL, asignando el centavo impar al primer pago (`FIRST_HALF = ceil(total / 2 * 100) / 100`).
*   **RF-2:** EL SISTEMA deberá responder a todas las peticiones con la estructura JSON estándar `{"success": bool, "error_code": str|null, "message": str, "data": any}`.

### 4.2. Dirigido por Eventos (Event-Driven: `CUANDO`)
*   **RF-3:** CUANDO `[el cliente envíe el reporte de pago inicial con referencia bancaria a POST /payments/{id}/report]`, EL SISTEMA deberá `[registrar el pago en estado PENDING y transicionar la orden a PAYMENT_1_VERIFYING]`.
*   **RF-4:** CUANDO `[el Super Admin verifique el pago en la consola]`, EL SISTEMA deberá `[marcar el pago como VERIFIED, pasar la orden a PREPARING y emitir una notificación sonora al restaurante]`.

### 4.3. Dirigido por Estados (State-Driven: `MIENTRAS`)
*   **RF-5:** MIENTRAS `[la orden permanezca en estado ON_THE_WAY]`, EL SISTEMA deberá `[publicar las coordenadas GPS del conductor en Redis Pub/Sub cada 5 a 10 segundos para los clientes suscritos al WebSocket]`.
*   **RF-6:** MIENTRAS `[el cliente no haya completado los modificadores obligatorios de un plato]`, LA APP FLUTTER deberá `[mantener deshabilitado el botón de agregar al carrito con opacidad al 50%]`.

### 4.4. Manejo de Errores y Comportamiento No Deseado (Unwanted Behavior: `SI ... ENTONCES`)
*   **RF-7:** SI `[dos repartidores intentan aceptar la misma orden simultáneamente]`, ENTONCES EL SISTEMA deberá `[asignar atómicamente al primer solicitante mediante 'WHERE driver_id IS NULL' y devolver HTTP 409 Conflict con código 'ORDER_ALREADY_ASSIGNED' al segundo]`.
*   **RF-8:** SI `[el usuario supera la cuota permitida de peticiones en la ventana de tiempo]`, ENTONCES EL SISTEMA deberá `[retornar HTTP 429 Too Many Requests con la cabecera 'Retry-After' antes de ejecutar cualquier consulta en PostgreSQL]`.
*   **RF-9:** SI `[el cliente pierde la conexión a internet en San Juan de los Morros]`, ENTONCES LA APP FLUTTER deberá `[persistir el estado del carrito en Hive/Isar y mostrar un aviso no bloqueante de reconexión]`.

### 4.5. Opcional / Habilitado por Configuración (Optional Feature: `DONDE`)
*   **RF-10:** DONDE `[el cliente elija pagar el segundo 50% en efectivo contra entrega]`, EL SISTEMA deberá `[mostrar en la app del repartidor el selector de divisas USD/VES a la tasa fijada en la orden]`.

---

## 5. Requisitos No Funcionales y SLAs
*   **Rendimiento y Capacidad:** La API debe responder con una latencia $p_{95} < 200\text{ ms}$ bajo una carga concurrente nominal de **1.500 usuarios** y picos de hasta **8.000 usuarios activos simultáneos** (según `docs/sdd/architecture.md`).
*   **Rate Limiting:** Respetar los límites por usuario definidos en la arquitectura (ej. 3 OTPs / 10 min, 10 drafts / min, 60 lecturas / min).
*   **Seguridad:** Idempotencia obligatoria (`X-Idempotency-Key`) en toda transacción monetaria. Validación estricta en servidor de precios y disponibilidad.
*   **Diseño Visual (Design System):** Cumplimiento estricto de la paleta *"Apetito Cálido y Confiable"* (`#FF5A36` primario, `#1E2229` textos, `#F8F9FA` fondo claro, tipografía `Outfit` + `Inter` con números tabulares y contraste WCAG 2.1 AA).

---

## 6. Casos Límite y Concurrencia
*   **División Fraccionaria Impar:** Validación con montos como `$15.01` ($\rightarrow$ `$7.51` inicial / `$7.50` final).
*   **Agotamiento de Stock Concurrente:** Qué ocurre si se compra el último plato disponible en el mismo milisegundo.
*   **Desconexión del Repartidor:** Búfer FIFO de coordenadas en la app móvil ante pérdida de señal en zonas periféricas.
*   **Reintentos de Pago:** Toques repetidos del usuario protegidos por Redis `SET NX`.

---

## 7. Fuera de Alcance (Out of Scope)
> Especificar qué aspectos NO se construirán en esta iteración para proteger el alcance y evitar desviaciones.
*   *Ejemplo: No se incluye integración directa con pasarelas automáticas de bancos internacionales (Stripe); el cobro se realiza vía Pago Móvil nacional y efectivo.*
*   *Ejemplo: No se incluye soporte de múltiples restaurantes en un mismo carrito de compra.*

---

## 8. Criterios de Finalización (Definition of Done - DoD)
*   [ ] Todos los requisitos funcionales (`RF-x`) cuentan con al menos una prueba automatizada que los valide.
*   [ ] 100% de cobertura en pruebas unitarias para cualquier cálculo financiero del ledger 50/50 (`pytest -v`).
*   [ ] Pruebas de concurrencia ejecutadas satisfactoriamente para mitigar race conditions (`pytest -v tests/concurrency/`).
*   [ ] Análisis estático aprobado sin advertencias (`ruff check .` en backend, `flutter analyze` en mobile).
*   [ ] La interfaz cumple los tokens y componentes de `docs/sdd/design_system.md`.
*   [ ] Commits registrados siguiendo la convención Conventional Commits (`feat:`, `fix:`, `docs:`).

---

## 9. Dudas Abiertas y Aclaraciones
*   [ ] [NECESITA ACLARACIÓN] [Indicar cualquier decisión operativa o técnica pendiente de validación con el cliente o equipo].