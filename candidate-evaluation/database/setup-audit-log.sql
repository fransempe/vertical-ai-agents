-- =====================================================
-- Script de Configuracion de Audit Log para candidate-evaluation
-- =====================================================
-- Ejecutar este script completo en el SQL Editor de Supabase
-- =====================================================

-- =====================================================
-- Paso 1: Habilitar extension para UUIDs
-- =====================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =====================================================
-- Paso 2: Crear tabla audit_events
-- =====================================================

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  event_type VARCHAR(30) NOT NULL DEFAULT 'audit',
  severity VARCHAR(20) NOT NULL DEFAULT 'info',
  actor_type VARCHAR(50) NOT NULL DEFAULT 'system',
  actor_id TEXT,
  source VARCHAR(100) NOT NULL DEFAULT 'candidate-evaluation',
  action VARCHAR(120) NOT NULL,
  resource_type VARCHAR(80),
  resource_id TEXT,
  status VARCHAR(30) NOT NULL,
  request_id TEXT,
  correlation_id TEXT,
  before_state JSONB,
  after_state JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_message TEXT,
  error_stack TEXT,
  CONSTRAINT audit_events_event_type_check
    CHECK (event_type IN ('audit', 'error')),
  CONSTRAINT audit_events_severity_check
    CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical')),
  CONSTRAINT audit_events_status_check
    CHECK (status IN ('started', 'success', 'failed', 'skipped'))
);

-- Comentarios para documentacion
COMMENT ON TABLE audit_events IS 'Registro append-only de auditoria de acciones de negocio y errores relevantes del servicio candidate-evaluation';
COMMENT ON COLUMN audit_events.event_type IS 'audit para movimientos funcionales, error para fallas tecnicas relevantes';
COMMENT ON COLUMN audit_events.actor_type IS 'Tipo de actor: system, user, admin, service, integration';
COMMENT ON COLUMN audit_events.actor_id IS 'Identificador del actor que ejecuto la accion';
COMMENT ON COLUMN audit_events.source IS 'Origen del evento: API, worker, bot, integracion, etc.';
COMMENT ON COLUMN audit_events.action IS 'Accion normalizada: candidate_evaluation_started, candidate_evaluation_completed, etc.';
COMMENT ON COLUMN audit_events.resource_type IS 'Tipo de entidad afectada: meet, candidate, jd_interview, meet_evaluation';
COMMENT ON COLUMN audit_events.resource_id IS 'ID de la entidad afectada como texto para soportar UUIDs y IDs externos';
COMMENT ON COLUMN audit_events.before_state IS 'Estado previo de la entidad cuando aplica';
COMMENT ON COLUMN audit_events.after_state IS 'Estado posterior de la entidad cuando aplica';
COMMENT ON COLUMN audit_events.metadata IS 'Contexto adicional estructurado; no guardar secretos ni datos sensibles innecesarios';

-- =====================================================
-- Paso 3: Crear indices
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_audit_events_created_at
ON audit_events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_actor
ON audit_events(actor_type, actor_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_action
ON audit_events(action);

CREATE INDEX IF NOT EXISTS idx_audit_events_resource
ON audit_events(resource_type, resource_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_status
ON audit_events(status);

CREATE INDEX IF NOT EXISTS idx_audit_events_request_id
ON audit_events(request_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_metadata
ON audit_events USING GIN(metadata);


-- =====================================================
-- Paso 4: Verificacion
-- =====================================================

SELECT
  table_name,
  column_name,
  data_type
FROM information_schema.columns
WHERE table_name = 'audit_events'
ORDER BY ordinal_position;

SELECT
  indexname,
  indexdef
FROM pg_indexes
WHERE tablename = 'audit_events';

-- =====================================================
-- Paso 5: Ejemplo de uso
-- =====================================================  

/*
INSERT INTO audit_events (
  actor_type,
  actor_id,
  source,
  action,
  resource_type,
  resource_id,
  status,
  metadata
) VALUES (
  'system',
  'automatic-evaluation',
  'candidate-evaluation-api',
  'candidate_evaluation_completed',
  'meet',
  '550e8400-e29b-41d4-a716-446655440000',
  'success',
  '{"score": 82, "result": "recommended"}'::jsonb
);
*/

-- =====================================================
-- FIN DEL SCRIPT
-- =====================================================
-- Proximos pasos:
-- 1. Verificar que la tabla e indices se crearon correctamente
-- 2. Configurar AUDIT_LOG_ENABLED=true en el servicio
-- 3. Confirmar que SUPABASE_URL y SUPABASE_KEY apuntan al proyecto correcto
-- 4. Exponer la tabla o una API de lectura desde el backoffice
-- =====================================================
