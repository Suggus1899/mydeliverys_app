# 10 — Tarifas, cobertura y tasa

* **RF-RATE-01:** CUANDO Celery Beat dispare cada 30 minutos, EL WORKER consultará el dólar oficial, validará `moneda=USD`, `fuente=oficial`, `promedio>0` y `fechaActualizacion` no futura, y guardará una versión con hora de consulta separada.
* **RF-RATE-02:** SI la última consulta válida tiene hasta seis horas, EL SISTEMA podrá cotizar con ella; DESPUÉS bloqueará nuevas cotizaciones sin alterar pedidos existentes.
* **RF-FEE-01:** CUANDO un administrador configure tramos, EL SISTEMA rechazará huecos, solapamientos, montos negativos y límites invertidos.
* **RF-FEE-02:** CUANDO una dirección quede fuera del último tramo activo, `POST /orders/draft` responderá `DELIVERY_OUT_OF_COVERAGE`.
* **RF-FEE-03:** EL SISTEMA calculará distancia geodésica en PostGIS y guardará distancia, tramo y tarifas en el snapshot.
