# AGENTS.md — mydeliverys_app (Delivery San Juan de los Morros)

## 📌 Proyecto
Plataforma integral de delivery adaptada a las condiciones locales de San Juan de los Morros, Estado Guárico, Venezuela.
- **Backend:** FastAPI (Python 3.11+) + PostgreSQL (PostGIS) + Redis + Celery.
- **Frontend / Apps:** Flutter (Dart) multiplataforma (Cliente, Conductor y Restaurante) con Riverpod, GoRouter y persistencia local (Hive/Isar).
- **Metodología:** **Spec-Driven Development (SDD)**. La documentación en `docs/sdd/` es la única fuente de la verdad inmutable.

---

## 🛠️ Comandos Principales

### Backend (`backend/`)
- Iniciar API en desarrollo: `uvicorn app.main:app --reload --port 8000`
- Tareas en segundo plano (Celery): `celery -A app.core.celery worker --loglevel=info`
- Migraciones de Base de Datos:
  - Generar revisión: `alembic revision --autogenerate -m "descripcion"`
  - Aplicar migraciones: `alembic upgrade head`
- Pruebas automatizadas: `pytest -v`
- Formateo y Linter: `ruff check .` / `ruff format .` o `black .`

### Frontend / Mobile (`mobile/` o apps cliente)
- Ejecutar en desarrollo: `flutter run`
- Generación de código (Riverpod/Freezed/Hive): `dart run build_runner build --delete-conflicting-outputs`
- Análisis estático: `flutter analyze`
- Pruebas unitarias y de widgets: `flutter test`

---

## 📐 Estilo y Convenciones de Código
- **Idioma del Código:** **Inglés** estricto para variables, clases, métodos, esquemas Pydantic y tablas de base de datos (`Order`, `PaymentBreakdown`, `food_orders`).
- **Idioma de Interfaz y Documentación:** **Español** para la UI de usuario final, commits convencionales y especificaciones en `docs/sdd/`.
- **Backend (Python):** 
  - Adherencia total a **PEP 8** y tipado estático obligatorio (**Type Hints** en 100% de funciones/métodos).
  - Manejo monetario exclusivo con `Decimal` en Python y `Numeric(10, 2)` en PostgreSQL. **Prohibido el uso de `float` para montos o saldos.**
- **Frontend (Dart/Flutter):**
  - Separación rigurosa de lógica y UI. Ningún widget calcula precios ni realiza llamadas directas a la base de datos.
  - Gestión de estado obligatoria con **Riverpod**. Queda estrictamente prohibido el uso de GetX o Provider antiguo.
  - Enrutamiento estructurado con **GoRouter**.
- **Base de Datos (PostgreSQL):**
  - Nombres de tablas en `snake_case` y en plural (ej. `restaurants`, `order_items`).
  - Claves primarias (PK) siempre en formato `UUIDv4`.
  - Coordenadas geográficas mediante extensiones de `PostGIS` (`GEOMETRY(Point, 4326)`).

---

## 📜 Reglas Innegociables (Constitución)
1. **La SDD manda:** Cualquier divergencia entre el código y los documentos en `docs/sdd/` significa que el código está mal. Modifica primero la especificación antes de cambiar la lógica de negocio.
2. **Resiliencia de Red Offline-First:** La conectividad en San Juan de los Morros puede fluctuar. Las aplicaciones cliente deben manejar caídas de red, persistir el carrito localmente en Hive/Isar y reintentar peticiones fallidas.
3. **Regla Financiera 50/50:**
   - Ningún pedido avanza a `PREPARING` sin validación confirmada del primer 50% (`FIRST_HALF_AMOUNT`).
   - El centavo impar siempre lo absorbe el primer pago: `FIRST_HALF_AMOUNT = ceil(total_amount / 2 * 100) / 100`.
   - NUNCA confiar en precios enviados por el cliente; FastAPI recalcula todo en el servidor (`POST /orders/draft`).
   - El ciclo de entrega no se cierra sin confirmación del segundo 50%.
4. **Formato de Respuesta de API:**
   Todas las respuestas JSON del backend deben tener la estructura:
   ```json
   {
     "success": true,
     "error_code": null,
     "message": "Operación completada con éxito.",
     "data": {}
   }
   ```
5. **No fallar en silencio:** Prohibido el uso de `try/except: pass` en Python o capturas de excepciones vacías en Dart.

---

## ✅ Al Terminar Cualquier Tarea
1. Verificar que el código pasa el linter y type checking (`ruff check .`, `flutter analyze`).
2. Comprobar que las pruebas automatizadas pasan limpiamente.
3. Crear commits siguiendo la convención **Conventional Commits**:
   - `feat: <nueva característica>`
   - `fix: <corrección de error>`
   - `refactor: <refactorización>`
   - `docs: <documentación>`
