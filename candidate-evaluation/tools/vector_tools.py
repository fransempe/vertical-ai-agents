"""
Herramientas para trabajar con embeddings y búsqueda vectorial usando pgvector
"""

import os
import json
from typing import List, Dict, Any, Optional
from supabase import create_client
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.logger import evaluation_logger

# Intentar importar OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    evaluation_logger.log_error("Vector Tools", "OpenAI no está instalado. Instala con: pip install openai")

load_dotenv()

# Inicializar cliente de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Inicializar cliente de OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

def get_supabase_client():
    """Obtiene el cliente de Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Genera un embedding para un texto usando OpenAI
    
    Args:
        text: Texto para generar embedding
        model: Modelo de embedding a usar (default: text-embedding-3-small)
    
    Returns:
        Lista de floats con el embedding (1536 dimensiones para text-embedding-3-small)
    """
    if not OPENAI_AVAILABLE or not openai_client:
        raise ValueError("OpenAI no está disponible. Verifica que OPENAI_API_KEY esté configurado.")
    
    try:
        evaluation_logger.log_task_start("Generar Embedding", f"Generando embedding para texto de {len(text)} caracteres")
        
        response = openai_client.embeddings.create(
            model=model,
            input=text
        )
        
        embedding = response.data[0].embedding
        evaluation_logger.log_task_complete("Generar Embedding", f"Embedding generado: {len(embedding)} dimensiones")
        
        return embedding
    except Exception as e:
        evaluation_logger.log_error("Generar Embedding", f"Error generando embedding: {str(e)}")
        raise

def insert_knowledge_chunk(
    content: str,
    embedding: List[float],
    entity_type: str,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Inserta un chunk en la tabla knowledge_chunks
    
    Args:
        content: Contenido textual del chunk
        embedding: Lista de floats con el embedding (1536 dimensiones)
        entity_type: Tipo de entidad ('candidate', 'jd_interview', 'documentation', etc.)
        entity_id: ID de la entidad relacionada (opcional)
        metadata: Diccionario con metadata adicional (opcional)
    
    Returns:
        ID del chunk insertado
    """
    try:
        evaluation_logger.log_task_start("Insertar Knowledge Chunk", f"Insertando chunk tipo: {entity_type}")
        
        supabase = get_supabase_client()
        
        # Llamar a la función SQL
        result = supabase.rpc(
            'insert_knowledge_chunk',
            {
                'p_content': content,
                'p_embedding': embedding,
                'p_entity_type': entity_type,
                'p_entity_id': entity_id,
                'p_metadata': metadata
            }
        ).execute()
        
        chunk_id = result.data if isinstance(result.data, str) else result.data.get('id') if result.data else None
        
        evaluation_logger.log_task_complete("Insertar Knowledge Chunk", f"Chunk insertado con ID: {chunk_id}")
        return chunk_id
        
    except Exception as e:
        evaluation_logger.log_error("Insertar Knowledge Chunk", f"Error insertando chunk: {str(e)}")
        raise

def update_knowledge_chunk(
    entity_id: str,
    entity_type: str,
    content: str,
    embedding: List[float],
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Actualiza un chunk existente o lo crea si no existe
    
    Args:
        entity_id: ID de la entidad
        entity_type: Tipo de entidad
        content: Nuevo contenido
        embedding: Nuevo embedding
        metadata: Nueva metadata (opcional)
    
    Returns:
        ID del chunk actualizado/creado
    """
    try:
        evaluation_logger.log_task_start("Actualizar Knowledge Chunk", f"Actualizando chunk: {entity_type} - {entity_id}")
        
        supabase = get_supabase_client()
        
        # Intentar usar la función RPC primero
        try:
            result = supabase.rpc(
                'update_knowledge_chunk',
                {
                    'p_entity_id': entity_id,
                    'p_entity_type': entity_type,
                    'p_content': content,
                    'p_embedding': embedding,
                    'p_metadata': metadata
                }
            ).execute()
            
            chunk_id = result.data if isinstance(result.data, str) else (result.data.get('id') if result.data else None)
            
            if chunk_id:
                evaluation_logger.log_task_complete("Actualizar Knowledge Chunk", f"Chunk actualizado con ID: {chunk_id}")
                return chunk_id
        except Exception as rpc_error:
            # Si falla la función RPC, hacer upsert manual
            evaluation_logger.log_task_progress("Actualizar Knowledge Chunk", "Función RPC no disponible, usando upsert manual")
        
        # Upsert manual: buscar si existe
        existing = supabase.table('knowledge_chunks').select('id').eq('entity_id', entity_id).eq('entity_type', entity_type).limit(1).execute()
        
        if existing.data and len(existing.data) > 0:
            # Actualizar existente
            chunk_id = existing.data[0]['id']
            update_data = {
                'content': content,
                'embedding': embedding,
                'updated_at': 'now()'
            }
            if metadata:
                update_data['metadata'] = metadata
            
            supabase.table('knowledge_chunks').update(update_data).eq('id', chunk_id).execute()
            evaluation_logger.log_task_complete("Actualizar Knowledge Chunk", f"Chunk actualizado manualmente con ID: {chunk_id}")
            return chunk_id
        else:
            # Insertar nuevo
            insert_data = {
                'content': content,
                'embedding': embedding,
                'entity_type': entity_type,
                'entity_id': entity_id,
            }
            if metadata:
                insert_data['metadata'] = metadata
            
            result = supabase.table('knowledge_chunks').insert(insert_data).execute()
            chunk_id = result.data[0]['id'] if result.data and len(result.data) > 0 else None
            evaluation_logger.log_task_complete("Actualizar Knowledge Chunk", f"Chunk insertado manualmente con ID: {chunk_id}")
            return chunk_id
        
    except Exception as e:
        evaluation_logger.log_error("Actualizar Knowledge Chunk", f"Error actualizando chunk: {str(e)}")
        raise

def search_similar_chunks(
    query_text: str,
    match_threshold: float = 0.7,
    match_count: int = 10,
    entity_type_filter: Optional[str] = None,
    model: str = "text-embedding-3-small"
) -> List[Dict[str, Any]]:
    """
    Busca chunks similares usando búsqueda vectorial
    
    Args:
        query_text: Texto de la consulta
        match_threshold: Umbral de similitud (0.0-1.0, default: 0.7)
        match_count: Cantidad máxima de resultados (default: 10)
        entity_type_filter: Filtrar por tipo de entidad (opcional)
        model: Modelo de embedding a usar
    
    Returns:
        Lista de chunks similares con sus similitudes
    """
    try:
        evaluation_logger.log_task_start("Buscar Chunks Similares", f"Buscando: '{query_text[:50]}...'")
        
        # Generar embedding de la consulta
        query_embedding = generate_embedding(query_text, model)
        
        # Buscar chunks similares
        supabase = get_supabase_client()
        
        result = supabase.rpc(
            'search_similar_chunks',
            {
                'query_embedding': query_embedding,
                'match_threshold': match_threshold,
                'match_count': match_count,
                'entity_type_filter': entity_type_filter
            }
        ).execute()
        
        chunks = result.data if result.data else []
        
        evaluation_logger.log_task_complete("Buscar Chunks Similares", f"Encontrados {len(chunks)} chunks similares")
        
        return chunks
        
    except Exception as e:
        evaluation_logger.log_error("Buscar Chunks Similares", f"Error buscando chunks: {str(e)}")
        raise

def delete_knowledge_chunks(entity_id: str, entity_type: str) -> int:
    """
    Elimina todos los chunks asociados a una entidad
    
    Args:
        entity_id: ID de la entidad
        entity_type: Tipo de entidad
    
    Returns:
        Número de chunks eliminados
    """
    try:
        evaluation_logger.log_task_start("Eliminar Knowledge Chunks", f"Eliminando chunks: {entity_type} - {entity_id}")
        
        supabase = get_supabase_client()
        
        result = supabase.rpc(
            'delete_knowledge_chunks',
            {
                'p_entity_id': entity_id,
                'p_entity_type': entity_type
            }
        ).execute()
        
        deleted_count = result.data if isinstance(result.data, int) else result.data.get('delete_knowledge_chunks', 0) if result.data else 0
        
        evaluation_logger.log_task_complete("Eliminar Knowledge Chunks", f"Eliminados {deleted_count} chunks")
        return deleted_count
        
    except Exception as e:
        evaluation_logger.log_error("Eliminar Knowledge Chunks", f"Error eliminando chunks: {str(e)}")
        raise

def index_candidate(candidate: Dict[str, Any]) -> str:
    """
    Indexa un candidato en la knowledge base
    
    Args:
        candidate: Diccionario con datos del candidato
    
    Returns:
        ID del chunk creado
    """
    try:
        evaluation_logger.log_task_start("Indexar Candidato", f"Indexando candidato: {candidate.get('name', 'Unknown')}")
        
        # Construir contenido del chunk
        content_parts = [
            f"Candidato {candidate.get('name', 'Unknown')} ({candidate.get('email', 'no-email')})"
        ]
        
        # Tech stack
        if candidate.get('tech_stack'):
            tech_stack_str = ', '.join(candidate['tech_stack']) if isinstance(candidate['tech_stack'], list) else candidate['tech_stack']
            content_parts.append(f"con tech_stack: {tech_stack_str}")
        
        # Observations
        observations = candidate.get('observations')
        if observations:
            if isinstance(observations, str):
                observations = json.loads(observations)
            
            # Experiencia laboral
            if observations.get('work_experience'):
                exp_parts = []
                for exp in observations['work_experience'][:3]:  # Primeras 3 experiencias
                    exp_str = f"{exp.get('position', '')} en {exp.get('company', '')}"
                    if exp.get('period'):
                        exp_str += f" ({exp.get('period')})"
                    exp_parts.append(exp_str)
                if exp_parts:
                    content_parts.append(f"Experiencia laboral: {', '.join(exp_parts)}")
            
            # Rubros
            if observations.get('industries_and_sectors'):
                industries = [ind.get('industry', '') for ind in observations['industries_and_sectors'][:5]]
                if industries:
                    content_parts.append(f"Rubros: {', '.join(industries)}")
            
            # Idiomas
            if observations.get('languages'):
                languages = [f"{lang.get('language', '')} ({lang.get('level', '')})" for lang in observations['languages']]
                if languages:
                    content_parts.append(f"Idiomas: {', '.join(languages)}")
            
            # Certificaciones
            if observations.get('certifications_and_courses'):
                certs = [cert.get('name', '') for cert in observations['certifications_and_courses'][:5]]
                if certs:
                    content_parts.append(f"Certificaciones: {', '.join(certs)}")
        
        content = ". ".join(content_parts) + "."
        
        # Generar embedding
        embedding = generate_embedding(content)
        
        # Metadata
        metadata = {
            'candidate_id': candidate.get('id'),
            'name': candidate.get('name'),
            'email': candidate.get('email'),
            'tech_stack': candidate.get('tech_stack', [])
        }
        
        # Actualizar o insertar chunk (upsert)
        chunk_id = update_knowledge_chunk(
            entity_id=candidate.get('id'),
            entity_type='candidate',
            content=content,
            embedding=embedding,
            metadata=metadata
        )
        
        evaluation_logger.log_task_complete("Indexar Candidato", f"Candidato indexado: {chunk_id}")
        return chunk_id
        
    except Exception as e:
        evaluation_logger.log_error("Indexar Candidato", f"Error indexando candidato: {str(e)}")
        raise

def index_jd_interview(jd_interview: Dict[str, Any]) -> str:
    """
    Indexa una JD Interview en la knowledge base
    
    Args:
        jd_interview: Diccionario con datos de la JD Interview
    
    Returns:
        ID del chunk creado
    """
    try:
        evaluation_logger.log_task_start("Indexar JD Interview", f"Indexando JD: {jd_interview.get('interview_name', 'Unknown')}")
        
        # Construir contenido del chunk
        content_parts = [
            f"Búsqueda activa: {jd_interview.get('interview_name', 'Unknown')}"
        ]
        
        # Tech stack
        tech_stack = jd_interview.get('tech_stack')
        if tech_stack:
            if isinstance(tech_stack, str):
                tech_stack_str = tech_stack
            else:
                tech_stack_str = ', '.join(tech_stack) if isinstance(tech_stack, list) else str(tech_stack)
            content_parts.append(f"Requiere tecnologías: {tech_stack_str}")
        
        # Job description (resumen)
        job_description = jd_interview.get('job_description', '')
        if job_description:
            # Limitar a primeros 200 caracteres
            job_desc_summary = job_description[:200] + "..." if len(job_description) > 200 else job_description
            content_parts.append(f"Descripción: {job_desc_summary}")
        
        # Agent ID
        if jd_interview.get('agent_id'):
            content_parts.append(f"Agente asociado: {jd_interview.get('agent_id')}")
        
        # Status
        status = jd_interview.get('status', 'active')
        content_parts.append(f"Estado: {status}")
        
        content = ". ".join(content_parts) + "."
        
        # Generar embedding
        embedding = generate_embedding(content)
        
        # Metadata
        metadata = {
            'jd_interview_id': jd_interview.get('id'),
            'interview_name': jd_interview.get('interview_name'),
            'tech_stack': tech_stack if isinstance(tech_stack, list) else (tech_stack.split(', ') if isinstance(tech_stack, str) else []),
            'status': status,
            'agent_id': jd_interview.get('agent_id')
        }
        
        # Actualizar o insertar chunk (upsert)
        chunk_id = update_knowledge_chunk(
            entity_id=jd_interview.get('id'),
            entity_type='jd_interview',
            content=content,
            embedding=embedding,
            metadata=metadata
        )
        
        evaluation_logger.log_task_complete("Indexar JD Interview", f"JD Interview indexada: {chunk_id}")
        return chunk_id
        
    except Exception as e:
        evaluation_logger.log_error("Indexar JD Interview", f"Error indexando JD Interview: {str(e)}")
        raise

def index_all_candidates(limit: Optional[int] = None) -> int:
    """
    Indexa todos los candidatos de la BD
    
    Args:
        limit: Límite de candidatos a indexar (None = todos)
    
    Returns:
        Número de candidatos indexados
    """
    try:
        evaluation_logger.log_task_start("Indexar Todos los Candidatos", f"Iniciando indexación masiva")
        
        # Obtener candidatos directamente de Supabase (sin usar tool decorado)
        supabase = get_supabase_client()
        response = supabase.table('candidates').select('*').limit(limit or 1000).execute()
        
        candidates = []
        for row in response.data:
            candidate = {
                "id": row.get('id'),
                "name": row.get('name'),
                "email": row.get('email'),
                "phone": row.get('phone'),
                "cv_url": row.get('cv_url'),
                "tech_stack": row.get('tech_stack'),
                "observations": row.get('observations'),
                "created_at": row.get('created_at')
            }
            candidates.append(candidate)
        
        if not isinstance(candidates, list):
            evaluation_logger.log_error("Indexar Todos los Candidatos", "Error: get_candidates_data no retornó una lista")
            return 0
        
        indexed_count = 0
        for candidate in candidates:
            try:
                index_candidate(candidate)
                indexed_count += 1
            except Exception as e:
                evaluation_logger.log_error("Indexar Todos los Candidatos", f"Error indexando candidato {candidate.get('id')}: {str(e)}")
                continue
        
        evaluation_logger.log_task_complete("Indexar Todos los Candidatos", f"Indexados {indexed_count} candidatos")
        return indexed_count
        
    except Exception as e:
        evaluation_logger.log_error("Indexar Todos los Candidatos", f"Error en indexación masiva: {str(e)}")
        raise

def index_all_jd_interviews() -> int:
    """
    Indexa todas las JD Interviews activas de la BD
    
    Returns:
        Número de JD Interviews indexadas
    """
    try:
        evaluation_logger.log_task_start("Indexar Todas las JD Interviews", "Iniciando indexación masiva")
        
        # Obtener JD Interviews directamente de Supabase (sin usar tool decorado)
        supabase = get_supabase_client()
        response = supabase.table('jd_interviews').select('*').eq('status', 'active').execute()
        
        jd_interviews = []
        for row in response.data:
            interview = {
                "id": row.get('id'),
                "interview_name": row.get('interview_name'),
                "agent_id": row.get('agent_id'),
                "job_description": row.get('job_description'),
                "tech_stack": row.get('tech_stack'),
                "client_id": row.get('client_id'),
                "status": row.get('status'),
                "created_at": row.get('created_at')
            }
            jd_interviews.append(interview)
        
        if not isinstance(jd_interviews, list):
            evaluation_logger.log_error("Indexar Todas las JD Interviews", "Error: get_all_jd_interviews no retornó una lista")
            return 0
        
        indexed_count = 0
        for jd_interview in jd_interviews:
            try:
                index_jd_interview(jd_interview)
                indexed_count += 1
            except Exception as e:
                evaluation_logger.log_error("Indexar Todas las JD Interviews", f"Error indexando JD {jd_interview.get('id')}: {str(e)}")
                continue
        
        evaluation_logger.log_task_complete("Indexar Todas las JD Interviews", f"Indexadas {indexed_count} JD Interviews")
        return indexed_count
        
    except Exception as e:
        evaluation_logger.log_error("Indexar Todas las JD Interviews", f"Error en indexación masiva: {str(e)}")
        raise

def index_meet(meet: Dict[str, Any]) -> str:
    """
    Indexa un registro de meet en la knowledge base

    Args:
        meet: Diccionario con datos del meet y, si están disponibles,
              sus relaciones a candidate y jd_interview

    Returns:
        ID del chunk creado/actualizado
    """
    try:
        evaluation_logger.log_task_start("Indexar Meet", f"Indexando meet: {meet.get('id', 'Unknown')}")

        candidate = meet.get('candidates') or meet.get('candidate') or {}
        jd_interview = meet.get('jd_interviews') or meet.get('jd_interview') or {}

        candidate_name = candidate.get('name', 'Candidato desconocido')
        candidate_email = candidate.get('email', 'sin-email')
        candidate_tech = candidate.get('tech_stack') or []
        if isinstance(candidate_tech, str):
            # En caso de que venga como string separado por comas
            candidate_tech_list = [t.strip() for t in candidate_tech.split(',') if t.strip()]
        else:
            candidate_tech_list = candidate_tech

        jd_name = jd_interview.get('interview_name', 'Búsqueda desconocida')
        jd_tech = jd_interview.get('tech_stack') or []
        if isinstance(jd_tech, str):
            jd_tech_list = [t.strip() for t in jd_tech.split(',') if t.strip()]
        else:
            jd_tech_list = jd_tech

        status = meet.get('status', 'desconocido')
        scheduled_at = meet.get('scheduled_at') or meet.get('created_at')

        # Construir contenido descriptivo
        content_parts = [
            f"Entrevista (meet) para el candidato {candidate_name} ({candidate_email})",
            f"Estado de la entrevista: {status}",
        ]

        if scheduled_at:
            content_parts.append(f"Fecha programada: {scheduled_at}")

        if jd_name:
            content_parts.append(f"Asociada a la búsqueda: {jd_name}")

        if candidate_tech_list:
            content_parts.append(f"Tecnologías del candidato: {', '.join(candidate_tech_list)}")

        if jd_tech_list:
            content_parts.append(f"Tecnologías requeridas por la búsqueda: {', '.join(jd_tech_list)}")

        content = ". ".join(content_parts) + "."

        # Generar embedding
        embedding = generate_embedding(content)

        # Metadata
        metadata: Dict[str, Any] = {
            "meet_id": meet.get("id"),
            "candidate_id": meet.get("candidate_id") or candidate.get("id"),
            "jd_interview_id": meet.get("jd_interviews_id") or jd_interview.get("id"),
            "status": status,
            "scheduled_at": str(scheduled_at) if scheduled_at else None,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "candidate_tech_stack": candidate_tech_list,
            "jd_interview_name": jd_name,
            "jd_tech_stack": jd_tech_list,
        }

        # Actualizar o insertar chunk (upsert)
        chunk_id = update_knowledge_chunk(
            entity_id=meet.get("id"),
            entity_type="meet",
            content=content,
            embedding=embedding,
            metadata=metadata,
        )

        evaluation_logger.log_task_complete("Indexar Meet", f"Meet indexado: {chunk_id}")
        return chunk_id

    except Exception as e:
        evaluation_logger.log_error("Indexar Meet", f"Error indexando meet: {str(e)}")
        raise

def index_all_meets(limit: Optional[int] = None) -> int:
    """
    Indexa todos los meets de la BD

    Args:
        limit: Límite de meets a indexar (None = todos)

    Returns:
        Número de meets indexados
    """
    try:
        evaluation_logger.log_task_start("Indexar Todos los Meets", "Iniciando indexación masiva de meets")

        supabase = get_supabase_client()

        # Cargamos meets con información de candidate y jd_interview si las relaciones están definidas
        # Nota: el nombre de las relaciones ('candidates', 'jd_interviews') debe coincidir con la configuración de Supabase
        select_str = "*, candidates(name,email,tech_stack), jd_interviews(id,interview_name,job_description,tech_stack,client_id)"
        query = supabase.table("meets").select(select_str)
        if limit:
            query = query.limit(limit)
        response = query.execute()

        meets = response.data or []

        indexed_count = 0
        for row in meets:
            try:
                index_meet(row)
                indexed_count += 1
            except Exception as e:
                evaluation_logger.log_error(
                    "Indexar Todos los Meets",
                    f"Error indexando meet {row.get('id')}: {str(e)}",
                )
                continue

        evaluation_logger.log_task_complete(
            "Indexar Todos los Meets",
            f"Indexados {indexed_count} meets",
        )
        return indexed_count

    except Exception as e:
        evaluation_logger.log_error(
            "Indexar Todos los Meets", f"Error en indexación masiva de meets: {str(e)}"
        )
        raise

def index_meet_evaluation(evaluation: Dict[str, Any]) -> str:
    """
    Indexa una evaluación de meet (meet_evaluations) en la knowledge base

    Args:
        evaluation: Fila de la tabla meet_evaluations

    Returns:
        ID del chunk creado/actualizado
    """
    try:
        evaluation_logger.log_task_start(
            "Indexar Meet Evaluation",
            f"Indexando evaluación de meet: {evaluation.get('id', 'Unknown')}",
        )

        meet_id = evaluation.get("meet_id")
        candidate_id = evaluation.get("candidate_id")
        jd_interview_id = evaluation.get("jd_interview_id")

        technical = evaluation.get("technical_assessment") or {}
        completeness = evaluation.get("completeness_summary") or {}
        alerts = evaluation.get("alerts") or []
        match_eval = evaluation.get("match_evaluation") or {}

        # Construir contenido descriptivo
        content_parts = [
            f"Evaluación de entrevista (meet) para el candidato {candidate_id} en la búsqueda {jd_interview_id}.",
        ]

        if technical:
            nivel = technical.get("knowledge_level")
            experiencia = technical.get("practical_experience")
            if nivel:
                content_parts.append(f"Nivel de conocimiento técnico: {nivel}")
            if experiencia:
                content_parts.append(f"Experiencia práctica: {experiencia}")

            preguntas = technical.get("technical_questions") or []
            if preguntas:
                # No incluimos todas las preguntas completas para evitar textos muy largos
                content_parts.append(
                    f"Número de preguntas técnicas evaluadas: {len(preguntas)}"
                )

        if completeness:
            resumen_completo = completeness.get("overall_completeness")
            if resumen_completo:
                content_parts.append(
                    f"Resumen de completitud de la entrevista: {resumen_completo}"
                )

        if alerts:
            alerts_texts = []
            for a in alerts[:5]:
                if isinstance(a, dict):
                    txt = a.get("message") or a.get("description") or str(a)
                else:
                    txt = str(a)
                alerts_texts.append(txt)
            if alerts_texts:
                content_parts.append(
                    "Alertas relevantes detectadas: " + "; ".join(alerts_texts)
                )

        if match_eval:
            score = match_eval.get("score")
            summary = match_eval.get("summary")
            if score is not None:
                content_parts.append(f"Score global de match: {score}")
            if summary:
                content_parts.append(f"Resumen de evaluación de match: {summary}")

        content = ". ".join(content_parts) + "."

        # Generar embedding
        embedding = generate_embedding(content)

        # Metadata
        metadata: Dict[str, Any] = {
            "meet_evaluation_id": evaluation.get("id"),
            "meet_id": meet_id,
            "candidate_id": candidate_id,
            "jd_interview_id": jd_interview_id,
            "has_alerts": bool(alerts),
            "created_at": evaluation.get("created_at"),
            "updated_at": evaluation.get("updated_at"),
        }

        # Actualizar o insertar chunk (upsert)
        chunk_id = update_knowledge_chunk(
            entity_id=evaluation.get("id"),
            entity_type="meet_evaluation",
            content=content,
            embedding=embedding,
            metadata=metadata,
        )

        evaluation_logger.log_task_complete(
            "Indexar Meet Evaluation", f"Meet Evaluation indexada: {chunk_id}"
        )
        return chunk_id

    except Exception as e:
        evaluation_logger.log_error(
            "Indexar Meet Evaluation", f"Error indexando meet_evaluation: {str(e)}"
        )
        raise

def index_all_meet_evaluations(limit: Optional[int] = None) -> int:
    """
    Indexa todas las evaluaciones de meets de la BD

    Args:
        limit: Límite de evaluaciones a indexar (None = todas)

    Returns:
        Número de evaluaciones indexadas
    """
    try:
        evaluation_logger.log_task_start(
            "Indexar Todas las Meet Evaluations",
            "Iniciando indexación masiva de evaluaciones de meets",
        )

        supabase = get_supabase_client()
        query = supabase.table("meet_evaluations").select("*")
        if limit:
            query = query.limit(limit)
        response = query.execute()

        evaluations = response.data or []

        indexed_count = 0
        for row in evaluations:
            try:
                index_meet_evaluation(row)
                indexed_count += 1
            except Exception as e:
                evaluation_logger.log_error(
                    "Indexar Todas las Meet Evaluations",
                    f"Error indexando meet_evaluation {row.get('id')}: {str(e)}",
                )
                continue

        evaluation_logger.log_task_complete(
            "Indexar Todas las Meet Evaluations",
            f"Indexadas {indexed_count} evaluaciones de meets",
        )
        return indexed_count

    except Exception as e:
        evaluation_logger.log_error(
            "Indexar Todas las Meet Evaluations",
            f"Error en indexación masiva de evaluaciones de meets: {str(e)}",
        )
        raise

def index_candidate_jd_status(record: Dict[str, Any]) -> str:
    """
    Indexa una relación candidate_jd_status en la knowledge base

    Args:
        record: Fila de la tabla candidate_jd_status, idealmente con joins
                a candidates y jd_interviews si están configurados.

    Returns:
        ID del chunk creado/actualizado
    """
    try:
        evaluation_logger.log_task_start(
            "Indexar Candidate JD Status",
            f"Indexando relación: {record.get('id', 'sin-id')}",
        )

        candidate = record.get("candidates") or record.get("candidate") or {}
        jd_interview = record.get("jd_interviews") or record.get("jd_interview") or {}

        candidate_id = record.get("candidate_id") or candidate.get("id")
        jd_interview_id = record.get("jd_interview_id") or jd_interview.get("id")
        status = record.get("status", "unknown")

        candidate_name = candidate.get("name", "Candidato desconocido")
        candidate_email = candidate.get("email", "sin-email")

        jd_name = jd_interview.get("interview_name", "Búsqueda desconocida")
        jd_tech = jd_interview.get("tech_stack") or []
        if isinstance(jd_tech, str):
            jd_tech_list = [t.strip() for t in jd_tech.split(",") if t.strip()]
        else:
            jd_tech_list = jd_tech

        created_at = record.get("created_at")

        # Construir contenido descriptivo
        content_parts = [
            f"Relación candidato-búsqueda: el candidato {candidate_name} ({candidate_email}) está asociado a la búsqueda {jd_name}.",
            f"Estado de la relación candidate_jd_status: {status}.",
        ]

        if jd_tech_list:
            content_parts.append(
                f"Tecnologías clave de la búsqueda: {', '.join(jd_tech_list)}"
            )

        if created_at:
            content_parts.append(f"Fecha de creación de la relación: {created_at}")

        content = " ".join(content_parts)

        # Generar embedding
        embedding = generate_embedding(content)

        # Metadata
        metadata: Dict[str, Any] = {
            "candidate_jd_status_id": record.get("id"),
            "candidate_id": candidate_id,
            "jd_interview_id": jd_interview_id,
            "status": status,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "jd_interview_name": jd_name,
            "jd_tech_stack": jd_tech_list,
            "created_at": created_at,
            "updated_at": record.get("updated_at"),
        }

        # Actualizar o insertar chunk (upsert)
        chunk_id = update_knowledge_chunk(
            entity_id=record.get("id"),
            entity_type="candidate_jd_status",
            content=content,
            embedding=embedding,
            metadata=metadata,
        )

        evaluation_logger.log_task_complete(
            "Indexar Candidate JD Status",
            f"Candidate JD Status indexado: {chunk_id}",
        )
        return chunk_id

    except Exception as e:
        evaluation_logger.log_error(
            "Indexar Candidate JD Status",
            f"Error indexando candidate_jd_status: {str(e)}",
        )
        raise

def index_all_candidate_jd_status(limit: Optional[int] = None) -> int:
    """
    Indexa todas las filas de candidate_jd_status de la BD

    Args:
        limit: Límite de filas a indexar (None = todas)

    Returns:
        Número de relaciones indexadas
    """
    try:
        evaluation_logger.log_task_start(
            "Indexar Todos los Candidate JD Status",
            "Iniciando indexación masiva de candidate_jd_status",
        )

        supabase = get_supabase_client()

        # Intentar traer también info de candidate y jd_interview si las relaciones existen
        # Los nombres 'candidates' y 'jd_interviews' dependen de las FKs en Supabase
        select_str = "*, candidates(name,email), jd_interviews(interview_name,tech_stack,client_id)"
        query = supabase.table("candidate_jd_status").select(select_str)
        if limit:
            query = query.limit(limit)
        response = query.execute()

        records = response.data or []

        indexed_count = 0
        for row in records:
            try:
                index_candidate_jd_status(row)
                indexed_count += 1
            except Exception as e:
                evaluation_logger.log_error(
                    "Indexar Todos los Candidate JD Status",
                    f"Error indexando candidate_jd_status {row.get('id')}: {str(e)}",
                )
                continue

        evaluation_logger.log_task_complete(
            "Indexar Todos los Candidate JD Status",
            f"Indexadas {indexed_count} relaciones candidate_jd_status",
        )
        return indexed_count

    except Exception as e:
        evaluation_logger.log_error(
            "Indexar Todos los Candidate JD Status",
            f"Error en indexación masiva de candidate_jd_status: {str(e)}",
        )
        raise
