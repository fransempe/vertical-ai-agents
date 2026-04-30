# Setup — `candidate-evaluation`

Guía para preparar el entorno local y ejecutar el paquete `agents/candidate-evaluation`: API FastAPI, crews CrewAI, integración con Supabase y OpenAI.

Para pruebas automatizadas y CI, ver [`TESTING.md`](TESTING.md). Para pgvector y búsqueda vectorial en Supabase, ver [`PGVECTOR_SETUP.md`](PGVECTOR_SETUP.md). Para auditoría funcional en Supabase, ver [`AUDIT_LOG.md`](AUDIT_LOG.md). Para **procesos de negocio** implementados en el servicio (matching candidatos–JD, etc.), ver [`PROCESSES.md`](PROCESSES.md).

---

## Requisitos

| Requisito | Detalle |
|-----------|---------|
| Python | **3.11 o superior** (`pyproject.toml`: `requires-python = ">=3.11"`; en CI suele usarse 3.12) |
| Red | Acceso a Supabase, OpenAI y (según flujo) AWS, ElevenLabs, servicio de email |

---

## 1. Ubicación en el repositorio

El código vive bajo el monorepo `agents`, en la carpeta:

`agents/candidate-evaluation/`

Todos los comandos de esta guía asumen como directorio de trabajo esa ruta.

```bash
cd agents/candidate-evaluation
```

---

## 2. Entorno virtual

```bash
python -m venv .venv
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

---

## 3. Dependencias

Solo runtime:

```bash
pip install -r requirements.txt
```

Desarrollo y tests (pytest, ruff, cobertura):

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Las versiones están fijadas en `requirements.txt`; el proyecto declara metadatos en `pyproject.toml` (pytest, ruff, cobertura).

---

## 4. Variables de entorno

El código usa `python-dotenv` en varios puntos (por ejemplo `agents.py`, `scripts/index_initial_data.py`). Coloca un archivo **`.env`** en la raíz del paquete (`candidate-evaluation/`) **o** exporta las variables en el shell. Al ejecutar scripts, el directorio de trabajo debe permitir que `load_dotenv()` resuelva el `.env` (por defecto, cwd).

### 4.1 Mínimo para el flujo principal por consola

`main.py` exige:

| Variable | Uso |
|----------|-----|
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_KEY` | Clave (service role o anon según tu política) |
| `OPENAI_API_KEY` | Modelos OpenAI (CrewAI / LangChain) |

### 4.2 API FastAPI (`api.py`)

Varios endpoints validan subconjuntos distintos al arrancar la petición:

- Rutas que leen CV desde S3 suelen requerir: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `OPENAI_API_KEY`.
- Muchas rutas de negocio requieren: `SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`.
- Rutas de ElevenLabs requieren: `SUPABASE_URL`, `SUPABASE_KEY`, `ELEVENLABS_API_KEY`. Opcionalmente, `ELEVENLABS_VOICE_ID` define la voz usada al crear agentes; si no se configura, se usa Melanie.

Configura todo lo que vayas a usar en local; si un endpoint pide variables que no están definidas, responderá con error de configuración.

### 4.3 Otras variables usadas en el código

| Variable | Rol |
|----------|-----|
| `AWS_BUCKET_NAME` | Bucket de CVs (descarga en `tools/cv_tools.py`) |
| `S3_REGION` | Región del bucket (si no está, se usa `AWS_REGION`, por defecto `us-east-1`) |
| `AWS_REGION` | Región AWS para S3/Textract si no definís `S3_REGION` |
| `AWS_S3_URL` | URLs o prefijos de bucket para CV (`cv_agent.py`, opcional) |
| `EMAIL_API_URL` | URL del servicio de envío de email (por defecto en código suele apuntar a `http://127.0.0.1:8004/send-simple-email` donde aplique) |
| `REPORT_TO_EMAIL` | Destino de reportes cuando el flujo lo usa |
| `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SCOPE`, `GRAPH_BASE`, `OUTLOOK_USER_ID` | Microsoft Graph / Outlook (`tools/email_tools.py`) |
| `CANDIDATE_EVAL_INTEGRATION_BASE_URL`, `CANDIDATE_EVAL_INTEGRATION_BEARER_TOKEN`, `CANDIDATE_EVAL_INTEGRATION_POST_SMOKE`, `CANDIDATE_EVAL_INTEGRATION_CHATBOT_LIVE` | Solo tests de integración (`tests/integration/`) |
| `AUDIT_LOG_ENABLED` | Si vale `true`, `1`, `yes` u `on`, el servicio intenta insertar eventos en `audit_events` para auditoría funcional. Requiere ejecutar antes `database/setup-audit-log.sql`. |
| `RAILWAY_RUN_MODE` | Modo del entrypoint `railway_start.py`. Por defecto `api`; usar `worker-cron` en el service cron de Railway. |
| `EVALUATION_JOBS_CRON_LIMIT` | Cantidad máxima de jobs a procesar por ejecución cron. Por defecto `3`. |
| `EVALUATION_JOBS_WORKER_ID` | Identificador del worker usado al reclamar jobs. Por defecto `railway-cron`. |

Para el worker async de evaluaciones de entrevistas, `SUPABASE_URL` y `SUPABASE_KEY` deben apuntar al mismo proyecto donde el backoffice creó `evaluation_jobs` con `hr-backoffice/database/evaluation-jobs.sql`.

No commitees secretos: mantén `.env` fuera del control de versiones (debe estar en `.gitignore`).

---

## 5. Cómo ejecutar

### 5.1 Proceso batch de evaluación (Crew)

Ejecuta el pipeline completo descrito en `main.py` (logs bajo `logs/`, resultados en JSON/TXT con timestamp):

```bash
python main.py
```

### 5.2 API HTTP

El módulo `api.py` expone la app FastAPI. En el propio archivo se usa uvicorn en `0.0.0.0:8000`.

```bash
python api.py
```

Equivalente explícito:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Para desarrollo con recarga automática:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Comprobación rápida sin autenticación extra (según despliegue):

```bash
curl -s http://127.0.0.1:8000/status
```

Endpoints relevantes incluyen entre otros: `POST /read-cv`, `POST /match-candidates`, `POST /evaluate-meet`, `POST /evaluation-jobs/process`, `POST /evaluation-jobs/{job_id}/retry`, `POST /chatbot`, `GET /get-candidate-info/{candidate_id}` (ver `api.py`).

### 5.2.1 Worker async de evaluaciones

Para procesar jobs encolados por el backoffice:

```bash
curl -X POST http://127.0.0.1:8000/evaluation-jobs/process \
  -H "Content-Type: application/json" \
  -d '{"limit": 1, "source": "local"}'
```

En producción conviene configurar un cron/worker periódico que llame ese endpoint, además del “kick” que hace el backoffice al encolar. El flujo completo está documentado en [`PROCESSES.md`](PROCESSES.md#2-evaluación-async-de-entrevistas).

### 5.2.2 Railway API y cron

Railway usa el start command definido en `railway.json`:

```bash
python railway_start.py
```

Ese entrypoint decide qué proceso ejecutar según `RAILWAY_RUN_MODE`:

| Service | Variables | Proceso |
|---------|-----------|---------|
| API normal | sin `RAILWAY_RUN_MODE` o `RAILWAY_RUN_MODE=api` | Levanta `uvicorn api:app --host 0.0.0.0 --port $PORT` |
| Cron worker | `RAILWAY_RUN_MODE=worker-cron` | Ejecuta `process_evaluation_jobs(...)`, imprime el resultado y termina |

Config recomendada para el **segundo service** de Railway que corre como cron:

```env
RAILWAY_RUN_MODE=worker-cron
EVALUATION_JOBS_CRON_LIMIT=3
EVALUATION_JOBS_WORKER_ID=railway-cron
SUPABASE_URL=...
SUPABASE_KEY=...
OPENAI_API_KEY=...
```

Cron schedule recomendado:

```cron
*/5 * * * *
```

Si el cron ejecuta pero no cambia ningún estado en `evaluation_jobs`, revisar los logs. Una ejecución saludable imprime algo con esta forma:

```json
{"status":"ok","worker_id":"railway-cron","claimed":1,"processed":[...]}
```

Si `claimed` es `0`, el cron corrió pero no encontró jobs elegibles (`pending` o `failed`, `next_run_at <= now()`, `attempts < max_attempts`). Ver el troubleshooting en [`PROCESSES.md`](PROCESSES.md#2-evaluación-async-de-entrevistas).

### 5.3 Indexación inicial para búsqueda vectorial

Si usas la knowledge base vectorial en Supabase:

```bash
python scripts/index_initial_data.py
```

Requisitos: Supabase configurado, embeddings/OpenAI según `tools/vector_tools.py`, y esquema alineado con [`PGVECTOR_SETUP.md`](PGVECTOR_SETUP.md).

---

## 6. Tests y calidad

Desde la raíz del paquete:

```bash
pytest
ruff check tests
```

Detalle de marcadores, integración y CI: [`TESTING.md`](TESTING.md).

---

## 7. Documentación relacionada

| Documento | Contenido |
|-----------|-----------|
| [`TESTING.md`](TESTING.md) | Pytest, cobertura, integración |
| [`PGVECTOR_SETUP.md`](PGVECTOR_SETUP.md) | Extensión `vector`, tablas, índices |
| [`AUDIT_LOG.md`](AUDIT_LOG.md) | Tabla `audit_events`, activación y consumo desde backoffice |
| [`VECTOR_SEARCH_TESTING.md`](VECTOR_SEARCH_TESTING.md) | Pruebas de búsqueda vectorial |

---

## 8. Problemas frecuentes

- **“Variables de entorno faltantes”** al ejecutar `main.py` o al llamar un endpoint: revisa la sección 4 y que el `.env` esté en `candidate-evaluation/` o que las variables estén exportadas en la sesión actual.
- **Puerto 8000 ocupado**: cambia el puerto en el comando uvicorn o libera el proceso que lo usa.
- **Dependencias o versiones de Python**: usa 3.11+ y reinstala con `pip install -r requirements.txt` en un venv limpio.
