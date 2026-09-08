# 🔐 Especificación Normalizada: Autenticación, Sesiones y Roles (EARS)

> **Versión normalizada** — Corregida según Plan Maestro V1. Completa 2FA, recuperación, relación operador-restaurante y unifica en notación EARS.

---

## 1. Contexto y Objetivo
*   **Problema:** El SDD original define roles y OTP básico pero omite: gestión de sesiones (access/refresh), revocación, 2FA obligatorio para SUPER_ADMIN, códigos de recuperación, provisión de socios (operadores de restaurante con relación 1:N), y bloqueo por fuerza bruta diferenciado por teléfono vs IP.
*   **Valor:** Seguridad robusta, trazabilidad de acciones administrativas, operación continua sin login repetido, y cumplimiento de la regla "no fallar en silencio".
*   **Módulos:** Backend FastAPI (`/api/v1/auth/*`), App Cliente (Flutter), App Driver (Flutter), Panel Restaurante (Flutter Web), Consola Super Admin (Flutter Web).

---

## 2. Actores (RBAC)
| Rol | Permisos | Ingreso |
|-----|----------|---------|
| `CUSTOMER` | Explorar, pedir, rastrear, pagar | Registro App + OTP WhatsApp |
| `DRIVER` | Ver pedidos asignados, actualizar GPS, cobrar | Creado por Admin. Teléfono + Contraseña |
| `RESTAURANT_ADMIN` | Aceptar/rechazar pedidos, gestionar menú/stock | Creado por Admin. Teléfono + Contraseña. **Asociado a 1 restaurante** (relación N:1 en `restaurant_staff`) |
| `SUPER_ADMIN` | Crear socios, finanzas globales, soporte, reasignación | Consola Web. Email + Contraseña + **TOTP 2FA obligatorio** |

---

## 3. Requisitos Funcionales (EARS)

### 3.1. Invariantes del Sistema (Ubícuos)
*   **RF-AUTH-01:** EL SISTEMA normalizará todo número de teléfono a formato E.164 (`+58414xxxxxxx`) antes de persistir o consultar.
*   **RF-AUTH-02:** EL SISTEMA exigirá `full_name` al completar el primer registro de cualquier rol.
*   **RF-AUTH-03:** EL SISTEMA almacenará contraseñas **solo** para roles `DRIVER`, `RESTAURANT_ADMIN`, `SUPER_ADMIN` usando **Argon2id** (nunca texto plano ni hash débil).
*   **RF-AUTH-04:** EL SISTEMA mantendrá la tabla `user_sessions` con: `id` (UUID), `user_id` (FK), `refresh_token_hash`, `user_agent`, `ip_address`, `created_at`, `expires_at`, `revoked_at` (nullable), `revoked_reason` (enum: `LOGOUT`, `PASSWORD_CHANGE`, `ADMIN_REVOKE`, `SECURITY_EVENT`).
*   **RF-AUTH-05:** EL SISTEMA invalidará **todas** las sesiones del usuario al: cerrar sesión explícita, cambiar credenciales, bloquear cuenta, o detectar evento de seguridad.

### 3.2. Dirigido por Eventos (CUANDO)

#### OTP WhatsApp (Clientes)
*   **RF-AUTH-06:** CUANDO `POST /auth/request-otp {phone}` reciba un teléfono válido, EL SISTEMA generará un código **numérico de 6 dígitos**, lo guardará en Redis `otp:{phone_norm}` con **TTL 180 segundos**, y encolará envío vía Celery a Meta Cloud API.
*   **RF-AUTH-07:** CUANDO `POST /auth/verify-otp {phone, otp}` valide código correcto, EL SISTEMA hará `upsert` en `users` (crea si no existe con `role=CUSTOMER`, `is_active=true`), emitirá **Access Token (15 min)** y **Refresh Token rotativo (30 días)**, y registrará sesión en `user_sessions`.
*   **RF-AUTH-08:** CUANDO el OTP expire o sea incorrecto, EL SISTEMA incrementará contador `otp_attempts:{phone_norm}` en Redis (TTL 10 min). **Al alcanzar 3 fallos**, bloqueará el teléfono 10 minutos (`otp_blocked:{phone_norm}`).
*   **RF-AUTH-09:** CUANDO se detecten >5 peticiones `request-otp` desde la misma IP en 3 minutos, EL SISTEMA bloqueará la IP 10 minutos (`otp_ip_blocked:{ip}`), **independiente** del bloqueo por teléfono.

#### Login con Contraseña (Driver, Restaurant Admin, Super Admin)
*   **RF-AUTH-10:** CUANDO `POST /auth/login {phone, password}` valide credenciales, EL SISTEMA verificará `is_active=true`, y para `SUPER_ADMIN` **exigirá** `POST /auth/2fa/verify {totp_code}` antes de emitir tokens.
*   **RF-AUTH-11:** CUANDO `SUPER_ADMIN` registre 2FA por primera vez, EL SISTEMA generará secreto TOTP (RFC 6238), mostrará QR, y **solo activará** tras confirmar un código válido. Generará **8 códigos de recuperación** de un solo uso (hash Argon2id).
*   **RF-AUTH-12:** CUANDO `SUPER_ADMIN` use código de recuperación, EL SISTEMA lo invalidará y emitirá nuevos tokens; **no** regenerará la lista completa.

#### Provisión de Socios (Operadores de Restaurante)
*   **RF-AUTH-13:** CUANDO `SUPER_ADMIN` cree operador vía `POST /admin/restaurant-staff {restaurant_id, phone, full_name, temp_password}`, EL SISTEMA creará usuario `RESTAURANT_ADMIN`, asociará en `restaurant_staff (user_id, restaurant_id, is_active)`, y enviará credenciales temporales por WhatsApp.
*   **RF-AUTH-14:** CUANDO operador inicie sesión por primera vez, EL SISTEMA **forzará** cambio de contraseña (`POST /auth/change-password {old, new}`) antes de permitir cualquier otra acción.

### 3.3. Dirigido por Estados (MIENTRAS)
*   **RF-AUTH-15:** MIENTRAS exista `refresh_token` válido en `user_sessions` (no revocado, `expires_at > now`), EL SISTEMA permitirá `POST /auth/refresh` rotando el token (invalidando el anterior, emitiendo nuevo par access/refresh).
*   **RF-AUTH-16:** MIENTRAS sesión web (`SUPER_ADMIN`, `RESTAURANT_ADMIN`), EL SISTEMA almacenará `refresh_token` en cookie **HttpOnly, Secure, SameSite=Lax** con **CSRF token** (double-submit cookie pattern). **No** persistirá secretos en Hive del navegador.
*   **RF-AUTH-17:** MIENTRAS sesión Android (`CUSTOMER`, `DRIVER`), EL SISTEMA almacenará tokens en **Android Keystore / EncryptedSharedPreferences** (nunca en Hive plano).

### 3.4. Manejo de Errores y Comportamiento No Deseado (SI ... ENTONCES)
*   **RF-AUTH-18:** SI `refresh_token` revocado o expirado, ENTONCES EL SISTEMA responderá `401 UNAUTHENTICATED` con `error_code: "SESSION_EXPIRED"` y **borrará** cookie/almacenamiento local.
*   **RF-AUTH-19:** SI `SUPER_ADMIN` supere 5 intentos fallidos de 2FA en 15 min, ENTONCES EL SISTEMA bloqueará la cuenta 30 min y alertará a otro `SUPER_ADMIN` vía `audit_logs`.
*   **RF-AUTH-20:** SI `RESTAURANT_ADMIN` intente acceder a recurso de otro restaurante (`restaurant_id` distinto al de su `restaurant_staff`), ENTONCES EL SISTEMA responderá `403 FORBIDDEN` con `error_code: "RESOURCE_OWNERSHIP_MISMATCH"`.
*   **RF-AUTH-21:** SI cliente intente `POST /orders/draft` sin `address_id` válido propio, ENTONCES `403 FORBIDDEN` con `error_code: "ADDRESS_NOT_OWNED"`.

### 3.5. Opcional / Configuración (DONDE)
*   **RF-AUTH-22:** DONDE `SUPER_ADMIN` configure `auth.session_max_hours_web` (default 8h), EL SISTEMA forzará re-login en paneles web tras ese tiempo aunque refresh token sea válido.

---

## 4. Requisitos No Funcionales y SLAs
*   **Latencia p95** endpoints auth: `< 150 ms` (lectura Redis) / `< 300 ms` (escritura BD + envío OTP async).
*   **Rate Limiting** (ver Architecture §5.2): `request-otp` 3/10min, `verify-otp` 5/3min, `login` 10/5min por IP.
*   **Seguridad:** Tokens JWT firmados RS256 (rotación claves cada 90 días). `X-Idempotency-Key` obligatorio en `verify-otp`, `login`, `change-password`.

---

## 5. Casos Límite y Concurrencia
*   **Sesiones concurrentes:** Múltiples dispositivos permitidos por defecto. `SUPER_ADMIN` puede forzar cierre de todas menos la actual.
*   **Race condition login + revocación:** `refresh` verifica `revoked_at IS NULL` en transacción `SELECT ... FOR UPDATE` sobre `user_sessions`.
*   **OTP reutilizado:** Redis `GETDEL` consume el código atómicamente (una sola vez).

---

## 6. Fuera de Alcance (Out of Scope)
*   Login social (Google, Apple, Facebook).
*   Autenticación biométrica nativa (delegada al OS del dispositivo).
*   SSO corporativo (SAML/OIDC).

---

## 7. Criterios de Finalización (DoD)
*   [ ] Todos los `RF-AUTH-xx` tienen prueba unitaria/integración asociada.
*   [ ] Cobertura 100% en `app.domain.auth` (ledger de sesiones, rotación, revocación).
*   [ ] Pruebas de concurrencia: 50 `refresh` simultáneos → solo 1 éxito por token, resto `401`.
*   [ ] `ruff check .`, `mypy`, `pytest -v` pasan.
*   [ ] Commits `feat(auth): ...` siguiendo Conventional Commits.
