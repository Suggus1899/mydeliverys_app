# 🛠️ Stack Tecnológico (Delivery San Juan de los Morros)

Este documento define la infraestructura tecnológica aprobada. **Bajo ninguna circunstancia se deben introducir nuevas tecnologías, frameworks o librerías de terceros (especialmente gestores de estado o bases de datos) sin modificar primero este documento.**

## 1. Frontend (Aplicaciones Móvil y PC)
*   **Framework Principal:** Flutter.
*   **Lenguaje:** Dart.
*   **Gestor de Estado (State Management):** **Riverpod** (paquete `flutter_riverpod`).
    *   *Justificación:* Seguro en tiempo de compilación y excelente para el manejo de dependencias asíncronas (como verificar si el usuario tiene internet). Queda estrictamente prohibido usar GetX, Provider (antiguo) o setState para lógica de negocio global.
*   **Enrutamiento:** **GoRouter**.
    *   *Regla:* Manejo estricto de URLs y Deep Linking para permitir notificaciones push que abran el pedido directamente.
*   **Almacenamiento Local (Offline caching):** **Hive** o **Isar**.
    *   *Regla:* El carrito de compras y los tokens de sesión deben persistirse localmente para manejar las desconexiones temporales.
*   **Geolocalización y Mapas:** `google_maps_flutter` y `geolocator`.

## 2. Backend (API y Lógica de Negocio)
*   **Framework Principal:** **FastAPI**.
    *   *Justificación:* Altísimo rendimiento, tipado asíncrono y autogeneración de documentación (OpenAPI/Swagger) obligatoria para alinear al equipo frontend.
*   **Lenguaje:** Python 3.11+.
*   **Gestor de Paquetes y Entorno:** **Poetry** (preferible) o `pip` con `requirements.txt` estricto.
*   **Autenticación:** JWT (JSON Web Tokens) a través de `FastAPI-Users` o implementación propia usando `PyJWT`.
    *   *Regla:* Los tokens deben tener un tiempo de expiración corto (access token) apoyado por un "refresh token".
*   **Tareas en Segundo Plano:** `Celery` + `Redis` (o `BackgroundTasks` de FastAPI si la escala inicial es pequeña).
    *   *Uso:* Enviar correos/SMS de confirmación o notificar a los restaurantes sin bloquear la respuesta al usuario.

## 3. Base de Datos (Persistencia e Infraestructura de Conexión)
*   **Motor Principal:** **PostgreSQL** con extensión espacial **PostGIS** (cálculo de distancias y costos de envío).
*   **Gestor de Pool de Conexiones:** **PgBouncer** (Modo Transaction Pooling) para sostener picos de hasta 8.000 clientes concurrentes sin agotar la memoria de PostgreSQL.
*   **Driver Asíncrono:** `asyncpg`.
*   **ORM (Mapeo Objeto-Relacional):** **SQLAlchemy** (v2.0+) o **SQLModel**.
    *   *Regla:* Prohibido escribir queries SQL en crudo (raw SQL) para operaciones CRUD estándar. Se debe usar la API del ORM para evitar inyección SQL.
*   **Migraciones:** **Alembic**.
    *   *Regla:* Cualquier cambio en la estructura de la base de datos (nuevas tablas, columnas) DEBE generarse a través de un script de Alembic. No se permite modificar tablas directamente en la BD de producción.

## 4. Integraciones de Terceros (APIs)
*   **Pasarela de Pagos:** Pago Móvil (bancos locales venezolanos) y Binance Pay.
    *   *Regla de Seguridad:* El backend NUNCA debe almacenar números de tarjeta de crédito (PCI DSS).
*   **Notificaciones Push:** Firebase Cloud Messaging (FCM).
*   **Mensajería y OTP:** WhatsApp Business API (Meta Cloud API o Twilio) para verificación de clientes.

## 5. Herramientas de Pruebas y Aseguramiento de Calidad (Testing & QA)
*   **Backend (Python):**
    *   **Framework Principal de Pruebas:** `pytest` con `pytest-asyncio` para pruebas asíncronas de FastAPI.
    *   **Cliente de Pruebas HTTP:** `httpx.AsyncClient`.
    *   **Servicios Reales en Contenedores:** `testcontainers-python` para instanciar PostgreSQL + PostGIS y Redis durante pruebas de integración.
    *   **Generador de Datos:** `factory-boy` o `faker`.
    *   **Pruebas de Carga y Estrés:** **Locust** (simulación de 1.500 a 8.000 usuarios concurrentes).
*   **Frontend (Flutter/Dart):**
    *   **Pruebas Unitarias y de Widgets:** `flutter_test`.
    *   **Mocking:** `mocktail` para aislar proveedores de Riverpod y servicios de red.
    *   **Pruebas de Integración E2E:** `integration_test` para validar flujos completos de usuario en dispositivos reales o emuladores.