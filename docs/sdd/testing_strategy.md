# 🧪 Estrategia Integral de Pruebas y Carga (Testing Strategy)

Este documento define la pirámide de pruebas automatizadas, las pruebas de estrés para soportar de **1.500 a 8.000 usuarios concurrentes** y las verificaciones obligatorias de concurrencia y condiciones de carrera para **mydeliverys_app**.

---

## 1. Pirámide de Pruebas

El proyecto implementa una estrategia de calidad en cuatro niveles jerárquicos:

```text
                ▲
               / \
              /   \     Nivel 4: Pruebas de Carga y Estrés (Locust: 1.500 - 8.000 CCU)
             /-----\
            /       \    Nivel 3: Pruebas de Concurrencia (Colisiones y Race Conditions)
           /---------\
          /           \   Nivel 2: Pruebas de Integración (PostGIS + Redis + Testcontainers)
         /-------------\
        /               \  Nivel 1: Pruebas Unitarias (100% Ledger 50/50, Máquina Estados, Hive)
       /─────────────────\
```

---

## 2. Nivel 1: Pruebas Unitarias (Unit Tests)

### 2.1. Backend (Python / `pytest`)
*   **Regla Financiera 50/50 (Cobertura Obligatoria 100%):**
    *   Verificación de la regla matemática del centavo impar:
        *   Monto impar: `$15.01` $\rightarrow$ Pago 1 = `$7.51`, Pago 2 = `$7.50`.
        *   Monto par: `$20.00` $\rightarrow$ Pago 1 = `$10.00`, Pago 2 = `$10.00`.
        *   Monto mínimo: `$0.01` $\rightarrow$ Pago 1 = `$0.01`, Pago 2 = `$0.00`.
    *   Garantía de precisión: todos los cálculos deben usar tipos `Decimal`. Queda prohibido el uso de flotantes (`float`).
    *   Invariante contable: `assert first_half + second_half == total_amount`.
*   **Máquina de Estados Global (`OrderStatus`):**
    *   Verificar que cada transición válida altere el estado correctamente.
    *   Verificar que cualquier transición inválida (ej. intentar saltar de `DRAFT` directo a `PREPARING` o de `ON_THE_WAY` a `DELIVERED` sin registrar el segundo 50%) lance un error controlado `InvalidStateTransitionError` con código `HTTP 400/422`.
*   **Validador de Modificadores:**
    *   Comprobar que selecciones inferiores a `min_selectable` o superiores a `max_selectable` sean rechazadas con `422 Unprocessable Entity`.

### 2.2. Frontend (Flutter / `flutter_test` + `mocktail`)
*   **Caché Offline del Carrito (Hive / Isar):**
    *   Persistencia del carrito: almacenar ítems, cerrar el contexto y verificar que la recarga en frío reconstruya exactamente los mismos productos y modificadores.
    *   Modal de Mono-Restaurante: intentar añadir un producto de otro comercio debe disparar el evento de advertencia sin corromper el estado en memoria.

---

## 3. Nivel 2: Pruebas de Integración (Integration Tests)

Las pruebas de integración no utilizan mocks para la persistencia; ejecutan servicios reales usando **`testcontainers-python`**:
*   **PostgreSQL + PostGIS:** Imagen `postgis/postgis:15-3.3`.
*   **Redis:** Imagen `redis:7-alpine`.

### 3.1. Escenarios Clave de Integración
1.  **Ciclo de Vida Completo del Pedido:**
    *   `POST /orders/draft` $\rightarrow$ cotización y congelamiento de precios.
    *   `POST /payments/{order_id}/report` $\rightarrow$ estado `PAYMENT_1_VERIFYING`.
    *   `POST /admin/payments/{payment_id}/verify` $\rightarrow$ estado `PREPARING`.
    *   `POST /driver/orders/{order_id}/arrived` $\rightarrow$ estado `ARRIVED_AT_CUSTOMER`.
    *   `POST /driver/orders/{order_id}/collect-cash` $\rightarrow$ estado `DELIVERED`.
2.  **Cálculos Geoespaciales PostGIS:**
    *   Calcular distancias reales en San Juan de los Morros (ej. desde un restaurante en Av. Bolívar hacia una dirección en Urb. Los Rosales o La Morera) mediante `ST_DistanceSphere` y comprobar que la tarifa de envío generada corresponda a la tabla oficial de distancias.

---

## 4. Nivel 3: Pruebas de Concurrencia y Condiciones de Carrera

Se ejecutan mediante scripts asíncronos (`pytest-asyncio` con `asyncio.gather`) para bombardear el servidor con peticiones simultáneas sobre el mismo recurso:

### 4.1. Test de Colisión: Doble Asignación de Pedido
*   **Escenario:** 50 conductores intentan aceptar la misma orden en estado `READY_FOR_PICKUP` exactamente en el mismo instante.
*   **Resultado Esperado:**
    *   Exactamente **1 petición** obtiene respuesta `200 OK` con `driver_id` asignado.
    *   Las **49 peticiones restantes** reciben `409 Conflict` con código `ORDER_ALREADY_ASSIGNED`.
    *   La base de datos mantiene un único conductor asignado.

### 4.2. Test de Idempotencia: Reporte Duplicado de Pago
*   **Escenario:** 10 peticiones idénticas enviadas con el mismo `X-Idempotency-Key` (simulando toques repetidos o reintentos de red del cliente).
*   **Resultado Esperado:**
    *   Solo se inserta **un único registro** en la tabla `payments`.
    *   Ningún balance contable se duplica.

### 4.3. Test de Sobreventa de Stock (Race Condition en Inventario)
*   **Escenario:** 20 clientes intentan comprar simultáneamente un plato con stock restante de 3 unidades.
*   **Resultado Esperado:**
    *   Exactamente 3 órdenes avanzan exitosamente.
    *   Las 17 peticiones restantes reciben error de stock agotado.
    *   El stock final en la base de datos es exactamente 0 (nunca negativo).

---

## 5. Nivel 4: Pruebas de Carga y Estrés (Locust: 1.500 - 8.000 Usuarios)

Para certificar que el sistema soporta el tráfico de San Juan de los Morros en picos de alta demanda, se utiliza **Locust** (`tests/load/locustfile.py`).

### 5.1. Perfiles de Carga y Rampa de Usuarios

```text
Usuarios Concurrentes (CCU)
  8.000 ┤                                  ╭───────────╮ (Pico Máximo de Estrés)
        │                                 ╭╯           ╰╮
  1.500 ┤        ╭────────────────────────╯             ╰───────── (Carga Sostenida)
        │       ╭╯
    500 ┤  ╭────╯ (Calentamiento)
      0 ┼──┴──────┴───────────────────────┴─────────────┴─────────► Tiempo (minutos)
        0  2      5                       25            35       45
```

1.  **Fase 1: Calentamiento (0 a 500 CCU en 2 minutos):**
    *   Verificación de que las conexiones de PgBouncer y la caché en Redis se inicialicen correctamente sin fallas en frío.
2.  **Fase 2: Carga Sostenida de Horas Pico (1.500 CCU durante 20 minutos):**
    *   Simula el flujo regular de usuarios activos en la hora del almuerzo o cena.
3.  **Fase 3: Pico de Estrés Extremo (Rampa rápida a 8.000 CCU durante 10 minutos):**
    *   Prueba de resistencia extrema (ej. promociones masivas o eventos festivos en la ciudad).

### 5.2. Distribución de Comportamiento de Usuarios en Locust
Cada usuario virtual ejecuta tareas ponderadas:
*   **70% Lectura de Catálogos (Caché Redis):**
    *   `GET /restaurants` (Lista de comercios abiertos).
    *   `GET /restaurants/{id}/menu` (Menú completo con modificadores).
*   **15% Generación de Cotización (`POST /orders/draft`):**
    *   Cálculo de distancia PostGIS y tarifas de envío.
*   **10% Consulta de Estado y Reporte de Pago:**
    *   `POST /payments/{order_id}/report` con cabecera `X-Idempotency-Key`.
    *   `GET /orders/{order_id}/status`.
*   **5% Transmisión de Coordenadas de Repartidores (WebSockets):**
    *   Envío de coordenadas simuladas cada 5 segundos al canal Redis Pub/Sub.

### 5.3. SLAs y Criterios de Aceptación Innegociables
| Métrica | Meta con 1.500 CCU | Meta con 8.000 CCU (Estrés) |
| :--- | :--- | :--- |
| **Latencia $p_{95}$ (Lecturas Catálogo)** | $< 120\text{ ms}$ | $< 250\text{ ms}$ |
| **Latencia $p_{95}$ (Checkout / Draft)** | $< 200\text{ ms}$ | $< 400\text{ ms}$ |
| **Latencia de Entrega WebSocket** | $< 30\text{ ms}$ | $< 60\text{ ms}$ |
| **Tasa de Errores HTTP (5xx)** | **$0.00\%$** | **$< 0.10\%$** |
| **Utilización de CPU en PostgreSQL** | $< 45\%$ | $< 75\%$ (gracias a PgBouncer y Redis) |
| **Integridad del Ledger** | $100\%$ sin descuadres | $100\%$ sin descuadres |

---

## 6. Comandos de Ejecución

### Ejecución de Pruebas Unitarias y de Integración
```bash
# Todas las pruebas unitarias y de integración
pytest -v

# Pruebas financieras estrictas con reporte de cobertura
pytest -v tests/unit/test_financial_ledger.py --cov=app/services/financial --cov-report=term-missing

# Pruebas exclusivas de concurrencia y colisiones
pytest -v tests/concurrency/
```

### Ejecución de Pruebas de Carga con Locust
```bash
# Modo interactivo con interfaz web en http://localhost:8089
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Modo Headless automatizado para CI/CD (1.500 usuarios, rampa de 50/seg por 10 min)
locust -f tests/load/locustfile.py --headless -u 1500 -r 50 --run-time 10m --host=http://localhost:8000 --html=reports/load_test_1500.html

# Modo Estrés Extremo (8.000 usuarios, rampa de 100/seg por 15 min)
locust -f tests/load/locustfile.py --headless -u 8000 -r 100 --run-time 15m --host=http://localhost:8000 --html=reports/stress_test_8000.html
```
