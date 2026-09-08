## Prompts por fase

|Fase|Prompt esencial|
|---|---|
|Constitución|"Proponme la constitución de este proyecto: N principios cortos y verificables sobre stack, calidad, tests y límites. Máx. 15 líneas. Espera mi aprobación."|
|Spec (entrevista)|"NO escribas código. Hazme preguntas de una en una (máx. 6) sobre casos límite, errores y alcance, y después genera spec.md con RF numerados en EARS, fuera de alcance y criterios de finalización. Solo el QUÉ y el POR QUÉ."|
|Clarificación|"Revisa la spec como un QA profesional: ambigüedades, contradicciones, casos límite ausentes, conflictos con la constitución. Solo detecta, no resuelvas."|
|Plan|"Lee constitución y spec. Sin código: genera plan.md con módulos, modelo de datos, decisiones justificadas (con la alternativa descartada) y estrategia de tests. Indica qué RF cubre cada parte."|
|Tareas|"Divide el plan en tareas de <30 min, ordenadas por dependencia, cada una con sus RF y una línea 'Hecho cuando:' verificable. Con checkboxes."|
|Implementación|"Implementa SOLO la tarea Tn. Tests primero. Ejecuta la suite y muéstrame el resultado. Marca Tn como hecha y PÁRATE."|
|Validación|"Recorre la spec RF (Requisito Funcional) por RF: qué test cubre cada uno y su resultado. Veredicto final: ¿spec cumplida?"|
|Cambio|"Nuevo requisito: <X>. NO toques código: actualiza primero la spec y muéstrame el diff."|
