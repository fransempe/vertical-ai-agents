# Guía de testing — `candidate-evaluation`

Documentación del enfoque de pruebas del paquete `agents/candidate-evaluation`: comandos, convenciones, inventario de tests, qué código cubren, historial por tandas y backlog.

**Resumen de entrega / cierre:** [`ANALISIS_FINAL_TESTING.md`](ANALISIS_FINAL_TESTING.md) — análisis global de estrategia, alcance y CI (complementa este documento).

---

## Visión general

- Los tests viven en `tests/` y se ejecutan con **pytest** desde el directorio del paquete.
- Hay mucha lógica acoplada a **Supabase**, **OpenAI**, **AWS** y **CrewAI**. La estrategia prioritaria es **mockear I/O y clientes** (`monkeypatch`, objetos tipo cadena Supabase) y cubrir **validaciones, errores y ramas puras** antes de integración real.
- El **CI** ejecuta **`ruff check .`**, **`ruff format --check .`** y **pytest** con cobertura.

---

## Requisitos

- Python **3.11+** (en GitHub Actions se usa **3.12**).
- Instalación:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

---

## Dónde ejecutar los comandos

Siempre desde la raíz del paquete:

```bash
cd agents/candidate-evaluation
```

---

## Comandos principales

### Tests unitarios (por defecto)

```bash
pytest
```

- Configuración en `[tool.pytest.ini_options]` de `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["."]`).
- Por defecto se excluyen tests marcados con `@pytest.mark.integration` (`addopts` incluye `-m "not integration"`).

### Solo integración

```bash
pytest -m integration --override-ini addopts="-q --strict-markers"
```

Un **POST real** a `/chatbot` con cuerpo **válido** (p. ej. campo `message`) requiere que el **servidor** tenga `OPENAI_API_KEY` y, según la ruta de código, cliente Supabase/RAG configurado; no está en la suite por defecto. Usar solo contra staging o entorno de prueba y documentar variables antes de automatizar un smoke adicional.

### Un archivo o filtro por nombre

```bash
pytest tests/test_api_formatters.py
pytest tests/test_supabase_tools.py -k fetch_job
```

### Cobertura

```bash
pytest --cov=. --cov-report=term-missing
```

- `[tool.coverage.run]` en `pyproject.toml`: `source = ["."]`, omite `tests/*`, `test_vector_search.py`, entornos virtuales.
- El porcentaje total depende de qué módulos se importan al correr la suite; comparar runs en el mismo entorno.

### Lint (alineado con CI)

```bash
ruff check .
ruff format --check .
```

Para aplicar formato en local (antes de commit):

```bash
ruff format .
```

### Flujo sugerido antes de un PR

```bash
ruff check .
ruff format --check .
pytest
pytest --cov=. --cov-report=term-missing
```

---

## Configuración relevante (`pyproject.toml`)

| Sección | Uso |
|--------|-----|
| `[tool.pytest.ini_options]` | `testpaths`, `pythonpath`, marcador `integration`, `addopts` |
| `[tool.coverage.run]` / `[tool.coverage.report]` | Fuentes, `omit`, `fail_under`, `show_missing` |
| `[tool.ruff]` / `[tool.ruff.lint]` | Target Python 3.11, `line-length`, exclusiones; **select** `E,F,I,UP,B,SIM`; **ignore** `E501`, `B904` |

---

## Convenciones al escribir tests

1. **Importar `api` o cadenas que pasen por `cv_tools` / S3**  
   Suele hacer falta **`pytest.importorskip("boto3")`** al inicio del módulo de test (o el test falla en entornos mínimos).

2. **Herramientas CrewAI `@tool`**  
   La función queda envuelta en `crewai.tools.base_tool.Tool`. Para llamar la implementación:  
   `nombre_herramienta.func(...)`  
   Ejemplo: `supabase_tools.fetch_job_description.func("https://...")`.

3. **Mocks de Supabase**  
   Patrón habitual: `monkeypatch.setattr(modulo, "create_client", lambda url, key: _FakeClient())` donde `_FakeClient().table(nombre)` devuelve objetos encadenables (`.select().eq().limit().execute()`, etc.) según el flujo real del código bajo test.

4. **FastAPI `TestClient`**  
   Para endpoints async, el cliente ejecuta el event loop; si se mockea `run_in_threadpool`, usar **`async def`** que ejecute el callable (como en `test_api_read_cv.py`).

5. **CrewAI `Task` y validación Pydantic**  
   `Task(agent=...)` exige un agente compatible con `BaseAgent`, no un `MagicMock` genérico. En este repo se reutiliza **`create_data_extractor_agent()`** para smoke de `create_extraction_task`.

6. **Estado global en tests de API**  
   Ejemplo: `matching_runs` en `api.py`. Los tests deben **insertar y limpiar** claves en `finally` para no contaminar otros tests.

7. **OpenAI import lazy en `_chatbot_impl`**  
   El cliente se instancia con `from openai import OpenAI` dentro de la función. Para tests del chatbot, parchear **`openai.OpenAI`** (módulo `openai`) con `monkeypatch.setattr(openai, "OpenAI", FakeClass)` antes del `TestClient.post("/chatbot", ...)`.

---

## Inventario de archivos (`tests/`)

| Archivo | Contenido principal |
|---------|----------------------|
| `conftest.py` | Hooks/fixtures compartidos (placeholder para futuros mocks globales). |
| `test_helpers.py` | `utils.helpers`: `clean_uuid`, `is_valid_uuid`. |
| `test_utils_logger.py` | `EvaluationLogger`: llamadas a métodos públicos sin excepción. |
| `test_api_formatters.py` | Helpers al inicio de `api.py` (`format_*`, `load/render_email_template`, `b64decode`), modelos Pydantic básicos; **`load_email_template`** con error de lectura genérico; requiere cadena de import con `boto3`. |
| `test_api_status.py` | `GET /status` con `TestClient`. |
| `test_api_matching_routes.py` | `GET /match-candidates/{run_id}` (404, `done`, `error`, `queued`); **`POST /match-candidates`** con mock de `do_matching_long_task` o **500** si `Thread.start` falla. |
| `test_api_matching_long_task.py` | **`do_matching_long_task`**: env faltante, éxito con/sin filtros, **`kickoff`** con error, JSON lista, dict **sin** clave **`matches`**, texto sin **`"matches"`** útil, **markdown** + recuperación, **`.raw`**, extracción **markdown** / **llaves**. |
| `test_api_read_cv.py` | `POST /read-cv`: éxito; **`.raw`** con JSON; varios **`{...}`** en el texto (último bloque con **success**); estados **AlreadyExists** / **failed**; **kickoff** que lanza → 500; **env obligatorio** faltante → 500. |
| `test_api_evaluate_meet.py` | `POST /evaluate-meet`: matriz 8–10 + **sin Supabase**; **500** fábrica crew; **string** sin JSON / **`{invalid}`** / JSON **lista**; **`get_meet_evaluation_data._func`** (**`SimpleNamespace`**); enriquecimiento con error; parse y **`save_meet_evaluation`** (**`__wrapped__`**, fallo, excepción, **None**); **emociones** desde `conversations`; **except** en fallback emotion si **`create_client`** falla. |
| `test_api_candidate_and_chatbot.py` | `GET /get-candidate-info`: UUID inválido, **not_found**, éxito, **`tech_stack` no lista** + `observations.other`, excepción Supabase → 500, fila **no mapping** → 500; `POST /chatbot` sin `OPENAI_API_KEY` → 500. |
| `test_api_chatbot_success.py` | `POST /chatbot`: RAG+OpenAI mockeados; ramas sin contexto; **thresholds** 0.3/0.4/0.5; **historial** en mensajes OpenAI; **chunks** sin resultados vectoriales en ningún threshold; **excepción genérica** (p. ej. fallo en `get_supabase_client`) → 500. |
| `test_api_elevenlabs_smoke.py` | `POST /create-elevenlabs-agent` y `PATCH /update-elevenlabs-agent` sin variables Supabase/ElevenLabs → 500. |
| `test_api_elevenlabs_success.py` | Creación/actualización → 200; **404** JD; **400** validaciones; **`POST`**/**`PATCH`** **500** si **`get_client_email`** no resoluble; **`POST`** **500** (ElevenLabs **None**, sin **agent_id**, **update** vacío); resultado **objeto** con **`.agent_id`** o solo **`.id`**; **`index_jd_interview`** con error; **`PATCH`** **400** (JD vacío, sin **agent_id** / **client_id**); **`PATCH`** **500** (excepción en prompt); **`PATCH`** index error → **200**. |
| `test_supabase_tools.py` | … **`fetch_job_description`** (**`RequestException`**), **`get_jd_interviews_data`**, **`get_all_jd_interviews`**, **`get_candidates_data`** (límite + error), **`get_existing_meets_candidates`** (éxito + error), **`send_evaluation_email`**, **`send_match_notification_email`**, … |
| `test_vector_tools.py` | Cliente Supabase, **`generate_embedding`** (éxito + error API), chunks, `update_knowledge_chunk`, `index_*`, … |
| `test_agents_smoke.py` | `create_data_extractor_agent()` y comprobación de rol. |
| `test_tasks_smoke.py` | Smoke de tasks + **`create_matching_task`** (nombres de herramientas en descripción: `get_existing_meets_candidates`, etc.). |
| `test_crew_smoke.py` | **`create_data_processing_crew`**, **`create_filtered_data_processing_crew`**, **`matching_crew`**, **`patch.object(Crew, kickoff)`** en matching, **`single_meet_crew`**, **`cv_crew.create_cv_analysis_crew`** (composición; sin **`kickoff`** real salvo patch). |
| `integration/test_placeholder.py` | `@pytest.mark.integration`: `GET /status`, `GET /docs`; Bearer opcional; **`POST /chatbot`** mínimo (`POST_SMOKE`) → **422**; opcional **`CHATBOT_LIVE`** con JSON válido (skip si 500 por OpenAI). |

---

## Cobertura por área de producto (orientativo)

| Área | Cobertura en tests |
|------|--------------------|
| `utils.helpers` | Directa (`test_helpers.py`). |
| `utils.logger` | Ligera (`test_utils_logger.py`). |
| `api.py` (helpers + rutas parciales) | `/evaluate-meet` (parse, emociones Supabase, guardado); `/read-cv`; **`/match-candidates`**; **ElevenLabs** create/patch; **`/chatbot`** (éxito + error); **`/get-candidate-info`**; helpers de email. |
| `tools/supabase_tools.py` | Parcial: matching, **`get_jd_interviews_data`** (incl. error en query), **`get_conversations_by_jd_interview`**, **`get_current_date`**, `save_interview_*`, etc. |
| `tools/vector_tools.py` | Parcial: **`generate_embedding`** (incl. fallo en API), chunks, update, indexación, … |
| `agents.py` | Smoke de una factory. |
| `tasks.py` | Smoke incl. **`create_matching_task`** (herramientas en texto), **filtered** / demás factories. |
| `crew.py` / `filtered_crew.py` | Smoke de composición en **`test_crew_smoke.py`** (sin ejecutar el flujo). |
| `tracking.py`, `fallback_estimator` | Sin tests dedicados (el estimador por heurística fue eliminado del código). |

Muchos endpoints de `api.py` y herramientas largas de `supabase_tools` siguen sin tests; el backlog abajo los prioriza.

---

## Historial de trabajo por tandas (resumen)

Las tandas describen cómo fue creciendo la suite; sirven para contexto y para planificar más cobertura.

### Tanda 1

- `supabase_tools`: `_fetch_url_with_retries` (éxito tras timeout, agotar reintentos), validaciones y errores de `fetch_job_description` (`.func`).
- `vector_tools`: errores claros sin `SUPABASE_*` y sin OpenAI para embeddings.

### Tanda 2

- `api` (helpers): `b64decode` con UTF-8 inválido; `render_email_template` (plantilla vacía, `KeyError`, error de `.format`).
- `vector_tools`: embedding OpenAI mockeado; insert/search/delete de chunks vía RPC mockeado.
- `supabase_tools`: `fetch_job_description` OK (`text/html`, `text/plain`); `HTTPError` / `ConnectionError`; `extract_supabase_conversations`; `get_current_date`.

### Tanda 3

- `vector_tools`: `update_knowledge_chunk` (RPC string/dict; fallback manual update/insert).
- `supabase_tools`: `get_meet_evaluation_data` (meet inexistente + flujo OK); `save_meet_evaluation` (sin env, JSON inválido, tipo incorrecto, sin `meet_id`, insert OK).
- `api`: estado de matching y `POST` con thread mockeado.
- `agents`: smoke `create_data_extractor_agent`.

### Tanda 4

- `supabase_tools`: `save_meet_evaluation` **update**; `get_client_email` (varias ramas).
- `vector_tools`: `index_candidate`, `index_jd_interview`, `index_all_candidates`, `index_all_jd_interviews`.
- `api`: `POST /read-cv` con mocks.
- `tasks`: `create_extraction_task` con agente real.

### Tanda 5

- **`api.py`**: `POST /evaluate-meet` con crew fake, `run_in_threadpool` mockeado (compatible con llamadas `func` o `func, *args`), `save_meet_evaluation` reemplazado en el módulo `api` para devolver éxito sin BD; resultado incluye `conversation_analysis.emotion_sentiment_summary` con texto de prosodia para no entrar al fetch de Supabase; `is_potential_match: false` para no ejecutar el bloque de email.
- **`api.py`**: `GET /get-candidate-info` (UUID inválido → `status: error` en cuerpo 200; UUID válido con `get_supabase_client` mockeado); `POST /chatbot` sin `OPENAI_API_KEY` → HTTP 500.
- **`vector_tools.py`**: `index_meet` (incl. `tech_stack` string en candidato); `index_meet_evaluation` (alertas, match, technical); `index_all_meets` con y sin `limit`; `index_all_meet_evaluations` con `limit`.
- **`tasks.py`**: `create_analysis_task` y `create_job_analysis_task` con `context` apuntando a la tarea de extracción.

### Tanda 6

- **`api.py`**: `POST /chatbot` con RAG mockeado (`get_supabase_client` devuelve conteo de chunks, `search_similar_chunks` devuelve filas, `openai.OpenAI` fake con `chat.completions.create`); `POST /create-elevenlabs-agent` y `PATCH /update-elevenlabs-agent` con env faltante → 500.
- **`tools/supabase_tools.py`**: `get_jd_interviews_data` (sin env; por ID vacío → `[]`; por ID con fila); `get_candidates_data` con `limit` como dict y `create_client` mockeado.
- **`tools/vector_tools.py`**: `index_all_meet_evaluations(limit=None)`; `index_candidate_jd_status`; `index_all_candidate_jd_status(limit=…)`.
- **`tasks.py`**: `create_candidate_job_comparison_task` con tres tareas en `context`.

### Tanda 7

- **`api.py`**: `POST /create-elevenlabs-agent` y `PATCH /update-elevenlabs-agent` con env Supabase/ElevenLabs, cliente Supabase encadenable, `get_client_email`, `create_elevenlabs_agent` / `generate_elevenlabs_prompt_from_jd` + `update_elevenlabs_agent_prompt` y `index_jd_interview` mockeados → 200.
- **`api.py`**: `POST /evaluate-meet` con resultado del crew sin `candidate.id` / `jd_interview.id`; `get_meet_evaluation_data` mockeado (`.func`) y captura del JSON pasado a `save_meet_evaluation` para comprobar enriquecimiento.
- **`api.py`**: `POST /chatbot` con `total_chunks == 0` y con error en `search_similar_chunks` (OpenAI mockeado vía `openai.OpenAI`).
- **`tools/vector_tools.py`**: `index_all_candidate_jd_status(limit=None)`; filas con fallo en `index_candidate_jd_status` incrementan solo los aciertos válidos.
- **`tools/supabase_tools.py`**: `get_jd_interviews_data(None)` → consulta `status=active` y `limit=50`; `create_candidate` con insert mockeado y `index_candidate` que falla (no rompe la creación).
- **`tasks.py`**: `create_processing_task` con cuatro tareas en `context`.

### Tanda 8

- **`api.py`**: `/evaluate-meet` con `is_potential_match: true`, `create_client` mockeado para `meets` (join anidado) y `conversations` (`conversation_data`); respuesta con mensaje que incluye **Email enviado**.
- **`api.py`**: `/evaluate-meet` sin prosodia en el resultado del crew: primer `create_client` para **conversations** (`emotion_analysis` + `order`/`limit`); segundo para email; `save_meet_evaluation` verifica `raw_emotion_analysis` en el JSON guardado.
- **`tools/supabase_tools.py`**: `create_candidate` con email ya existente (**AlreadyExists**); inserción en **candidate_recruiters** cuando hay `user_id` y `client_id`.
- **`tasks.py`**: `create_email_sending_task` con `context` = `processing_task`; cadena single-meet (extracción → evaluación) con `create_single_meet_evaluator_agent`.
- **`integration/`**: smoke HTTP opcional con `CANDIDATE_EVAL_INTEGRATION_BASE_URL` y `GET /status`.

### Tanda 9

- **`api.py`**: `/evaluate-meet` match sin **`jd_interview` anidado** (solo consulta `meets`, sin email); match con cliente **sin email**; **`render_email_template`** forzado a error (API 200, sin “Email enviado”); **`messages: []`** en conversación (aún “Email enviado”).
- **`tools/supabase_tools.py`**: **`save_interview_evaluation`**: JD inexistente, `client_id` NULL, JSON de `summary` inválido, **insert** exitoso en `interview_evaluations`.
- **`tasks.py`**: **`create_evaluation_saving_task`**: `processing_task` en `context`; descripción con UUID de JD fijo o texto de “buscar jd_interview_id”.
- **`integration/`**: smoke opcional **`GET /docs`** (Swagger) con la misma base URL.

---

### Tanda 10

- **`api.py`**: `/evaluate-meet` con **`meets` sin filas** para el `meet_id` → 200, sin “Email enviado”.
- **`tools/supabase_tools.py`**: **`save_interview_evaluation`** rama **update** (registro previo + `update` con datos); fallo si **update** no devuelve filas.
- **`tasks.py`**: **`create_filtered_extraction_task`** (JD en descripción + herramienta); **`create_matching_task`** con `user_id`/`client_id` vs global (`get_candidates_data` / `get_all_jd_interviews`).
- **`integration/`**: cabecera opcional **`Authorization: Bearer`** via `CANDIDATE_EVAL_INTEGRATION_BEARER_TOKEN`.

---

### Tanda 11

- **`api.py`**: `/evaluate-meet` con crew sin prosodia y **sin variables `SUPABASE_*`**: no se llama a Supabase para emociones; respuesta **success**.
- **`tools/supabase_tools.py`**: **`get_existing_meets_candidates`** (mapa jd → candidatos); **`get_conversations_by_jd_interview`** (JD inexistente; JD OK y **sin meets** → mensaje informativo).
- **`tasks.py`**: **`create_matching_task`**: texto incluye **`get_existing_meets_candidates`** (variantes recruiter y global).
- **`crew.py` / `filtered_crew.py`**: **`test_crew_smoke.py`** — 7 tareas y 6 agentes en ambos crews; stub de `get_conversations_by_jd_interview` en el filtrado.
- **`integration/`**: POST opcional a **`/chatbot`** con cuerpo `{}` y **`CANDIDATE_EVAL_INTEGRATION_POST_SMOKE=1`** → espera **422** (no exige OpenAI).

---

### Tanda 12

- **`tools/supabase_tools.py`**: **`get_conversations_by_jd_interview`**: mock encadenado **JD → `clients` → `meets` → `conversations`** con filas anidadas tipo **`candidates`**; la herramienta devuelve una **lista JSON** con metadatos de JD, cliente y candidato. Caso adicional: **dos `meets`** y acumulación de filas; **`client_id` NULL** (no se consulta `clients`; `client` en cada conversación es `null`).
- **`api.py`** / **integración**: sin cambios de código en esta tanda; siguen priorizables huecos de cobertura en **`api.py`** y un smoke de **POST `/chatbot` con cuerpo válido** solo en entorno controlado (servidor con **`OPENAI_API_KEY`**, RAG/Supabase según despliegue), no como obligación de CI.

---

### Tanda 13

- **`api.py`**: **`POST /read-cv`** — parseo desde **`.raw`**, estados **AlreadyExists** / **failed**, **500** si el crew lanza.
- **`api.py`**: **`POST /evaluate-meet`** — resultado del crew como string en **bloque de código markdown (json)** en **`raw`**, o **dict** en **`content`**.
- **`api.py`**: **`load_email_template`** — excepción genérica al abrir (p. ej. `PermissionError`) → `""`.
- **`api.py`**: **`GET /get-candidate-info`** — **`not_found`**, **`tech_stack`** no lista, **`observations.other`**, error en **`get_supabase_client`** → 500.
- **`tools/supabase_tools.py`**: **`get_current_date`** — rama **`except`** con `fallback_date`.
- **`integration/`**: **`CANDIDATE_EVAL_INTEGRATION_CHATBOT_LIVE=1`** — POST **`/chatbot`** con **`message`** + **`conversation_history`**; **skip** si el servidor responde 500 por falta de OpenAI (documentado en el docstring del módulo).

---

### Tanda 14

- **`api.py`**: **`POST /match-candidates`** — **500** si **`Thread.start()`** falla (más limpieza de **`matching_runs`** con `uuid4` fijo).
- **`api.py`**: **`POST /read-cv`** — **500** por **variables de entorno faltantes** (AWS + OpenAI).
- **`api.py`**: **`POST /evaluate-meet`** — resultado con **`.raw` como dict**; resultado con **`.content` como string JSON** (sin markdown).
- **`api.py`**: **`PATCH /update-elevenlabs-agent`** — **404** si no hay fila en **`jd_interviews`**.
- **`tools/vector_tools.py`**: **`generate_embedding`** — error de la API de embeddings se **propaga** tras el `log`.
- **`tools/supabase_tools.py`**: **`get_client_email`** — **excepción** en **`create_client`** → JSON con **`error`**.

---

### Tanda 15

- **`api.py` — `evaluate-meet`**: parseo con JSON inválido (rama **except** interna); **`str(result)`** sin `.raw`/`.content`; **`save_meet_evaluation`** con **`success: false`**, con **excepción**, y con herramienta **`None`**; **Supabase `conversations`** para **fusionar `raw_emotion_analysis`** cuando el resumen tiene **burst** pero no **raw**.
- **`api.py` — `chatbot`**: **500** por excepción genérica en **`_chatbot_impl`** (p. ej. fallo al obtener cliente Supabase).
- **`api.py` — `create-elevenlabs-agent`**: **404** JD inexistente; **400** **`job_description`** vacío; **400** sin **`client_id`**; **400** si **`get_client_email`** devuelve **`error`**.
- **`tools/supabase_tools.py`**: **`get_jd_interviews_data`** — excepción en cadena **`.execute()`** → JSON **`error`**.
- **`matching_crew` / `single_meet_crew`**: smoke de composición en **`test_crew_smoke.py`** (1 agente / 1 tarea matching; 1 agente / 2 tareas single-meet con **`get_meet_evaluation_data`** mockeado).

---

### Tanda 16

- **`api.py` — `do_matching_long_task`**: nuevo **`test_api_matching_long_task.py`** — env faltante → **error**; éxito con **filtros** `user_id`+`client_id`; sin filtros; solo **`user_id`**; **`kickoff`** que lanza; resultado **JSON lista**; dict sin **`matches`**; resultado con **`.raw`** string.
- **`api.py` — `evaluate-meet`**: **`save_meet_evaluation.__wrapped__`** (callable con `*args`).
- **`api.py` — ElevenLabs create**: **500** si **`create_elevenlabs_agent`** devuelve **None**; **500** sin **agent_id** en respuesta; **500** si **`update`** de **`jd_interviews`** no devuelve filas.
- **`api.py` — ElevenLabs update**: **500** por excepción en **`generate_elevenlabs_prompt_from_jd`** (handler genérico).
- **`tools/supabase_tools.py`**: **`fetch_job_description`** — **`RequestException`** genérica (además de timeout/HTTP/connection).
- **`cv_crew`**: smoke **`create_cv_analysis_crew`** en **`test_crew_smoke.py`**.

---

### Tanda 17

- **`api.py` — `evaluate-meet`**: excepción en **`create_client`** durante el fallback de **`emotion_analysis`** → respuesta **200** (bloque **except** 828–829).
- **`api.py` — `chatbot`**: búsqueda vectorial probando **thresholds** **0.3 → 0.4 → 0.5** hasta obtener chunks.
- **`api.py` — `create-elevenlabs-agent`**: resultado tipo **objeto** con **`.agent_id`**; **`index_jd_interview`** que lanza → **200** (indexación en try/except).
- **`api.py` — `do_matching_long_task`**: extracción de **`matches`** desde bloque **markdown** ```json``` y desde **llaves balanceadas** cuando el texto no es JSON directo.
- **`tools/supabase_tools.py`**: **`send_evaluation_email`** — **éxito** con **`requests.post`** mockeado; **`RequestException`** → JSON **`error`**.

---

### Tanda 18

- **`tools/supabase_tools.py`**: **`send_match_notification_email`** — éxito con **`post`** mockeado; **`RequestException`**; excepción genérica (p. ej. **`ValueError`**).
- **`api.py` — `read-cv`**: varios bloques **`{...}`** en el texto; se usa el último con **`success`** / **`email`** (heurística 251–257).
- **`api.py` — `evaluate-meet`**: **500** si `create_single_meet_evaluation_crew` lanza; **string** sin JSON; **`{invalid}`** (error de parseo interno); **enriquecimiento** vía **`get_meet_evaluation_data._func`** solo (**`SimpleNamespace`**); **`_func`** que lanza → **200**; **`save_meet_evaluation`** como función.
- **`api.py` — `do_matching_long_task`**: dict JSON **válido** sin clave **`matches`** (rama «formato no reconocido»).
- **`api.py` — `chatbot`**: historial con **`user`/`assistant`** pasa a **`chat.completions.create`** (mensajes capturados).
- **`api.py` — `PATCH /update-elevenlabs-agent`**: **400** **`job_description`** vacío; **400** sin **`agent_id`**; **400** sin **`client_id`**; **200** si **`index_jd_interview`** falla en el try (1190–1191).

**Nota:** En CrewAI reciente, **`Crew`** es modelo Pydantic: no se puede sustituir **`kickoff`** en instancia con `monkeypatch.setattr` (no hay campo); se omitió el smoke de `kickoff` mockeado.

---

### Tanda 19

- **`tools/supabase_tools.py`**: **`get_existing_meets_candidates`** — **`create_client`** lanza → JSON **`error`**.
- **`api.py` — `do_matching_long_task`**: bloque **markdown** con JSON inválido (404–405) y segundo objeto **`{"matches": …}`** recuperable.
- **`api.py` — `GET /get-candidate-info`**: fila de candidato **sin** `.get` → **500** (1677–1683).
- **`api.py` — `evaluate-meet`**: **`json.loads`** del string devuelve **lista** → `full_result` → **`{}`** (684–685).
- **`api.py` — `chatbot`**: hay chunks en BD pero **`search_similar_chunks`** vacío en todos los thresholds (1461–1462).
- **`api.py` — ElevenLabs**: **`POST`/`PATCH`** **500** si **`get_client_email`** no es resoluble (1277–1279 / 1113–1115); **`POST`** resultado objeto con solo **`.id`** (1344–1345).

---

### Tanda 20

- **`tools/supabase_tools.py`**: **`get_all_jd_interviews`** — con **`client_id`** (doble **`.eq`**); sin **`client_id`** (solo **active**); **`create_client`** lanza → JSON **`error`**.
- **`tools/supabase_tools.py`**: **`get_candidates_data`** — excepción en **`.limit`/execute** → **`error`**; **`limit`** string no numérico → **100** (1362–1365).
- **`api.py` — `do_matching_long_task`**: texto **sin** substring **`"matches"`** en sentido JSON → **0** matches (469–474); **estrategia 3** (438–449) con **`re.finditer(r'"matches"')`** vacío (monkeypatch) + texto no JSON válido global → extracción **primer `{`…último `}`**.
- **`test_crew_smoke.py`**: **`patch.object(Crew, "kickoff", …)`** en **`matching_crew`** y en **`cv_crew`** sin LLM real.

**Nota (estrategia 3 en `matching`)**: En producción, si hay **`"matches"`** como clave, la **estrategia 2** suele ganar; el test anterior fuerza la **3** vaciando **`finditer`** para esa clave.

---

### Tanda 21

- **`api.py` — `read-cv`**: bloque **`{...}`** inválido y siguiente válido (251–252); **`re.findall`** lanza → **`except`** externo silencia (263–265).
- **`api.py` — `do_matching_long_task`**: estrategia 2 — **`"matches"`** sin **`{`** previo → **`continue`** (415); estrategia 3 — slice con **`"matches"`** pero JSON inválido (448–449) → **0** matches.
- **`tools/supabase_tools.py` — `create_candidate`**: **`tech_stack`** JSON lista y escalar no lista (1444–1447); **`observations`** JSON inválido / tipo no válido (1454–1465); fallo en **select** por email → insert igual (1499–1501); email inválido → rama sin precheck (1505–1507); **`candidate_recruiters`** respuesta vacía o excepción en insert (1529–1535); **`create_client`** lanza → JSON **`success: false`** (1556–1558).

---

### Tanda 22

- **`api.py` — `evaluate-meet`**: enriquecimiento con **`get_meet_evaluation_data.__wrapped__`** (701–702) y **callable** sin **`name`** (707–708); **`save_meet_evaluation.func`** / **`._func`** (844–847); email de match: roles **`assistant`** / **`ai`** / otro (940–943); **`conversation_data`** como **string** (945–946).
- **`api.py` — ElevenLabs PATCH**: **`get_client_email.__wrapped__`** / **`._func`** (1106–1111); respuesta con **`error`** (1120–1123); **`sender_email`** vacío (1125–1129); **`generate_elevenlabs_prompt_from_jd`** con prompt vacío tras **strip** (1137–1140); **`update_elevenlabs_agent_prompt`** falsy (1174–1178).
- **`api.py` — `create-elevenlabs-agent`**: **`get_client_email.__wrapped__`** / **`._func`** (1270–1275); **400** si email vacío (1291–1295); **500** por excepción genérica p. ej. **`create_client`** (1395–1401).
- **`test_api_chatbot_success.py`**: ya cubría **chunks en BD pero búsqueda vacía en todos los thresholds** (1461–1462) — sin cambio en esta tanda.

**Cobertura `api.py` (referencia)**: ~**99%**; sin cubrir de forma práctica: **`except HTTPException: raise`** en **`get-candidate-info`** (1676) y **`if __name__ == "__main__"`** (1706–1707).

---

### Tanda 23

- **`tools/supabase_tools.py` — `save_interview_evaluation`**: excepción en consulta **`jd_interviews`** (1608–1610); **insert** sin filas en respuesta (1837–1841).
- **`tools/supabase_tools.py` — `save_meeting_minute`** (función no decorada con **`@tool`**): éxito con **`generate_embedding`** / **`update_knowledge_chunk`** mockeados; **`tags`** lista, JSON lista, CSV y escalar JSON; errores sin env / UUID / **`raw_minutes`** vacío / fallo de embedding; insert vacío; fallo al indexar en **`knowledge_chunks`** sin tumbar el **200** lógico.
- **`tools/supabase_tools.py` — `get_candidates_by_recruiter`**: tabla vacía; filas sin **`candidate_id`** válido; éxito con **`in_('id', …)`**; excepción en cadena Supabase.

---

### Tanda 24

- **`tools/supabase_tools.py` — `_fetch_url_with_retries`**: **`HTTPError`** en **`Session.get`** → **`RequestException`** (no reintento).
- **`fetch_job_description`**: URL vacía/solo espacios; **`RuntimeError`** desde **`_fetch_url_with_retries`** → **`except Exception`** externo.
- **`extract_supabase_conversations` / `SupabaseExtractorTool`**: **`create_client`** lanza → JSON **`error`**; instanciación con mock de cliente.
- **`save_meet_evaluation`**: **`candidate_id`** / **`jd_interview_id`** obligatorios; **update** e **insert** con respuesta **`.data`** vacía → fallo.
- **`get_jd_interviews_data`**: truncado de **`job_description`** largo; aviso si JSON serializado supera ~100k caracteres (**`capsys`**).
- **`get_candidates_data`**: **`limit`** tipo dict sin entero usable → **100** por defecto.
- **`create_candidate`**: **`observations`** ya **dict** se envía tal cual al **insert** (sin copia JSON).
- **`save_interview_evaluation`**: fallo en cadena **`.select`…`.execute()`** de **`interview_evaluations`**; **`create_client`** lanza → JSON **`error`**.
- **`save_meeting_minute`**: **`create_client`** lanza → **`success: false`**.
- **`send_evaluation_email`**: **`ConnectionError`**, **`Timeout`**, **`HTTPError`** tras **`raise_for_status`** → JSON **`error`**; destinatario detectado en el **cuerpo** si **`REPORT_TO_EMAIL`** vacío; **`log_task_start`** lanza → **`except Exception`**.

---

### Tanda 25

- **`_fetch_url_with_retries`**: **`max_retries=0`** → **`RequestException`** (“Máximo número de reintentos…”).
- **`send_evaluation_email`**: **`re.search`** lanza en el primer bloque; segundo bloque con **226–228** (email detectado en `body`); **`re.search`** solo en el segundo bloque (fallo o fallback); pruebas previas de **`ConnectionError`/`Timeout`/`HTTPError`** y **fallback** flocklab.
- **`get_conversations_by_jd_interview`**: excepción al leer **`clients`** (no tumba el flujo); **`meets_response.data` is None** → **`except`** externo.
- **`get_meet_evaluation_data`**: **`clients`** sin filas → **`REPORT_TO_EMAIL`** fallback; **`jd_interviews` None** → error.
- **`save_meet_evaluation`**: **`full_result`** **dict**; **`conversation_analysis`** con tipos no normalizados; **`meet_evaluations.select`** lanza → **`except`** externo.
- **`get_candidates_data`**: **`limit is None`** → **100**.
- **`save_interview_evaluation`**: argumentos en tiempo de ejecución (dict/list vs JSON), **`json.loads`** genérico en parse, **`candidates`** JSON escalar, ramas **`else`** del parse, **`summary`** sin `kpis` y candidatos vacíos, **`summary`** no dict tras parse (lista JSON + **`candidates_count`**), **`fortalezas_clave`** escalar, niveles de score en **ranking**, cobertura **100%** de **`tools/supabase_tools.py`** en la suite focalizada.

**Referencia cobertura**: con **`pytest tests/test_supabase_tools.py --cov=. --cov-report=term-missing`**, **`tools/supabase_tools.py`** queda **sin líneas sin cubrir** (informe puede omitir el archivo por cobertura completa).

---

### Tanda 26

- **`tools/vector_tools.py`**: tests para **`get_supabase_client`** con **`create_client`** mockeado; errores propagados en **`insert_knowledge_chunk`**, **`generate_embedding`**, **`search_similar_chunks`**, **`delete_knowledge_chunks`**; **`update_knowledge_chunk`** (metadata en update/insert manual, **`except`** externo **196–198**); **`index_*`** y **`index_all_*`** (errores por fila, **`continue`**, **`except`** externos); ramas de **`index_jd_interview`** (lista de **`tech_stack`**), **`index_meet`** (listas y string JD **569**); **`# pragma: no cover`** en **`ImportError`** de OpenAI y en comprobaciones **`isinstance(..., list)`** imposibles tras construir siempre una lista.
- **`utils/logger.py`**: **`log_conversation_analysis`** con dict vacío y **`log_statistics`** con varias claves (suite **`test_utils_logger.py`**).
- **`utils/helpers.py`**: sin cambios de lógica; permanece cubierto por **`test_helpers.py`**.
- **`api.py`**: **`# pragma: no cover`** en **`if __name__ == "__main__"`** (arranque **uvicorn**).

Con **`pytest tests/test_vector_tools.py tests/test_utils_logger.py tests/test_helpers.py --cov=. --cov-report=term-missing`**, **`tools/vector_tools.py`**, **`utils/helpers.py`** y **`utils/logger.py`** pueden aparecer como **omitidos por cobertura completa**.

---

### Tanda 27

- **`api.py` — `_get_candidate_info_impl`**: test **`test_get_candidate_info_impl_reraises_http_exception`** — **`get_supabase_client`** lanza **`HTTPException`** → rama **`except HTTPException: raise`** (**1675–1676**), sin convertir en 500 genérico.
- Con la suite completa (**`pytest tests/ --ignore=tests/integration --cov=api`**), **`api.py`** puede informarse como **100%** (archivo omitido en el reporte si está completo).

---

### Tanda 28

- **`agents.py`**: **`test_create_candidate_matching_agent_recruiter_tools_when_user_and_client`** — rama **266** (`get_candidates_by_recruiter` cuando hay **`user_id`** y **`client_id`**); **`test_create_elevenlabs_prompt_generator_agent_role`** — factory **319+**.
- **`tasks.py`**: **`test_create_single_meeting_minutes_task_context_and_save_tool`** (**879**), **`test_create_elevenlabs_prompt_generation_task_embeds_strings`** (**953**).
- Con **`pytest tests/ --ignore=tests/integration --cov=agents --cov=tasks`**, ambos módulos pueden quedar **100%**.

---

### Tanda 29

- **`filtered_crew.py` / `single_meet_crew.py`**: tests en **`test_crew_smoke.py`** para ramas de resolución del **Tool** (`__wrapped__`, **`_func`**, callable sin **`name`**, sin función accesible, y probe que lanza); stubs con **`*args`** cuando el callable recibe el propio tool como primer argumento.
- **`main.py`**: nuevo **`tests/test_main_smoke.py`** — variables de entorno faltantes; éxito con **`kickoff`** JSON; resultado no JSON (**.txt**); **`KeyboardInterrupt`**; excepción genérica; **`# pragma: no cover`** en **`if __name__ == "__main__"`**.

### Tanda 30

- **`tools/cv_tools.py`** (`tests/test_cv_tools.py`): **`_get_s3_client`** (credenciales faltantes, cliente mockeado); **`_extract_text_from_docx`** / **`_extract_text_from_doc`** con DOCX en memoria; **`extract_candidate_data.func`** (email/tecnologías y rama de error vía **`re.findall`** mockeado).
- **`tools/elevenlabs_tools.py`** (`tests/test_elevenlabs_tools.py`): **`generate_elevenlabs_prompt_from_jd`** con **`Crew`** mockeado (JSON válido, JSON inválido con fallback interno, texto plano, excepción al crear agente); **`create_elevenlabs_agent`** sin **`ELEVENLABS_API_KEY`**; **`update_elevenlabs_agent_prompt`** sin clave y con cliente ElevenLabs mockeado.
- Cobertura dirigida: **`pytest --cov=tools.cv_tools --cov=tools.elevenlabs_tools`** desde el directorio del paquete (nombres de módulo con punto, no rutas con barra).

### Tanda 31

- **`tools/cv_tools.py`**: **`_extract_text_from_pdf`** con **`pdfplumber`** mockeado y rama **`PyPDF2`** cuando plumber no devuelve texto; fallo total cuando todos los métodos (incl. Textract) fallan; **`_extract_text_from_pdf_with_textract`** (archivo mayor a 5MB, **`AccessDeniedException`** vía mensaje); **`download_cv_from_s3.func`** con S3 mockeado (éxito **docx**/**pdf** con extractor mockeado, clave con prefijo **`cvs/`**, **`NoSuchKey`**, archivo vacío, formato no soportado); **`extract_candidate_data`** (**`suggested_profile` Fullstack**, rol **quality assurance** → **`QA`**, normalización LinkedIn).
- **`tools/elevenlabs_tools.py`**: **`create_elevenlabs_agent`** con API key y **`ElevenLabs.conversational_ai.agents.create`** mockeado; ramas de nombre de agente generado con **`null`** (fallback) y prefijo **`nombre` del cliente**.

### Tanda 32

- **`tools/cv_tools.py`**: **`download_cv_from_s3.func`** — **`NoSuchBucket`** en **`get_object`**; **`AccessDenied`** / **`403`**; **`InvalidAccessKeyId`** / **`SignatureDoesNotMatch`**; mensaje con **`NoSuchKey`** (rama de detalle con **`s3://`**); error genérico; **`head_object`** que envuelve excepción en **`Error verificando objeto en S3`**.
- **`tools/cv_tools.py`**: **`extract_candidate_data`** — perfiles **UX/UI**, **DevOps**, **Team Manager** (negocio Excel/Power BI, **recursos humanos**, **tech lead**); **Frontend** solo (CV sin **JavaScript** literal: la heurística de stack usa subcadenas y **javascript** contiene **node**); **Backend** solo.
- **`tools/elevenlabs_tools.py`**: **`create_elevenlabs_agent`** cuando **`agents.create`** lanza — rama **`except`** que devuelve **`None`**.

### Tanda 33

- **`tools/cv_tools.py`**: heurística de perfil por stack — funciones **`_stack_matches_needle_token`** / **`_stack_matches_any_needle`** (igualdad por tecnología, regex por token para evitar **java** en **javascript**, caso **`sql`** con sufijos tipo **PostgreSQL**); lista **`backendTechs`** sin **`node`** suelto (solo **`node.js`** alineado al canonical **Node.js**).
- **`tests/test_cv_tools.py`**: regresión **Frontend** con **JavaScript + TypeScript + React + Next.js** (ya no **Fullstack** espurio); **Fullstack** solo con señal backend real (**Python/Django/PostgreSQL**).
- **`tools/elevenlabs_tools.py`**: **`create_elevenlabs_agent`** con respuesta opaca (**`__slots__`**, sin **`.dict()`** / **`__dict__`**) — rama **`else`** con **`str(response)`** como **`agent_id`**.

---

### Tanda 34

- **`tests/test_stack_matches_needle.py`**: cobertura directa de **`_stack_matches_needle_token`** — **java** vs **javascript**, **`c#`**, **`.net`**, **`next.js`**, **`ci/cd`**, sufijo **`sql`** (**PostgreSQL** / **MySQL** / no **Redis**), **`robot framework`** (multi-palabra), **`node.js`** vs **javascript**.
- **`tools/elevenlabs_tools.py`**: **`update_elevenlabs_agent_prompt`** con respuesta opaca (**`__slots__`**, sin **`.dict()`** / **`__dict__`**) — claves **`agent_id`** + **`result`** (`str(response)`).

---

### Tanda 35

- **`tools/cv_tools.py`** (`tests/test_cv_tools.py`): rama **pdfminer** cuando **pdfplumber** y **PyPDF2** no devuelven texto; **Textract** — éxito con **`Blocks`** tipo **LINE**; mensajes **InvalidParameterException** y **ProvisionedThroughputExceededException**.
- **`matching_crew`**: **`test_create_candidate_matching_crew_with_user_and_client_ids`** — **`create_candidate_matching_crew(user_id=..., client_id=...)`** compone 1 agente / 1 tarea (smoke sin **kickoff**).

---

### Tanda 36

- **`tools/cv_tools.py`** (`tests/test_cv_tools.py`): **Textract** con **`Blocks`** sin **LINE** (solo **WORD**) → error envuelto **Textract OCR**; **`_extract_text_from_pdf`** tras fallo de Textract — bloque de diagnóstico con **`PdfReader`** (éxito) y variante donde el segundo **`PdfReader`** (diagnóstico) lanza (rama **`except Exception:`** silenciosa).
- **`crew.py`**: **`test_create_data_processing_crew_sequential_and_verbose`** — **`Process.sequential`** y **`verbose=True`**.

---

### Tanda 37

- **`tools/cv_tools.py`**: el **`except`** del bloque de diagnóstico tras fallo de Textract pasa de **`except:`** a **`except Exception:`** (compatible con **ruff E722** / estilo); el comportamiento sigue siendo silencioso; la rama queda cubierta por **`test_extract_text_from_pdf_textract_failure_diagnostic_pdfreader_raises`** (segundo **`PdfReader`** falla).

---

### Tanda 38

- **CI** (`.github/workflows/candidate-evaluation-ci.yml`): paso **`Ruff (tools — E722,E9)`** — **`ruff check tools --select E722,E9`** (bare **`except`** y errores de sintaxis), sin exigir alineación global de **`tools/`** con isort/pyupgrade (**I**/**UP**).
- **`tools/supabase_tools.py`**: **`except:`** → **`except Exception:`** al parsear **`fortalezas_clave`** con **`json.loads`** (último **`E722`** en **`tools/`** bajo ese subconjunto).

---

### Tanda 39

- **CI**: el paso de ruff sobre **`tools/`** pasa de **`--select E722,E9`** a **`ruff check tools`** completo (reglas **E/F/I/UP** del **`pyproject.toml`**).
- **Alineación automática**: **`ruff check tools --fix`** en el repo (anotaciones PEP 585/604, imports, f-strings, etc.).
- **Ajustes manuales**: **`tools/cv_tools.py`** — eliminación de **`num_pages`** no usados; **`tools/email_tools.py`** — eliminación de asignación **`conversation_analysis`** no usada en el bloque de listado de candidatos.

---

### Tanda 40

- **`ruff check .`** en la raíz del paquete: **`ruff check . --fix`** aplicado (imports, anotaciones, f-strings, etc.) en **`api.py`**, **`agents/`**, **`filtered_crew.py`**, **`matching_crew.py`**, **`single_meet_crew.py`**, **`scripts/`**, y demás módulos fuera de **`tools/`** y **`tests/`**.
- **Manual**: **`api.py`** — variables de email mockeado con prefijo **`_`**; eliminación de **`start_time`** / **`execution_time`** no usados en **`_create_elevenlabs_agent_impl`**; **`scripts/index_initial_data.py`** — **`_ = get_supabase_client()`**; **`single_meet_crew.py`** — **`_ = func_to_call(...)`** en el probe del tool.
- **CI**: un solo paso **`ruff check .`** (sustituye **`ruff check tests`** + **`ruff check tools`**).

---

### Tanda 41

- **`ruff format .`** aplicado en el repo (25 archivos reformateados en la primera pasada; **`line-length = 120`** heredada del formateador).
- **CI**: paso **`Ruff (format)`** — **`ruff format --check .`** (falla si el código no está formateado; no modifica archivos en el runner).

---

### Tanda 42

- **`[tool.ruff.lint] select`**: **B** (bugbear) y **SIM** (simplify); **`ignore`**: **`B904`** (excepciones re-lanzadas como **HTTPException** / utilidades sin cadena explícita **`from`**).
- **Código**: **`agents.py`** — asignación de herramienta de candidatos con expresión condicional; **`api.py`** — parseo JSON del resultado; **`tools/vector_tools.py`** — listas **`jd_tech`** y texto de alertas; **`tools/cv_tools.py`** — **`NoSuchBucket`** manejado con **`isinstance`** dentro de **`except Exception`** (compatible **B030**); bucles PDF sin índice de **`enumerate`** no usado (**B007**).

---

## Backlog sugerido (tanda 43 y siguientes)

1. Reglas adicionales (**PTH**, **N**, etc.) o quitar **`B904`** del **`ignore`** cuando se acepte **`raise ... from e`** masivo.
2. **Performance / carga**: fuera de alcance salvo job explícito en CI.

---

## CI (GitHub Actions)

Workflow: `.github/workflows/candidate-evaluation-ci.yml`

- **Disparadores**: cambios bajo `agents/candidate-evaluation/**` o el propio workflow.
- **Pasos**: `pip install -r requirements.txt -r requirements-dev.txt` → `ruff check .` → `ruff format --check .` → `pytest --cov=. --cov-report=term-missing`.
- **Directorio de trabajo** del job: `agents/candidate-evaluation`.

---

## Scripts y archivos fuera de `tests/`

- **`test_vector_search.py`** (en la raíz del paquete): script/manual de pruebas de búsqueda vectorial, **no** es parte de la suite pytest; está en `omit` de coverage para no distorsionar el informe.
- Documentación operativa de vectores: `docs/VECTOR_SEARCH_TESTING.md`, `docs/PGVECTOR_SETUP.md` (complementarios a esta guía).

---

## Troubleshooting

| Síntoma | Qué revisar |
|--------|--------------|
| `ModuleNotFoundError` al importar `api` | Instalar `requirements.txt` completos (p. ej. `boto3`). |
| Tests de integración no se listan / no corren | Marcador `integration` y `addopts`; usar override indicado arriba. |
| Cobertura muy baja o distinta entre máquinas | Misma versión de deps; recordar que solo se mide código bajo `source`/`omit` del `pyproject`. |
| `TypeError: 'Tool' object is not callable` | Usar `.func` en herramientas CrewAI. |
| `ValidationError` en `Task(agent=...)` | No usar `MagicMock` como agente; usar factory real o instancia `Agent` válida. |
| Fallos por estado global (`matching_runs`, env) | Limpiar en `finally` o usar `monkeypatch`/`setenv` acotado al test. |
| Chatbot test no usa el mock de OpenAI | Parchear el módulo `openai` (`openai.OpenAI`), no solo `api.OpenAI`, porque el import es dentro de `_chatbot_impl`. |

---

## Referencia rápida de comandos

```bash
cd agents/candidate-evaluation
ruff check .
ruff format --check .
pytest
pytest --cov=. --cov-report=term-missing
pytest tests/test_vector_tools.py -k index
```

Tras ampliar tests, conviene volver a ejecutar cobertura en local y revisar `Missing` en el reporte terminal.
