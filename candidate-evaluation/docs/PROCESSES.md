# Procesos — `candidate-evaluation`

Documentación de flujos de negocio implementados en el servicio (API FastAPI, Supabase). Para setup local y tests, ver [SETUP.md](SETUP.md) y [TESTING.md](TESTING.md).

---

## Índice

1. [Matching de candidatos con búsquedas (JD)](#1-matching-de-candidatos-con-búsquedas-jd)

---

## 1. Matching de candidatos con búsquedas (JD)

### Objetivo

Sugerir **qué candidatos encajan con qué búsquedas** (`jd_interviews`) según solapamiento de tecnologías y texto de la descripción del puesto. El resultado lo consume el **HR Backoffice** (lista de matches con scores y acción “Programar entrevista”).

### Entrada (API)

- **POST** al endpoint de matching del servicio (p. ej. `/match-candidates` en la API de `candidate-evaluation`).
- Cuerpo típico: `user_id` y `client_id` opcionales (filtran candidatos y JD según corresponda).

### Motor actual (Fase 2 — determinístico)

El proceso **`do_matching_long_task`** en `api.py` **no** ejecuta CrewAI para armar la lista de matches. En su lugar llama a:

| Componente | Archivo | Rol |
|------------|---------|-----|
| Motor de matching | `matching_engine.py` | Lógica reproducible: tokens, alias, intersección, score |
| Carga de datos | Mismas tablas Supabase que usaban las tools | Candidatos, JD activas, meets existentes |
| Log de diagnóstico | `log_matching_inputs_debug` en `tools/supabase_tools.py` | Volcado opcional de candidatos y JD antes del cálculo |

El **crew** de CrewAI (`matching_crew.py`, `tasks.py`, agente en `agents.py`) sigue en el repositorio como referencia o para evoluciones futuras, pero **el endpoint de matching ya no depende del LLM** para decidir quién matchea con quién.

### Variables de entorno

| Variable | Uso en matching |
|----------|-------------------|
| `SUPABASE_URL` | Obligatorio |
| `SUPABASE_KEY` | Obligatorio |
| `OPENAI_API_KEY` | **No** requerido para este flujo |
| `MATCHING_DEBUG_INPUTS` | Opcional: `0` / `false` desactiva el log detallado de inputs (por defecto activo) |

### Fuentes de datos

1. **Candidatos**
   - Con **`user_id` y `client_id`**: se obtienen IDs desde `candidate_recruiters` y luego los registros en `candidates`.
   - **Sin ambos**: hasta **1000** filas de `candidates` (equivalente al alcance “global” del tool histórico).

2. **Búsquedas (JD)**  
   Tabla `jd_interviews` con **`status = 'active'`**.  
   Si viene **`client_id`**, se filtra por ese cliente.

3. **Exclusiones**  
   Para cada par (candidato, `jd_interview_id`), si ya existe un registro en **`meets`** con ese par, **no** se genera match (evita duplicar entrevistas ya creadas).

### Lógica de encaje (resumen)

1. Normalizar términos del **`tech_stack`** del candidato (lista) con un mapa de **alias** (ej. React/ReactJS, JS/JavaScript, Node/Node.js).
2. Construir el conjunto de requisitos de la búsqueda:
   - Tokens del campo **`tech_stack`** de la JD (texto tipo CSV).
   - Palabras extraídas del **`job_description`**.
3. Calcular la **intersección** entre skills del candidato y requisitos de la JD.
4. Si no hay intersección directa, un **fallback** por subcadena del texto del JD (tokens del candidato presentes en el texto).
5. **Score** (`compatibility_score`) entre **30 y 100** según cantidad de coincidencias y “recall” respecto al stack del candidato.
6. **`match_analysis`**: texto fijo en español explicando que el match es determinístico y qué tecnologías alinearon.
7. **`observations_match`**: se devuelve `null` (el motor actual no puntúa observations).

### Salida (contrato con el backoffice)

Lista **`matches`**: cada elemento agrupa un **candidato** y un array **`matching_interviews`**, cada uno con:

- `jd_interviews`: datos de la fila en BD (`id`, `interview_name`, `agent_id`, `job_description`, `tech_stack`, `client_id`, `created_at`, etc.).
- `compatibility_score`: número entero.
- `match_analysis`: string.
- `observations_match`: `null` o objeto (si en el futuro se enriquece).

El **HR Backoffice** transforma y muestra estos datos; puede rehidratar `agent_id` desde su lista local de JD si el payload viene incompleto.

### Diagnóstico

- Log **`[MATCHING INPUT LOG]`** en consola: candidatos con `tech_stack` y JD con preview de descripción (ver implementación en `log_matching_inputs_debug`).
- Log **`[MATCHING API]`**: cantidad de grupos de candidatos con al menos un match tras el cálculo.

### Tests

- `tests/test_matching_engine.py`: utilidades de tokens y score.
- `tests/test_api_matching_long_task.py`: `do_matching_long_task` con `run_deterministic_matching` mockeado.

### Limitaciones actuales

- Candidatos **sin `tech_stack`** no generan match en el motor determinístico (no hay señal técnica).
- No se usa embeddings ni LLM en este paso; el resultado es **estable** entre ejecuciones con los mismos datos.

---

*Última actualización alineada con el motor determinístico en `matching_engine.py` y `do_matching_long_task` en `api.py`.*
