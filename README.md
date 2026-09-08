# 🛵 mydeliverys_app — Delivery San Juan de los Morros

Plataforma integral de entrega a domicilio adaptada específicamente a las condiciones locales y operativas de **San Juan de los Morros (Estado Guárico, Venezuela)**.

El proyecto está diseñado bajo la metodología **Spec-Driven Development (SDD)**: el desarrollo es guiado y validado a partir de especificaciones formales inmutables antes de escribir código.

---

## 🚀 Características Principales

*   **Integridad Financiera (Regla 50/50):** Modelo de cobro fraccionado seguro para mitigar riesgos inflacionarios y de impago:
    *   **Primer 50%:** Pago inicial (Pago Móvil / transferencia) verificado antes de que el restaurante inicie la preparación (`PREPARING`).
    *   **Segundo 50%:** Cobro contra entrega (efectivo o Pago Móvil validado) antes de completar la orden (`DELIVERED`).
    *   **Regla Matemática del Centavo:** El centavo impar en totales fraccionarios es absorbido siempre por el primer pago.
*   **Resiliencia de Red (Offline-First):** La aplicación cliente maneja fluctuaciones de conectividad local guardando carritos y estados en base de datos local (Hive/Isar) con sincronización fluida.
*   **Seguimiento en Vivo de Bajo Consumo:** Comunicación en tiempo real mediante WebSockets y Redis Pub/Sub para las coordenadas del repartidor, optimizando la batería y la red móvil.
*   **Gestión por Roles (RBAC):**
    *   📱 **Cliente:** Registro sin contraseña vía WhatsApp OTP (TTL 3 min en Redis).
    *   🍳 **Restaurante:** Tablero Kanban táctil con alertas sonoras para cocina y toggle de stock.
    *   🛵 **Repartidor:** App de ruta optimizada con geocercas de proximidad.
    *   💻 **Super Admin:** Consola web para conciliación de pagos, gestión de socios y mapa de operaciones en vivo.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
| :--- | :--- |
| **Frontend / Apps** | **Flutter** (Dart), **Riverpod** (Estado), **GoRouter** (Navegación), **Hive/Isar** (Caché Offline), `google_maps_flutter` |
| **Backend API** | **FastAPI** (Python 3.11+ asíncrono), Pydantic v2, JWT (Access + Refresh Tokens) |
| **Procesamiento Asíncrono** | **Celery** + **Redis** (Cola de tareas para WhatsApp OTP, notificaciones FCM y despachos) |
| **Base de Datos** | **PostgreSQL** con extensión **PostGIS** para cálculo geoespacial de rutas y costos de envío |
| **ORM y Migraciones** | **SQLAlchemy 2.0+** / SQLModel y **Alembic** |
| **Integraciones** | Pago Móvil / Binance Pay, Firebase Cloud Messaging (FCM), WhatsApp Business API / Twilio |

---

## 📁 Estructura del Repositorio

```text
mydeliverys_app/
├── docs/
│   └── sdd/                     # Documentación oficial y viva (SDD)
│       ├── constitution.md      # Principios inquebrantables del proyecto
│       ├── stack.md             # Stack tecnológico aprobado
│       ├── architecture.md      # Topología, modelo relacional, máquina de estados y concurrencia
│       ├── testing_strategy.md  # Pirámide de pruebas, concurrencia y pruebas de carga (1.500 - 8.000 CCU)
│       ├── design_system.md     # Sistema de diseño visual, tokens, componentes y UX por rol
│       └── features/            # Especificaciones funcionales detalladas
│           ├── admin_dashboards.md
│           ├── auth_and_roles.md
│           ├── catalog_and_cart.md
│           ├── checkout_and_5050.md
│           └── live_tracking.md
├── AGENTS.md                    # Directrices y reglas de ingeniería para agentes IA
├── .gitignore                   # Configuración para Python, Flutter, BD y secretos
├── samples/                     # Plantillas y diagramas de referencia del flujo SDD
└── README.md                    # Presentación oficial del proyecto
```

---

## 📜 Especificaciones SDD (Spec-Driven Development)

Toda decisión técnica y funcional está documentada en la carpeta [`docs/sdd/`](./docs/sdd):

1. [📜 Constitución del Proyecto](./docs/sdd/constitution.md): Principios innegociables, manejo monetario con `Decimal`/`Numeric`, seguridad en concurrencia y fidelidad al diseño.
2. [🛠️ Stack Tecnológico](./docs/sdd/stack.md): Justificación y catálogo de librerías aprobadas (incluyendo PgBouncer y herramientas de testing).
3. [🏗️ Arquitectura, Concurrencia y Rate Limiting](./docs/sdd/architecture.md): Topología modular, esquemas PostGIS, máquina de estados, soporte para 1.500 - 8.000 CCU y cuotas de rate limiting por usuario.
4. [🧪 Estrategia de Pruebas y Carga](./docs/sdd/testing_strategy.md): Pirámide de pruebas (Unitarias, Integración, Concurrencia/Race Conditions y Estrés con Locust).
5. [🎨 Sistema de Diseño Visual (Design System)](./docs/sdd/design_system.md): Paleta de colores, tipografía Outfit/Inter con cifras tabulares, componentes y UX adaptada al sol llanero.
6. [🔐 Autenticación y Roles](./docs/sdd/features/auth_and_roles.md): Ciclo de vida de tokens, roles y flujo OTP por WhatsApp.
7. [🍔 Catálogo y Carrito](./docs/sdd/features/catalog_and_cart.md): Jerarquía de productos, modificadores y persistencia offline.
8. [🛒 Checkout y Regla 50/50](./docs/sdd/features/checkout_and_5050.md): Motor financiero del ledger, cálculo de envío por distancia y conciliación.
9. [🛵 Seguimiento en Vivo](./docs/sdd/features/live_tracking.md): WebSockets, Redis Pub/Sub y geocercas.
10. [💻 Paneles de Control](./docs/sdd/features/admin_dashboards.md): Kanban de cocina y consola Super Admin.

---

## 🤝 Convenciones de Contribución
- Todos los commits deben seguir **Conventional Commits**:
  - `feat:` Nuevas características.
  - `fix:` Corrección de errores.
  - `refactor:` Mejoras internas de código sin alteración de funcionalidad.
  - `docs:` Actualizaciones en documentación SDD.
- La documentación en `docs/sdd/` es la **única fuente de la verdad**. El código que no coincida con la especificación es considerado defectuoso.