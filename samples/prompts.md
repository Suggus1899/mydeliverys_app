# 🧭 Guía de Prompts SDD — mydeliverys_app (Delivery San Juan de los Morros)

Esta guía contiene los prompts esenciales para cada fase del flujo **Spec-Driven Development (SDD)** adaptados a la arquitectura, reglas innegociables y contexto operativo de **mydeliverys_app**.

---

## 📑 Tabla Rápida de Prompts por Fase

| Fase SDD | Objetivo | Prompt Esencial |
| :--- | :--- | :--- |
| **0. Constitución** | Verificar límites innegociables | *"Revisa `docs/sdd/constitution.md` y `docs/sdd/stack.md`. Confirma que entiendes las reglas: SDD como única verdad, 50/50 financiero (centavo impar al primer pago), manejo exclusivo de `Decimal`, cero dobles asignaciones (`WHERE driver_id IS NULL`), Rate Limiting y sistema de diseño 'Apetito Cálido'. No propongas código que viole estos límites."* |
| **1. Spec (Entrevista EARS)** | Definir el QUÉ y POR QUÉ sin código | *"NO escribas código. Vamos a especificar la funcionalidad `<Nombre>`. Basándote en `samples/spec.md`, hazme preguntas de una en una (máx. 5) sobre actores (CUSTOMER, DRIVER, RESTAURANT_ADMIN, SUPER_ADMIN), casos límite, resiliencia offline en San Juan de los Morros y el modelo 50/50. Luego genera `specs/NNN-<nombre>/spec.md` con RFs numerados en notación formal EARS, fuera de alcance y DoD."* |
| **2. Clarificación (QA)** | Detectar vacíos antes de diseñar | *"Revisa `specs/NNN-<nombre>/spec.md` con mentalidad de QA y arquitecto de sistemas distribuidos: detecta posibles condiciones de carrera (race conditions), colisiones de pedidos entre repartidores, fallas ante desconexión móvil, inconsistencias de centavos y conflictos con la constitución. Solo lista los hallazgos críticos sin escribir código ni resolverlos aún."* |
| **3. Planificación (Plan)** | Diseñar la solución técnica | *"Lee la constitución, la arquitectura y la spec `specs/NNN-<nombre>/spec.md`. Sin escribir código de implementación, genera `specs/NNN-<nombre>/plan.md` con: modelos relacionales/PostGIS o Hive, endpoints REST/WS con Rate Limiting, mitigación atómica de colisiones, componentes UI según `docs/sdd/design_system.md` y estrategia de pruebas. Mapea cada decisión al RF correspondiente."* |
| **4. Tareas (Tasks)** | Desglosar en pasos verificables | *"Divide el plan en tareas atómicas de menos de 30 minutos en `specs/NNN-<nombre>/tasks.md`, ordenadas estrictamente por dependencias (esquemas y BD primero, luego lógica y tests, finalmente UI). Cada tarea debe incluir: RFs que cubre, archivos exactos a modificar, checkboxes y una condición verificable 'Hecho cuando: <comando de prueba que pasa>'."* |
| **5. Implementación (Test-First)** | Construir tarea a tarea con tests | *"Implementa EXCLUSIVAMENTE la tarea T<n> de `tasks.md`. Escribe las pruebas automatizadas primero (`pytest` en backend o `flutter_test` en mobile), luego el código mínimo necesario para pasarlas. Ejecuta la suite de pruebas y muéstrame el resultado limpio. Si todo pasa, marca el checkbox de T<n> y DETENTE para revisión antes de seguir."* |
| **6. Pruebas de Concurrencia y Carga** | Validar colisiones y alta demanda | *"Ejecuta las pruebas de concurrencia (`pytest -v tests/concurrency/`) simulando colisiones de conductores sobre el mismo pedido para asegurar que reciben HTTP 409 Conflict. Si es un endpoint de alta frecuencia, ejecuta el test de estrés con Locust para validar que la latencia p95 sea < 200 ms con 1.500 a 8.000 usuarios concurrentes."* |
| **7. Validación Final** | Auditar cumplimiento de la spec | *"Recorre la spec `specs/NNN-<nombre>/spec.md` requisito por requisito (RF-1 a RF-n). Indica qué test automatizado cubre cada uno y su resultado. Verifica el análisis estático (`ruff check .` y `flutter analyze`) y confirma si la funcionalidad está 100% cumplida para fusionar con commit convencional."* |
| **8. Gestión del Cambio (Spec-First)** | Modificar requisitos sin romper código | *"Tenemos un nuevo requerimiento o ajuste: `<X>`. REGLA CONSTITUCIONAL: NO toques el código aún. Actualiza primero la spec en `specs/NNN-<nombre>/spec.md` o en `docs/sdd/features/`, documenta los nuevos RFs y muéstrame el diff para mi aprobación antes de planificar tareas."* |

---

## 💡 Consejos de Uso para el Desarrollador
1. **Nunca saltes de la Spec a la Implementación:** El valor de SDD radica en clarificar y planificar antes de picar código. Si una duda surge durante la implementación, la spec estaba incompleta.
2. **Una tarea a la vez:** Obliga al agente de IA a detenerse tras cada tarea (`T<n>`). Esto evita que genere cientos de líneas sin validar y facilita revertir cambios si algo no encaja.
3. **Tests Primero (TDD en cada tarea):** Si el test se escribe después del código, suele acomodarse a la implementación en lugar de validar el requisito formal EARS.
