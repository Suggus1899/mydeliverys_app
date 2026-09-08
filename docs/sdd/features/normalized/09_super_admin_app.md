# 09 — Aplicación Super Admin

## Alcance

Flutter web claro, adaptable y accesible. Autenticación por contraseña seguida de TOTP; la sesión vive ocho horas en cookie `HttpOnly`, `Secure`, `SameSite=Strict` y cada mutación exige CSRF.

## Requisitos EARS

* **RF-SADM-01:** CUANDO las credenciales sean válidas, EL SISTEMA emitirá un token temporal de cinco minutos ligado al usuario y exigirá TOTP antes de crear la sesión web.
* **RF-SADM-02:** CUANDO haya pagos digitales pendientes, LA CONSOLA mostrará fase, obligación USD/VES congelada, banco, referencia y comprobante, y permitirá aprobar o rechazar con motivo.
* **RF-SADM-03:** CUANDO se apruebe el segundo pago, EL SISTEMA conservará `PAYMENT_2_VERIFYING` hasta la confirmación física del conductor.
* **RF-SADM-04:** CUANDO se abra operaciones, LA CONSOLA recibirá posiciones autorizadas mediante `/ws/admin/map` y marcará ubicaciones con más de 45 segundos como desactualizadas.
* **RF-SADM-05:** CUANDO se cree un ajuste, reembolso, reasignación o liquidación, EL SISTEMA conservará actor, momento, concepto, moneda, comprobante y movimiento original.

## Aceptación

Acceso por teclado, foco visible, lector de pantalla, cifras tabulares, contraste WCAG 2.2 AA y cierre de sesión que revoque la sesión persistida.
