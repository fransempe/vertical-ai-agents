# Guía: Implementación de pgvector en candidate-evaluation

## 📋 Resumen

Esta guía explica cómo configurar pgvector en Supabase para el proyecto `agents/candidate-evaluation`, permitiendo búsquedas vectoriales sobre candidatos, entrevistas y datos del sistema.

---

## 🎯 Objetivo

Configurar pgvector para que el chatbot pueda:
- Buscar candidatos por similitud semántica
- Encontrar búsquedas (JD) relacionadas
- Responder preguntas sobre el sistema usando búsqueda vectorial

---

## 📊 Estructura de Datos Actual

El proyecto `candidate-evaluation` trabaja con:
- **Candidates**: tech_stack, observations (JSONB)
- **jd_interviews**: job_description, tech_stack
- **Meets**: relaciones candidate ↔ jd_interview
- **Conversations**: conversation_data (JSONB)

---

## 🗄️ Configuración en Supabase (SQL)

### Paso 1: Habilitar pgvector

Ejecutar en el **SQL Editor de Supabase**:

```sql
-- Habilitar la extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verificar instalación
SELECT extname, extversion 
FROM pg_extension 
WHERE extname = 'vector';
```

### Paso 2: Crear Tabla de Knowledge Chunks

```sql
-- Tabla para almacenar chunks indexados con embeddings
CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  embedding vector(1536), -- OpenAI text-embedding-3-small
  entity_type VARCHAR(50) NOT NULL, 
  -- Valores: 'candidate', 'jd_interview', 'documentation', 'meet', 'conversation'
  entity_id UUID, -- ID de la entidad en su tabla original
  metadata JSONB, -- Info adicional: tech_stack, status, etc.
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_entity_type 
ON knowledge_chunks(entity_type);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_entity_id 
ON knowledge_chunks(entity_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_metadata 
ON knowledge_chunks USING GIN(metadata);

-- Índice vectorial para búsqueda por similitud (CRÍTICO)
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding 
ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Paso 3: Función de Búsqueda Vectorial

```sql
-- Función para buscar chunks similares
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
```

### Paso 4: Función para Insertar Chunks

```sql
-- Función helper para insertar chunks desde Python
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
```

### Paso 5: Función para Actualizar Chunks

```sql
-- Función para actualizar un chunk existente
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
```

### Paso 6: Función para Eliminar Chunks

```sql
-- Función para eliminar chunks de una entidad
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
```

### Paso 7: Trigger para updated_at

```sql
-- Trigger para actualizar updated_at automáticamente
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
```

---

## 📝 Estructura de Chunks por Entidad

### Chunk para Candidate

**Formato del content:**
```
"Candidato {name} ({email}) con tech_stack: {tech_stack}. 
Experiencia laboral: {work_experience_summary}. 
Rubros: {industries_summary}. 
Idiomas: {languages_summary}. 
Certificaciones: {certifications_summary}."
```

**Ejemplo:**
```
"Candidato Juan Pérez (juan@email.com) con tech_stack: React, TypeScript, Node.js. 
Experiencia laboral: Desarrollador Senior en TechCorp (2020-2024, 48 meses), trabajó con React y TypeScript. 
Rubros: Tecnología (48 meses), Fintech (12 meses). 
Idiomas: Español (nativo), Inglés (avanzado). 
Certificaciones: AWS Solutions Architect (2023)."
```

**Metadata:**
```json
{
  "candidate_id": "uuid",
  "tech_stack": ["React", "TypeScript", "Node.js"],
  "industries": ["Tecnología", "Fintech"],
  "languages": ["Español", "Inglés"],
  "has_certifications": true,
  "created_at": "2024-01-01"
}
```

### Chunk para JD Interview

**Formato del content:**
```
"Búsqueda activa: {interview_name}. 
Requiere tecnologías: {tech_stack}. 
Descripción: {job_description_summary}. 
Agente asociado: {agent_id}. 
Estado: {status}."
```

**Ejemplo:**
```
"Búsqueda activa: Desarrollador React Senior. 
Requiere tecnologías: React, TypeScript, Node.js, PostgreSQL. 
Descripción: Buscamos desarrollador senior con experiencia en React y TypeScript para trabajar en proyectos de fintech. 
Agente asociado: agent-react-senior-v1. 
Estado: active."
```

**Metadata:**
```json
{
  "jd_interview_id": "uuid",
  "tech_stack": ["React", "TypeScript", "Node.js", "PostgreSQL"],
  "status": "active",
  "agent_id": "agent-react-senior-v1",
  "client_id": "uuid"
}
```

### Chunk para Documentación

**Formato del content:**
```
"{título}: {descripción_detallada}"
```

**Ejemplo:**
```
"Matching de Candidatos: El matching funciona comparando el tech_stack de los candidatos (array) con el tech_stack de las búsquedas activas (string separado por comas). 
También analiza las observations del CV incluyendo experiencia laboral, rubros, idiomas y certificaciones. 
El score final combina tech_stack (60%) y observations (40%)."
```

**Metadata:**
```json
{
  "doc_type": "system_documentation",
  "category": "matching",
  "version": "1.0"
}
```

---

## 🔄 Flujo de Indexación

### Indexación Inicial (Batch)

1. **Extraer todos los datos de BD:**
   - Candidates con tech_stack y observations
   - JdInterviews activas
   - Documentación del sistema

2. **Crear chunks:**
   - Formatear datos como texto descriptivo
   - Generar embeddings (OpenAI API)

3. **Insertar en knowledge_chunks:**
   - Usar función `insert_knowledge_chunk` o INSERT directo

### Indexación Incremental (Real-time)

**Cuando se crea/actualiza:**
- **Candidate creado** → Indexar nuevo chunk
- **Candidate actualizado** → Actualizar chunk existente
- **JD Interview creada** → Indexar nuevo chunk
- **JD Interview actualizada** → Actualizar chunk existente

**Estrategia:**
- Webhook desde Supabase → Endpoint Python
- O polling periódico desde Python
- O trigger en Python después de operaciones CRUD

---

## 🔍 Cómo se Usaría desde Python (Conceptual)

### 1. Generar Embedding

```python
# Conceptual - no implementado aún
import openai

def generate_embedding(text: str) -> list:
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
```

### 2. Insertar Chunk

```python
# Conceptual - usando función SQL
supabase.rpc('insert_knowledge_chunk', {
    'p_content': 'Candidato Juan Pérez...',
    'p_embedding': embedding,  # array de 1536 floats
    'p_entity_type': 'candidate',
    'p_entity_id': 'uuid-candidate',
    'p_metadata': {'tech_stack': ['React', 'TypeScript']}
})
```

### 3. Buscar Chunks Similares

```python
# Conceptual - buscar chunks similares
query_embedding = generate_embedding("¿Qué candidatos tienen React?")

results = supabase.rpc('search_similar_chunks', {
    'query_embedding': query_embedding,
    'match_threshold': 0.7,
    'match_count': 10,
    'entity_type_filter': 'candidate'
})
```

---

## 📊 Ejemplos de Queries SQL Directas

### Buscar candidatos similares a una descripción

```sql
-- 1. Generar embedding de la pregunta (desde Python)
-- embedding = [0.123, 0.456, ...] (1536 valores)

-- 2. Buscar chunks de candidatos similares
SELECT 
  content,
  entity_id,
  metadata,
  1 - (embedding <=> '[embedding_array]'::vector) as similarity
FROM knowledge_chunks
WHERE entity_type = 'candidate'
  AND 1 - (embedding <=> '[embedding_array]'::vector) > 0.7
ORDER BY embedding <=> '[embedding_array]'::vector
LIMIT 10;
```

### Buscar búsquedas (JD) relacionadas

```sql
SELECT 
  content,
  entity_id,
  metadata,
  1 - (embedding <=> '[embedding_array]'::vector) as similarity
FROM knowledge_chunks
WHERE entity_type = 'jd_interview'
  AND 1 - (embedding <=> '[embedding_array]'::vector) > 0.7
ORDER BY embedding <=> '[embedding_array]'::vector
LIMIT 5;
```

### Buscar documentación relevante

```sql
SELECT 
  content,
  metadata,
  1 - (embedding <=> '[embedding_array]'::vector) as similarity
FROM knowledge_chunks
WHERE entity_type = 'documentation'
  AND 1 - (embedding <=> '[embedding_array]'::vector) > 0.6
ORDER BY embedding <=> '[embedding_array]'::vector
LIMIT 5;
```

---

## ✅ Checklist de Implementación

### Configuración SQL (Supabase)
- [ ] Habilitar extensión `vector`
- [ ] Crear tabla `knowledge_chunks`
- [ ] Crear índices (incluido vectorial)
- [ ] Crear función `search_similar_chunks`
- [ ] Crear función `insert_knowledge_chunk`
- [ ] Crear función `update_knowledge_chunk`
- [ ] Crear función `delete_knowledge_chunks`
- [ ] Crear trigger para `updated_at`
- [ ] Verificar que todo funciona

### Próximos Pasos (Cuando implementes código)
- [ ] Agregar función Python para generar embeddings
- [ ] Agregar función Python para indexar candidates
- [ ] Agregar función Python para indexar jd_interviews
- [ ] Agregar función Python para buscar chunks similares
- [ ] Implementar indexación inicial (batch)
- [ ] Implementar indexación incremental (real-time)

---

## 🎯 Casos de Uso Específicos

### Caso 1: Buscar Candidatos por Descripción
**Pregunta:** "Necesito un desarrollador con React y experiencia en fintech"

**Proceso:**
1. Generar embedding de la pregunta
2. Buscar chunks de tipo 'candidate' similares
3. Filtrar por metadata (industries: fintech)
4. Retornar candidatos más relevantes

### Caso 2: Encontrar Búsquedas Relacionadas
**Pregunta:** "¿Qué búsquedas hay para desarrolladores frontend?"

**Proceso:**
1. Generar embedding de la pregunta
2. Buscar chunks de tipo 'jd_interview' similares
3. Filtrar por status = 'active'
4. Retornar búsquedas relevantes

### Caso 3: Responder Preguntas Conceptuales
**Pregunta:** "¿Cómo funciona el matching de candidatos?"

**Proceso:**
1. Generar embedding de la pregunta
2. Buscar chunks de tipo 'documentation' similares
3. Retornar documentación más relevante
4. Usar como contexto para LLM

---

## 📝 Notas Importantes

### Dimensiones del Embedding
- **OpenAI text-embedding-3-small**: 1536 dimensiones ✅ (recomendado)
- **OpenAI text-embedding-3-large**: 3072 dimensiones
- Ajustar `vector(1536)` según el modelo

### Índice ivfflat
- **lists = 100**: Para ~10k-100k chunks
- Ajustar según volumen:
  - < 1k chunks: lists = 10
  - 1k-10k chunks: lists = 50
  - 10k-100k chunks: lists = 100
  - > 100k chunks: lists = 200

### Threshold de Similitud
- **0.7**: Buen balance (recomendado)
- **0.8**: Más estricto, menos resultados
- **0.6**: Más permisivo, más resultados

### Operadores de Distancia
- **`<=>`**: Distancia coseno (recomendado para embeddings)
- **`<->`**: Distancia euclidiana
- **`<#>`**: Producto interno negativo

---

## 🚀 Próximos Pasos

1. ✅ **Configurar pgvector** (este documento)
2. ⏳ **Implementar funciones Python** para embeddings
3. ⏳ **Indexar datos iniciales** (batch job)
4. ⏳ **Integrar búsqueda** en el chatbot
5. ⏳ **Indexación incremental** (real-time)

---

## 📚 Referencias

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Supabase pgvector Guide](https://supabase.com/docs/guides/database/extensions/pgvector)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
