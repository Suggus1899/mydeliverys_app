# 12 — Conciliación, compensaciones y operación

* **RF-OPS-01:** CADA cobro, ajuste y devolución será inmutable; las correcciones crearán movimientos compensatorios relacionados.
* **RF-OPS-02:** CUANDO se aplique un movimiento bancario, UNA restricción durable impedirá asociarlo a dos pedidos.
* **RF-OPS-03:** SI un abono es tardío, parcial o excedente, EL SISTEMA conservará el movimiento como incidencia sin reactivar pedidos cancelados.
* **RF-OPS-04:** CUANDO se genere una liquidación, EL SISTEMA fijará beneficiario, periodo, moneda, conceptos y saldo elegible, excluyendo saldos ya distribuidos.
* **RF-OPS-05:** SOLO una liquidación `DRAFT` podrá confirmarse; solo una `CONFIRMED` con comprobante podrá marcarse `PAID`.
* **RF-OPS-06:** CADA alerta operativa por tasa, pago demorado, reserva, cola o ubicación conservará correlación y quedará visible al administrador.
