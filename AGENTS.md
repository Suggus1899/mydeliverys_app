# AGENTS.md — mydeliverys_app (Delivery San Juan de los Morros)

## 📌 Proyecto
Plataforma integral de delivery adaptada específicamente a las condiciones locales y operativas de San Juan de los Morros, Estado Guárico, Venezuela.
- **Backend:** FastAPI (Python 3.11+) asíncrono + PostgreSQL (PostGIS) + Redis + Celery + PgBouncer.
- **Frontend / Apps:** Flutter (Dart) multiplataforma (Cliente, Conductor y Restaurante) con Riverpod, GoRouter y persistencia local (Hive/Isar).
- **Metodología:** **Spec-Driven Development (SDD)**. La documentación en `docs/sdd/` es la **única fuente de la verdad inmutable**.

---

## 🛠️ Comandos Principales

### Backend (`backend/`)
- Iniciar API en desarrollo: `uvicorn app.main:app --reload --port 8000`
- Tareas en segundo plano (Celery): `celery -A app.core.celery worker --loglevel=info`
- Migraciones de Base de Datos:
  - Generar revisión: `alembic revision --autogenerate -m "descripcion"`
  - Aplicar migraciones: `alembic upgrade head`
- Pruebas automatizadas (Unitarias e Integración): `pytest -v`
- Pruebas de concurrencia y condiciones de carrera: `pytest -v tests/concurrency/`
- Pruebas de carga y estrés (Locust): `locust -f tests/load/locustfile.py --headless -u 1500 -r 50 --run-time 5m`
- Formateo y Linter: `ruff check .` / `ruff format .` o `black .`

### Frontend / Mobile (`mobile/` o apps cliente)
- Ejecutar en desarrollo: `flutter run`
- Generación de código (Riverpod/Freezed/Hive): `dart run build_runner build --delete-conflicting-outputs`
- Análisis estático: `flutter analyze`
- Pruebas unitarias y de widgets: `flutter test`

---

## 📐 Estilo y Convenciones de Código

### Idioma
- **Código Fuente (Variables, clases, métodos, esquemas, tablas):** **Inglés** estricto (`Order`, `PaymentBreakdown`, `food_orders`).
- **Interfaz de Usuario (UI), Mensajes de Error y Textos:** **Español** (`"Tu pedido está en camino"`).
- **Documentación Interna, Specs y Commits:** **Español**.

### Backend (Python / FastAPI)
- Adherencia total a **PEP 8** y tipado estático estricto (**Type Hints** en el 100% de funciones y métodos).
- Manejo monetario exclusivo con `Decimal` en Python y `Numeric(10, 2)` en PostgreSQL. **Prohibido el uso de `float` o `double` para montos o saldos.**
- Protección obligatoria de endpoints con **Rate Limiting** en Redis antes de tocar la base de datos (según `docs/sdd/architecture.md`).
- Manejo de respuestas estándar JSON en todo endpoint.

### Frontend (Dart / Flutter)
- Separación rigurosa de lógica y UI. Ningún widget calcula precios ni realiza llamadas directas a la base de datos.
- Gestión de estado obligatoria con **Riverpod**. Queda terminantemente prohibido el uso de GetX o Provider antiguo.
- Enrutamiento estructurado con **GoRouter** y deep linking.
- **Fidelidad al Sistema de Diseño (`docs/sdd/design_system.md`):**
  - Paleta *"Apetito Cálido y Confiable"*: Primario Naranja Coral/Bermellón (`#FF5A36`), Textos Gris Carbón (`#1E2229`), Fondo lienzo claro (`#F8F9FA`) y tarjetas (`#FFFFFF`).
  - **Uso moderado del primario:** Reservado para la acción principal de la pantalla (botones CTA, precio total y badge activo).
  - Tipografía: Titulares en **`Outfit`** y cuerpo en **`Inter`**.
  - **Cifras Tabulares Obligatorias:** Todo monto monetario debe usar `fontFeatures: [const FontFeature.tabularFigures()]` para evitar bailes visuales en `$7.51` vs `$7.50`.
  - **Light Theme First (V1):** Prioridad en un tema claro limpio para el lucimiento de las fotografías de comida.

### Base de Datos (PostgreSQL + PostGIS)
- Nombres de tablas en `snake_case` y en plural (`restaurants`, `order_items`, `payments`).
- Claves primarias (PK) siempre en formato **`UUIDv4`**.
- Coordenadas geográficas mediante extensiones de **PostGIS** (`GEOMETRY(Point, 4326)`).

---

## 📜 Reglas Innegociables (Constitución)
1. **La SDD manda:** Cualquier divergencia entre el código y los documentos en `docs/sdd/` significa que el código está mal. Modifica primero la especificación antes de cambiar la lógica de negocio.
2. **Plantilla de Specs Oficial:** Al crear una nueva funcionalidad, copia y completa la plantilla en [`samples/spec.md`](./samples/spec.md) en notación formal EARS.
3. **Resiliencia de Red Offline-First:** La conectividad en San Juan de los Morros puede fluctuar. Las aplicaciones cliente deben manejar caídas de red, persistir el carrito localmente en Hive/Isar y reintentar peticiones fallidas.
4. **Regla Financiera 50/50:**
   - Ningún pedido avanza a `PREPARING` sin validación confirmada del primer 50% (`FIRST_HALF_AMOUNT`).
   - El centavo impar siempre lo absorbe el primer pago: `FIRST_HALF_AMOUNT = ceil(total_amount / 2 * 100) / 100`.
   - NUNCA confiar en precios enviados por el cliente; FastAPI recalcula todo en el servidor (`POST /orders/draft`).
   - El ciclo de entrega no se cierra sin confirmación del segundo 50%.
5. **Formato de Respuesta de API:**
   Todas las respuestas JSON del backend deben tener la estructura:
   ```json
   {
     "success": true,
     "error_code": null,
     "message": "Operación completada con éxito.",
     "data": {}
   }
   ```
6. **No fallar en silencio:** Prohibido el uso de `try/except: pass` en Python o capturas de excepciones vacías en Dart.
7. **Seguridad en Concurrencia (Cero Doble Asignación):** Todo endpoint transaccional (despacho de pedidos, deducción de stock y pagos) debe ser atómico y mitigar *race conditions* (`UPDATE ... WHERE driver_id IS NULL`, `X-Idempotency-Key` en Redis).
8. **Cobertura de Pruebas 100% en Ledger:** La lógica matemática del cálculo 50/50 y las transiciones de la máquina de estados deben contar con un 100% de cobertura en pruebas unitarias antes de fusionar código.
9. **Límites Tecnológicos:** Prohibido añadir nuevas librerías o dependencias no aprobadas en `docs/sdd/stack.md` sin autorización explícita.
10. **Control Exclusivo de Commits por el Humano:** El desarrollador humano es el único autorizado para ejecutar `git commit` y gestionar el historial de Git. **Los agentes de IA tienen estrictamente prohibido ejecutar comandos de commit.** El agente debe únicamente sugerir el mensaje de commit formateado al finalizar cada tarea.

---

## ✅ Al Terminar Cualquier Tarea
1. Verificar que el código pasa el linter y type checking (`ruff check .`, `flutter analyze`).
2. Comprobar que las pruebas automatizadas pasan limpiamente (`pytest -v`, `flutter test`).
3. Comprobar que las pruebas de concurrencia pasan si se modificaron módulos transaccionales (`pytest -v tests/concurrency/`).
4. **Sugerir el mensaje de commit al desarrollador** siguiendo la convención **Conventional Commits** (sin ejecutar el commit):
   - `feat: <nueva característica>`
   - `fix: <corrección de error>`
   - `refactor: <refactorización>`
   - `docs: <documentación>`
