# MyDeliveryS App - Delivery San Juan de los Morros

Plataforma integral de delivery adaptada específicamente a las condiciones locales y operativas de San Juan de los Morros, Estado Guárico, Venezuela.

## 🏗️ Arquitectura

- **Backend:** FastAPI (Python 3.12) asíncrono + PostgreSQL (PostGIS) + Redis + Celery + PgBouncer
- **Frontend:** Flutter (Dart) multiplataforma (Cliente, Conductor, Restaurante, Super Admin)
- **Metodología:** Spec-Driven Development (SDD) - La documentación en `docs/sdd/` es la única fuente de la verdad

## 🚀 Inicio Rápido

### Prerrequisitos

- Docker y Docker Compose
- Python 3.12+ (para desarrollo local)
- Flutter 3.44.8 (versión usada por CI)

### Con Docker Compose (Recomendado)

```bash
# Clonar repositorio
git clone <repo-url>
cd mydeliverys_app

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# Levantar toda la infraestructura
docker-compose up -d

# Verificar que todo funciona
curl http://localhost:8000/health
```

### Desarrollo Local (Backend)

```bash
cd backend

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\Activate.ps1  # Windows

# Instalar dependencias
pip install poetry
poetry install --with=dev

# Configurar base de datos (requiere PostgreSQL + PostGIS local)
cp .env.example .env
# Editar .env

# Ejecutar migraciones
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

## 📁 Estructura del Proyecto

```
mydeliverys_app/
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── api/v1/         # Endpoints REST
│   │   ├── core/           # Config, DB, Security, Middleware
│   │   ├── domain/         # Lógica de negocio pura (financial, states, errors)
│   │   ├── infrastructure/ # Redis, external APIs
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Servicios de aplicación
│   │   ├── tasks/          # Celery tasks
│   │   └── main.py         # Entry point
│   ├── alembic/            # Migraciones DB
│   ├── tests/              # Tests (unit, integration, concurrency, load)
│   ├── Dockerfile
│   └── pyproject.toml
├── mobile/                  # Apps Android de cliente y conductor
├── admin_web/               # Consolas web de restaurante y Super Admin
├── docs/
│   └── sdd/                # Spec-Driven Development docs
│       ├── architecture.md
│       ├── constitution.md
│       ├── design_system.md
│       ├── stack.md
│       ├── testing_strategy.md
│       └── features/       # Especificaciones por feature
│           └── normalized/ # Especificaciones EARS normalizadas
├── samples/                 # Plantillas SDD
├── docker-compose.yml       # Infraestructura completa
├── .github/workflows/       # CI/CD
└── README.md
```

## 🧪 Testing

```bash
# Backend tests
cd backend
poetry run pytest -v                    # Todos los tests
poetry run pytest -v tests/unit         # Unit tests (100% coverage required)
poetry run pytest -v tests/integration  # Integration tests (requiere DB real)
poetry run pytest -v tests/concurrency  # Concurrency tests
poetry run pytest -v tests/load         # Load tests (Locust)

# Linting & Type checking
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
```

## 📋 Especificaciones (SDD)

Todas las funcionalidades están documentadas en notación EARS en `docs/sdd/features/normalized/`:

1. `01_auth_and_sessions.md` - Autenticación, sesiones, 2FA, roles
2. `02_catalog_inventory_cart.md` - Catálogo, inventario, reservas, carrito
3. `03_checkout_payments_ledger.md` - Checkout, pagos 50/50, ledger financiero
4. `04_live_tracking_resilience.md` - Tracking GPS, geo-cercas, resiliencia
5. `05_admin_dashboards.md` - Paneles restaurante y super admin
6. `06_client_app.md` - App cliente (offline-first)
7. `07_driver_app.md` - App conductor (modo solar)
8. `08_restaurant_app.md` - App restaurante (tablet/kiosco)
9. `09_super_admin_app.md` - Consola Super Admin
10. `10_tariffs_exchange_rate.md` - Tarifas y tasa de cambio
11. `11_dispatch_incidents.md` - Despacho e incidencias
12. `12_settlements_operations.md` - Liquidaciones y operación

## 🔧 Variables de Entorno Principales

Ver `.env.example` para lista completa.

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL via PgBouncer | `postgresql+asyncpg://...` |
| `REDIS_CONTROL_URL` | Redis de controles y colas, sin eviction | `redis://localhost:6379/0` |
| `REDIS_CACHE_URL` | Redis de cache reconstruible | `redis://localhost:6380/0` |
| `SECRET_KEY` | JWT signing key (min 32 chars) | **Requerido** |
| `JWT_PRIVATE_KEY_PATH` | Path to RS256 private key | `/app/keys/private.pem` |
| `JWT_PUBLIC_KEY_PATH` | Path to RS256 public key | `/app/keys/public.pem` |
| `DOLARAPI_URL` | Endpoint oficial de DolarAPI Venezuela | `https://ve.dolarapi.com/v1/dolares/oficial` |
| `WHATSAPP_API_URL` | Meta Cloud API URL | **Requerido para producción** |
| `FCM_CREDENTIALS_PATH` | Firebase credentials JSON | **Requerido para producción** |

## 🐳 Servicios Docker

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| `postgres` | 5432 | PostgreSQL 16 + PostGIS 3.4 |
| `pgbouncer` | 6432 | Connection pooler (transaction mode) |
| `redis-control` | 6379 | OTP, cuotas, idempotencia, colas y Pub/Sub sin eviction |
| `redis-cache` | 6380 | Cache reconstruible con política LRU |
| `api` | 8000 | FastAPI backend |
| `celery-worker` | - | Background tasks |
| `celery-beat` | - | Periodic tasks (exchange rate fetch) |
| `flower` | 5555 | Celery monitoring |

## 📊 Monitoreo

- **Flower (Celery):** http://localhost:5555
- **API Docs (Swagger):** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Readiness:** http://localhost:8000/ready

## 🔒 Seguridad

- JWT RS256 con rotación de claves
- Argon2id para hash de contraseñas
- Rate limiting por IP/usuario en Redis (sliding window)
- Idempotencia en doble capa (Redis + PostgreSQL)
- Transacciones atómicas con `WHERE driver_id IS NULL`
- Auditoría inmutable en `audit_logs`

## 📦 Despliegue

```bash
# Build imágenes de producción
docker compose build

# Deploy
docker compose up -d
```

## 📝 Convenciones de Commit

```
feat: nueva característica
fix: corrección de error
refactor: refactorización
docs: documentación
test: tests
chore: mantenimiento
```

## 📄 Licencia

MIT License - ver LICENSE para detalles.
