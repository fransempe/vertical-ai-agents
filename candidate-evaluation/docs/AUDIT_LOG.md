# Audit Log en Supabase

Esta guía describe el registro de auditoría funcional del servicio `candidate-evaluation`. El objetivo es que el backoffice pueda consultar qué procesos automáticos se ejecutaron, sobre qué entidad, con qué resultado y, si fallaron, con qué error.

## Tabla

El script ejecutable está en:

```bash
database/setup-audit-log.sql
```

Debe correrse completo desde el SQL Editor de Supabase. Crea la tabla `audit_events`, índices de consulta y triggers para que la tabla sea append-only.

Campos principales:

| Campo | Uso |
|-------|-----|
| `created_at` | Fecha/hora del evento |
| `event_type` | `audit` o `error` |
| `severity` | `info`, `warning`, `error`, etc. |
| `actor_type` / `actor_id` | Quién ejecutó la acción (`system` / `automatic-evaluation` para evaluaciones automáticas) |
| `source` | Origen del evento (`candidate-evaluation-api`, worker, integración) |
| `action` | Acción normalizada, por ejemplo `candidate_evaluation_started` |
| `resource_type` / `resource_id` | Entidad afectada, por ejemplo `meet` + `meet_id` |
| `status` | `started`, `success`, `failed`, `skipped` |
| `metadata` | Contexto estructurado para filtros y detalle |
| `error_message` / `error_stack` | Información técnica si el evento representa una falla |

## Activación

El código no escribe auditoría por defecto para evitar errores antes de crear la tabla. Después de correr el SQL, activar:

```bash
AUDIT_LOG_ENABLED=true
```

También deben existir las variables habituales de Supabase:

```bash
SUPABASE_URL=...
SUPABASE_KEY=...
```

Usar preferentemente una service role key del backend o una key con permisos explícitos para insertar en `audit_events`.

## Eventos actuales

Cada movimiento genera un solo registro. El resultado final se expresa con `status` y el detalle va dentro de `metadata`.

El endpoint automático `POST /evaluate-meet` registra:

| Acción | Estado | Cuándo ocurre |
|--------|--------|---------------|
| `candidate_evaluation` | `success` | Al finalizar correctamente, incluyendo score, recomendación, `evaluation_id` y si se envió email |
| `candidate_evaluation` | `failed` | Si la evaluación termina con excepción |

El endpoint `POST /read-cv` registra:

| Acción | Estado | Cuándo ocurre |
|--------|--------|---------------|
| `candidate_creation_from_cv` | `success` | Cuando el análisis de CV termina y el candidato fue creado, ya existía o no se pudo determinar el resultado de creación |
| `candidate_creation_from_cv` | `failed` | Si falla la creación del candidato reportada por el crew o si falla el proceso de lectura/análisis del CV |

El endpoint `POST /create-elevenlabs-agent` registra:

| Acción | Estado | Cuándo ocurre |
|--------|--------|---------------|
| `elevenlabs_agent_creation` | `success` | Al crear el agente en ElevenLabs y actualizar `jd_interviews.agent_id` |
| `elevenlabs_agent_creation` | `failed` | Si falla la validación, la creación en ElevenLabs, la actualización en Supabase u otro paso crítico |

El flujo de matching `POST /match-candidates` registra:

| Acción | Estado | Cuándo ocurre |
|--------|--------|---------------|
| `candidate_matching` | `success` | Al finalizar el matching determinístico |
| `candidate_matching` | `failed` | Si falla el encolado, falta configuración o falla el motor de matching |

Ejemplo lógico:

```json
{
  "actor_type": "system",
  "actor_id": "automatic-evaluation",
  "source": "candidate-evaluation-api",
  "action": "candidate_evaluation",
  "resource_type": "meet",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "metadata": {
    "evaluation_id": "audit-eval-1",
    "compatibility_score": 91,
    "is_potential_match": false,
    "email_sent": false
  }
}
```

Ejemplo de creación de candidato desde CV:

```json
{
  "actor_type": "system",
  "actor_id": "cv-analysis",
  "source": "candidate-evaluation-api",
  "action": "candidate_creation_from_cv",
  "resource_type": "cv",
  "resource_id": "folder/cv.pdf",
  "status": "success",
  "metadata": {
    "filename": "folder/cv.pdf",
    "user_id": "user_123",
    "client_id": "client_456",
    "candidate_created": true,
    "candidate_status": "created",
    "candidate_email": "candidate@example.com"
  }
}
```

Ejemplo de creación de agente:

```json
{
  "actor_type": "system",
  "actor_id": "elevenlabs-agent-creator",
  "source": "candidate-evaluation-api",
  "action": "elevenlabs_agent_creation",
  "resource_type": "jd_interview",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "metadata": {
    "agent_id": "agent_123",
    "agent_name": "Agente Senior Python",
    "interview_name": "Senior Python",
    "client_id": "550e8400-e29b-41d4-a716-446655440001"
  }
}
```

Ejemplo de matching:

```json
{
  "actor_type": "system",
  "actor_id": "matching-engine",
  "source": "candidate-evaluation-api",
  "action": "candidate_matching",
  "resource_type": "matching_run",
  "resource_id": "9a2dbb08-9b8a-4249-b621-2f622b8449b1",
  "status": "success",
  "metadata": {
    "user_id": "user_123",
    "client_id": "client_456",
    "execution_time": "0:00:01.234567",
    "total_matches": 8
  }
}
```

## Backoffice

Para una primera vista en backoffice, consultar `audit_events` con filtros por:

- `created_at`
- `event_type`
- `severity`
- `actor_type` / `actor_id`
- `action`
- `resource_type` / `resource_id`
- `status`

Para ver el historial de una entidad concreta:

```sql
SELECT *
FROM audit_events
WHERE resource_type = 'meet'
  AND resource_id = '<meet_id>'
ORDER BY created_at DESC;
```

## Seguridad y retención

- No guardar passwords, tokens ni API keys en `metadata`; el helper enmascara claves sensibles comunes.
- La tabla es append-only: si una acción se revierte, registrar un nuevo evento.
- Si se habilita RLS, validar que el backend pueda insertar y que el backoffice solo pueda leer lo permitido.
- Para alto volumen, definir una política de retención o archivado por fecha.
