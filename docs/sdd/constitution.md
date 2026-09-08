# 📜 Constitución del Proyecto (Delivery San Juan de los Morros)

Este documento define las reglas inquebrantables, principios de ingeniería y convenciones de desarrollo para la aplicación de delivery. **Ningún desarrollador (humano o IA) puede violar estas reglas.**

## 1. Principios Core
*   **Fuente de la Verdad:** La documentación SDD (Spec-Driven Development) es la única fuente de la verdad. Si el código diverge de la especificación, el código es incorrecto.
*   **Resiliencia de Red (Contexto Local):** La conexión en San Juan de los Morros puede fluctuar. La aplicación Flutter debe manejar transiciones offline/online con gracia (ej. guardar el carrito en caché local y reintentar peticiones fallidas).
*   **Integridad Financiera (Regla 50/50):** Ningún pedido puede pasar al estado "En Preparación" sin que el backend (Python) valide el pago del primer 50%. El estado del pago final (el otro 50%) debe bloquear el cierre del ciclo del pedido hasta ser confirmado. NUNCA se debe confiar en el cálculo de precios proveniente del frontend.
*   **Seguridad en Concurrencia y Cero Doble Asignación:** Todo endpoint transaccional o de despacho (asignación de pedidos, reportes de pagos, control de stock) debe ser atómico y seguro contra condiciones de carrera (*race conditions*). Queda estrictamente prohibido permitir que dos repartidores tomen el mismo pedido o que un reporte de pago se duplique.
*   **Aseguramiento de Calidad y Cobertura Financiera 100%:** La lógica financiera del ledger 50/50 y las transiciones de la máquina de estados deben tener **cobertura del 100%** en pruebas unitarias automatizadas. Todo endpoint crítico debe superar pruebas de concurrencia y validar los SLAs de carga (1.500 a 8.000 usuarios concurrentes).

## 2. Convenciones de Código
*   **Idioma:** 
    *   Código fuente (variables, funciones, clases, tablas): **Inglés** (`Order`, `PaymentBreakdown`).
    *   Mensajes de commit y documentación interna (SDD): **Español**.
    *   Textos orientados al usuario final (UI): **Español**.
*   **Estilos por Tecnología:**
    *   **Backend (Python):** 
        *   Adherencia estricta a **PEP 8**.
        *   Uso obligatorio de **Type Hints** (tipado estático) en todas las funciones y métodos. Prohibido el código ambiguo.
        *   Uso de formateadores automáticos (ej. `Black` o `Ruff`).
    *   **Frontend (Flutter/Dart):** 
        *   Separación estricta de la lógica y la UI. La interfaz gráfica no debe hacer llamadas directas a la base de datos ni calcular precios.
        *   Uso de `flutter_lints`. Evitar widgets monolíticos extrayendo componentes reutilizables.
    *   **Base de Datos (PostgreSQL):** Nombres de tablas en `snake_case` y en plural (ej. `food_orders`, `users`). Las claves primarias (PK) deben ser UUIDv4, no enteros autoincrementales, para mayor seguridad.

## 3. Flujo de Trabajo y Control de Versiones
Todos los mensajes de commit deben seguir la convención "Conventional Commits" para rastrear los cambios fácilmente:
*   `feat:` Nueva característica (ej. `feat: agregar catálogo de restaurantes`)
*   `fix:` Corrección de errores (ej. `fix: cálculo incorrecto del 50% de pago inicial`)
*   `refactor:` Cambios de código que no añaden características.
*   `docs:` Actualización de archivos `.md` en la carpeta `/docs/sdd`.

## 4. Manejo de Errores Global
*   **Nunca fallar en silencio:** En Flutter, captura todas las excepciones y muestra un mensaje amigable al usuario. En Python, nunca uses un `try/except` vacío (`pass`).
*   **Respuestas de API Estandarizadas:** Todas las respuestas del backend deben seguir este formato JSON predecible, independientemente de si es un éxito o un error:
    ```json
    {
      "success": false,
      "error_code": "INSUFFICIENT_PAYMENT",
      "message": "El pago inicial no cubre el 50% requerido.",
      "data": null
    }
    ```