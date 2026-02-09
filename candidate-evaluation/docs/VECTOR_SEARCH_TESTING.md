# Guía de Pruebas: Búsqueda Vectorial

## 📋 Prerequisitos

1. ✅ **pgvector configurado** en Supabase (ejecutar `setup-pgvector.sql`)
2. ✅ **Variables de entorno configuradas:**
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `OPENAI_API_KEY`
3. ✅ **Dependencias instaladas:**
   ```bash
   pip install openai supabase python-dotenv
   ```

---

## 🚀 Cómo Probar

### Opción 1: Script de Prueba Completo

Ejecuta el script de prueba que prueba todas las funciones:

```bash
cd agents/candidate-evaluation
python test_vector_search.py
```

El script ejecutará:
1. ✅ Generar embedding
2. ✅ Insertar chunk de prueba
3. ✅ Buscar chunks similares
4. ✅ Indexar candidato individual
5. ✅ Indexar JD Interview individual
6. ✅ Indexar todos los candidatos (opcional, limitado a 5)
7. ✅ Indexar todas las JD Interviews (opcional)
8. ✅ Búsqueda después de indexar
9. ✅ Limpieza de datos de prueba

### Opción 2: Pruebas Individuales desde Python

Abre un shell de Python:

```bash
cd agents/candidate-evaluation
python
```

Luego ejecuta:

```python
from tools.vector_tools import (
    generate_embedding,
    search_similar_chunks,
    index_candidate,
    index_all_candidates
)

# 1. Probar generación de embedding
embedding = generate_embedding("Candidato con React y TypeScript")
print(f"Embedding generado: {len(embedding)} dimensiones")

# 2. Indexar un candidato
from tools.supabase_tools import get_candidates_data
import json

candidates = json.loads(get_candidates_data(limit=1))
if candidates:
    chunk_id = index_candidate(candidates[0])
    print(f"Candidato indexado: {chunk_id}")

# 3. Buscar candidatos similares
results = search_similar_chunks(
    query_text="¿Qué candidatos tienen React?",
    match_threshold=0.6,
    match_count=5,
    entity_type_filter='candidate'
)

for result in results:
    print(f"Similitud: {result['similarity']:.3f}")
    print(f"Contenido: {result['content'][:100]}...")
    print()
```

---

## 📝 Ejemplos de Pruebas

### Test 1: Generar Embedding

```python
from tools.vector_tools import generate_embedding

text = "Candidato con React y TypeScript"
embedding = generate_embedding(text)
print(f"Dimensiones: {len(embedding)}")  # Debe ser 1536
```

**Resultado esperado:**
```
✅ Embedding generado exitosamente
   Dimensiones: 1536
```

### Test 2: Indexar Candidato

```python
from tools.vector_tools import index_candidate
from tools.supabase_tools import get_candidates_data
import json

# Obtener un candidato
candidates = json.loads(get_candidates_data(limit=1))
if candidates:
    chunk_id = index_candidate(candidates[0])
    print(f"Chunk ID: {chunk_id}")
```

**Resultado esperado:**
```
✅ Candidato indexado exitosamente
   Chunk ID: uuid-del-chunk
```

### Test 3: Buscar Chunks Similares

```python
from tools.vector_tools import search_similar_chunks

results = search_similar_chunks(
    query_text="¿Qué candidatos tienen React?",
    match_threshold=0.6,
    match_count=5,
    entity_type_filter='candidate'
)

for result in results:
    print(f"Similitud: {result['similarity']:.3f}")
    print(f"Contenido: {result['content']}")
```

**Resultado esperado:**
```
✅ Búsqueda completada
   Resultados encontrados: X
   [Lista de chunks similares con sus similitudes]
```

### Test 4: Indexar Todos los Candidatos

```python
from tools.vector_tools import index_all_candidates

count = index_all_candidates(limit=10)  # Indexar solo 10 para prueba
print(f"Candidatos indexados: {count}")
```

**Resultado esperado:**
```
✅ Indexación completada
   Candidatos indexados: 10
```

---

## 🔍 Verificar en Supabase

### Ver chunks indexados

```sql
-- Ver todos los chunks
SELECT 
  id,
  entity_type,
  entity_id,
  LEFT(content, 100) as content_preview,
  created_at
FROM knowledge_chunks
ORDER BY created_at DESC
LIMIT 10;
```

### Ver estadísticas

```sql
-- Estadísticas por tipo de entidad
SELECT 
  entity_type,
  COUNT(*) as total_chunks
FROM knowledge_chunks
GROUP BY entity_type;
```

### Probar búsqueda directamente

```sql
-- Nota: Necesitas un embedding real para probar esto
-- Esto es solo para referencia
SELECT * FROM search_similar_chunks(
  '[0.123, 0.456, ...]'::vector(1536),  -- embedding de prueba
  0.7,
  10,
  'candidate'
);
```

---

## 🐛 Troubleshooting

### Error: "OpenAI no está disponible"

**Causa:** `OPENAI_API_KEY` no está configurado o OpenAI no está instalado.

**Solución:**
```bash
pip install openai
# Y asegúrate de tener OPENAI_API_KEY en tu .env
```

### Error: "SUPABASE_URL y SUPABASE_KEY deben estar configurados"

**Causa:** Variables de entorno no configuradas.

**Solución:**
Verifica que tu `.env` tenga:
```
SUPABASE_URL=tu_url
SUPABASE_KEY=tu_key
```

### Error: "function search_similar_chunks does not exist"

**Causa:** No se ejecutó el script `setup-pgvector.sql`.

**Solución:**
Ejecuta el script SQL completo en Supabase SQL Editor.

### Error: "relation knowledge_chunks does not exist"

**Causa:** La tabla no fue creada.

**Solución:**
Ejecuta el script `setup-pgvector.sql` en Supabase.

### No encuentra resultados en búsqueda

**Posibles causas:**
1. No hay chunks indexados → Indexa algunos datos primero
2. Threshold muy alto → Baja el `match_threshold` a 0.5 o 0.6
3. Embeddings no coinciden → Verifica que uses el mismo modelo

**Solución:**
```python
# Bajar threshold para testing
results = search_similar_chunks(
    query_text="tu pregunta",
    match_threshold=0.5,  # Más permisivo
    match_count=10
)
```

---

## 📊 Verificar que Funciona

### Checklist de Verificación

1. ✅ **Embedding se genera:**
   ```python
   embedding = generate_embedding("test")
   assert len(embedding) == 1536
   ```

2. ✅ **Chunk se inserta:**
   ```python
   chunk_id = insert_knowledge_chunk(...)
   assert chunk_id is not None
   ```

3. ✅ **Búsqueda encuentra resultados:**
   ```python
   results = search_similar_chunks("React", match_threshold=0.5)
   assert len(results) > 0
   ```

4. ✅ **Candidatos se indexan:**
   ```python
   count = index_all_candidates(limit=1)
   assert count > 0
   ```

---

## 🎯 Próximos Pasos Después de Probar

Una vez que las pruebas pasen:

1. ✅ **Indexar datos iniciales:**
   ```python
   # Indexar todos los candidatos
   index_all_candidates()
   
   # Indexar todas las JD Interviews
   index_all_jd_interviews()
   ```

2. ✅ **Integrar en el chatbot:**
   - Usar `search_similar_chunks` en el endpoint del chatbot
   - Combinar resultados con SQL queries
   - Generar respuestas con contexto

3. ✅ **Indexación incremental:**
   - Indexar cuando se crea un candidato
   - Actualizar cuando se modifica
   - Eliminar cuando se borra

---

## 💡 Tips

- **Threshold recomendado:** 0.7 para producción, 0.5-0.6 para testing
- **Match count:** 10-15 chunks es suficiente para contexto
- **Indexar incrementalmente:** Mejor que indexar todo de una vez
- **Verificar embeddings:** Asegúrate de usar el mismo modelo siempre

---

## 📚 Referencias

- Ver `PGVECTOR_SETUP.md` para configuración
- Ver `vector_tools.py` para código fuente
- Ver `test_vector_search.py` para ejemplos completos
