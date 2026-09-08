# 11 — Despacho, custodia e incidencias

* **RF-DSP-01:** CUANDO varios conductores acepten una oferta, UNA actualización condicional asignará exactamente uno y conservará `READY_FOR_PICKUP`.
* **RF-DSP-02:** EL SISTEMA impedirá que un conductor tenga más de un pedido activo mediante restricción durable en PostgreSQL.
* **RF-DSP-03:** CUANDO el conductor confirme recogida, EL PEDIDO cambiará a `ON_THE_WAY` y comenzará el perfil GPS de ruta.
* **RF-DSP-04:** CUANDO se reasigne después de recoger, EL ADMINISTRADOR adjuntará evidencia de transferencia de custodia; desde el commit el conductor anterior perderá acceso REST y WebSocket.
* **RF-INC-01:** CUANDO transcurran 15 minutos medidos por servidor desde la llegada y no exista un pago digital pendiente, EL CONDUCTOR podrá documentar ausencia y cerrar `DELIVERY_FAILED`.
* **RF-INC-02:** LOS puntos históricos reinyectados nunca activarán geocercas ni transiciones.
