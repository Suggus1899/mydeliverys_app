# 🔐 Especificación de Autenticación y Roles (Delivery)

Este documento define las reglas de acceso, el registro basado en WhatsApp para clientes, la provisión de cuentas para socios y el ciclo de vida criptográfico de las sesiones.

## 1. Matriz de Roles (RBAC - Role Based Access Control)

El sistema soporta 4 roles mutuamente excluyentes. Un usuario tiene un único rol definido en la tabla `users`.

| Rol | Permisos Principales | Método de Ingreso |
| :--- | :--- | :--- |
| `CUSTOMER` | Explorar, pedir, rastrear, pagar. | Registro en App + OTP por WhatsApp. |
| `DRIVER` | Ver pedidos asignados, actualizar estados GPS. | Creado por Admin. Login con Teléfono + Contraseña. |
| `RESTAURANT_ADMIN` | Aceptar/Rechazar pedidos, gestionar menú. | Creado por Admin. Login con Teléfono + Contraseña. |
| `SUPER_ADMIN` | Crear socios, ver finanzas globales, soporte. | Consola Web. Email + Contraseña + 2FA. |

---

## 2. Flujo de Autenticación: Clientes (WhatsApp OTP)

Para evitar cuentas falsas (bots) y asegurar que el conductor pueda contactar al cliente, el número de teléfono es la identidad principal. No se usan contraseñas para clientes.

### 2.1. Reglas del Flujo OTP (One Time Password)
1.  **Generación:** El backend (FastAPI) genera un código numérico de 6 dígitos.
2.  **Almacenamiento Temporal:** El código se guarda en **Redis** con un *Time-To-Live* (TTL) estricto de 3 minutos. Nunca se guarda en PostgreSQL.
3.  **Transmisión:** Un `Celery Worker` consume la tarea y envía el mensaje vía API de WhatsApp (ej. Meta Graph API o Twilio).
4.  **Bloqueo de Fuerza Bruta:** Redis debe bloquear temporalmente el número telefónico tras 3 intentos fallidos de validación.

### Diagrama de Secuencia (Registro/Login Cliente)
```mermaid
sequenceDiagram
    participant App as Flutter App
    participant API as FastAPI
    participant Redis as Redis Cache
    participant WS as WhatsApp API

    App->>API: POST /auth/request-otp {phone: "0414..."}
    API->>Redis: SETEX otp:0414... 180 "482910"
    API->>WS: Tarea Celery: Enviar "482910"
    API-->>App: 200 OK (OTP Enviado)
    
    App->>API: POST /auth/verify-otp {phone, otp}
    API->>Redis: GET otp:0414...
    alt OTP Correcto
        API->>DB: Upsert User (Si no existe, lo crea)
        API-->>App: 200 OK + {AccessToken, RefreshToken}
    else OTP Incorrecto/Expirado
        API-->>App: 401 Unauthorized
    end