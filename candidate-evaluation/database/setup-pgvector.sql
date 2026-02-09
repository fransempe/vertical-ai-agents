-- =====================================================
-- Script de Configuración de pgvector para candidate-evaluation
-- =====================================================
-- Ejecutar este script completo en el SQL Editor de Supabase
-- =====================================================

-- Paso 1: Habilitar extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verificar instalación
SELECT 
  extname as extension_name, 
  extversion as version
FROM pg_extension 
WHERE extname = 'vector';

-- =====================================================
-- Paso 2: Crear tabla knowledge_chunks
-- =====================================================

CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  embedding vector(1536), -- OpenAI text-embedding-3-small usa 1536 dimensiones
  entity_type VARCHAR(50) NOT NULL, 
  -- Valores posibles: 'candidate', 'jd_interview', 'documentation', 'meet', 'conversation'
  entity_id UUID, -- ID de la entidad en su tabla original
  metadata JSONB, -- Información adicional estructurada
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comentarios para documentación
COMMENT ON TABLE knowledge_chunks IS 'Almacena chunks de información indexados con embeddings para búsqueda vectorial';
COMMENT ON COLUMN knowledge_chunks.content IS 'Texto descriptivo del chunk';
COMMENT ON COLUMN knowledge_chunks.embedding IS 'Vector embedding de 1536 dimensiones (OpenAI text-embedding-3-small)';
COMMENT ON COLUMN knowledge_chunks.entity_type IS 'Tipo de entidad: candidate, jd_interview, documentation, meet, conversation';
COMMENT ON COLUMN knowledge_chunks.entity_id IS 'ID de la entidad relacionada en su tabla original';
COMMENT ON COLUMN knowledge_chunks.metadata IS 'Información adicional en formato JSONB (tech_stack, status, etc.)';

-- =====================================================
-- Paso 3: Crear índices
-- =====================================================

-- Índice para búsqueda por tipo de entidad
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_entity_type 
ON knowledge_chunks(entity_type);

-- Índice para búsqueda por ID de entidad
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_entity_id 
ON knowledge_chunks(entity_id);

-- Índice GIN para búsqueda en metadata JSONB
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_metadata 
ON knowledge_chunks USING GIN(metadata);

-- Índice vectorial para búsqueda por similitud (CRÍTICO)
-- ivfflat es el algoritmo de índice vectorial más rápido para pgvector
-- lists = 100 es un buen valor para ~10k-100k chunks
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding 
ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- =====================================================
-- Paso 4: Función de búsqueda vectorial
-- =====================================================

CREATE OR REPLACE FUNCTION search_similar_chunks(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.7,
  match_count int DEFAULT 10,
  entity_type_filter VARCHAR(50) DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  content TEXT,
  entity_type VARCHAR(50),
  entity_id UUID,
  metadata JSONB,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    kc.id,
    kc.content,
    kc.entity_type,
    kc.entity_id,
    kc.metadata,
    1 - (kc.embedding <=> query_embedding) as similarity
  FROM knowledge_chunks kc
  WHERE 
    (entity_type_filter IS NULL OR kc.entity_type = entity_type_filter)
    AND 1 - (kc.embedding <=> query_embedding) > match_threshold
  ORDER BY kc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_similar_chunks IS 'Busca chunks similares usando distancia coseno. Retorna los más similares según el threshold.';

-- =====================================================
-- Paso 5: Función para insertar chunks
-- =====================================================

CREATE OR REPLACE FUNCTION insert_knowledge_chunk(
  p_content TEXT,
  p_embedding vector(1536),
  p_entity_type VARCHAR(50),
  p_entity_id UUID DEFAULT NULL,
  p_metadata JSONB DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  new_id UUID;
BEGIN
  INSERT INTO knowledge_chunks (
    content,
    embedding,
    entity_type,
    entity_id,
    metadata
  )
  VALUES (
    p_content,
    p_embedding,
    p_entity_type,
    p_entity_id,
    p_metadata
  )
  RETURNING id INTO new_id;
  
  RETURN new_id;
END;
$$;

COMMENT ON FUNCTION insert_knowledge_chunk IS 'Inserta un nuevo chunk en la base de conocimiento. Retorna el ID del chunk creado.';

-- =====================================================
-- Paso 6: Función para actualizar chunks
-- =====================================================

CREATE OR REPLACE FUNCTION update_knowledge_chunk(
  p_entity_id UUID,
  p_entity_type VARCHAR(50),
  p_content TEXT,
  p_embedding vector(1536),
  p_metadata JSONB DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  updated_id UUID;
BEGIN
  UPDATE knowledge_chunks
  SET 
    content = p_content,
    embedding = p_embedding,
    metadata = COALESCE(p_metadata, metadata),
    updated_at = NOW()
  WHERE 
    entity_id = p_entity_id 
    AND entity_type = p_entity_type
  RETURNING id INTO updated_id;
  
  -- Si no existe, crear uno nuevo
  IF updated_id IS NULL THEN
    INSERT INTO knowledge_chunks (
      content,
      embedding,
      entity_type,
      entity_id,
      metadata
    )
    VALUES (
      p_content,
      p_embedding,
      p_entity_type,
      p_entity_id,
      p_metadata
    )
    RETURNING id INTO updated_id;
  END IF;
  
  RETURN updated_id;
END;
$$;

COMMENT ON FUNCTION update_knowledge_chunk IS 'Actualiza un chunk existente o lo crea si no existe. Útil para indexación incremental.';

-- =====================================================
-- Paso 7: Función para eliminar chunks
-- =====================================================

CREATE OR REPLACE FUNCTION delete_knowledge_chunks(
  p_entity_id UUID,
  p_entity_type VARCHAR(50)
)
RETURNS int
LANGUAGE plpgsql
AS $$
DECLARE
  deleted_count int;
BEGIN
  DELETE FROM knowledge_chunks
  WHERE 
    entity_id = p_entity_id 
    AND entity_type = p_entity_type;
  
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$;

COMMENT ON FUNCTION delete_knowledge_chunks IS 'Elimina todos los chunks asociados a una entidad. Retorna el número de chunks eliminados.';

-- =====================================================
-- Paso 8: Trigger para updated_at
-- =====================================================

CREATE OR REPLACE FUNCTION update_knowledge_chunks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_knowledge_chunks_updated_at
  BEFORE UPDATE ON knowledge_chunks
  FOR EACH ROW
  EXECUTE FUNCTION update_knowledge_chunks_updated_at();

-- =====================================================
-- Paso 9: Verificación
-- =====================================================

-- Verificar que la tabla existe
SELECT 
  table_name,
  column_name,
  data_type
FROM information_schema.columns
WHERE table_name = 'knowledge_chunks'
ORDER BY ordinal_position;

-- Verificar que las funciones existen
SELECT 
  routine_name,
  routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name IN (
    'search_similar_chunks',
    'insert_knowledge_chunk',
    'update_knowledge_chunk',
    'delete_knowledge_chunks'
  );

-- Verificar índices
SELECT 
  indexname,
  indexdef
FROM pg_indexes
WHERE tablename = 'knowledge_chunks';

-- =====================================================
-- Paso 10: Ejemplo de uso (comentado - para referencia)
-- =====================================================

-- Ejemplo 1: Insertar un chunk (desde Python)
/*
SELECT insert_knowledge_chunk(
  'Candidato Juan Pérez (juan@email.com) con tech_stack: React, TypeScript...',
  '[0.123, 0.456, ...]'::vector(1536), -- embedding array
  'candidate',
  'uuid-candidate-123',
  '{"tech_stack": ["React", "TypeScript"]}'::jsonb
);
*/

-- Ejemplo 2: Buscar chunks similares (desde Python)
/*
SELECT * FROM search_similar_chunks(
  '[0.123, 0.456, ...]'::vector(1536), -- embedding de la pregunta
  0.7, -- threshold
  10, -- cantidad de resultados
  'candidate' -- filtrar por tipo
);
*/

-- Ejemplo 3: Actualizar un chunk
/*
SELECT update_knowledge_chunk(
  'uuid-candidate-123',
  'candidate',
  'Nuevo contenido actualizado...',
  '[0.123, 0.456, ...]'::vector(1536),
  '{"tech_stack": ["React", "TypeScript", "Node.js"]}'::jsonb
);
*/

-- Ejemplo 4: Eliminar chunks de una entidad
/*
SELECT delete_knowledge_chunks(
  'uuid-candidate-123',
  'candidate'
);
*/

-- =====================================================
-- FIN DEL SCRIPT
-- =====================================================
-- Próximos pasos:
-- 1. Verificar que todo se creó correctamente
-- 2. Implementar funciones Python para generar embeddings
-- 3. Indexar datos iniciales
-- 4. Integrar búsqueda en el chatbot
-- =====================================================
