#!/usr/bin/env python3
"""
API simple para disparar el proceso de análisis de candidatos
"""

import os
import json
import base64
import re
import requests
import tiktoken
import uuid
from uuid import UUID
from utils.helpers import clean_uuid, is_valid_uuid
import threading
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Optional, List, Any
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Response
import httpx
from pydantic import BaseModel
from crew import create_data_processing_crew
from cv_crew import create_cv_analysis_crew
from matching_crew import create_candidate_matching_crew
from filtered_crew import create_filtered_data_processing_crew
from single_meet_crew import create_single_meet_evaluation_crew
from utils.logger import evaluation_logger
from supabase import create_client
from tracking import TokenTracker
from tools.token_estimator import estimate_cost, estimate_task_tokens, estimate_completion_tokens, breakdown_context_tokens
from tools.supabase_tools import get_meet_evaluation_data, save_meet_evaluation, get_client_email
from tools.elevenlabs_tools import create_elevenlabs_agent, generate_elevenlabs_prompt_from_jd, update_elevenlabs_agent_prompt
from tools.vector_tools import search_similar_chunks, get_supabase_client
from agents import create_single_meet_evaluator_agent
from tasks import create_single_meet_extraction_task, create_single_meet_evaluation_task


GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "")
GRAPH_CLIENT_STATE = os.getenv("GRAPH_CLIENT_STATE", "")  # Debe coincidir con el usado al crear la suscripción
GRAPH_SCOPE = os.getenv("GRAPH_SCOPE", "https://graph.microsoft.com/.default")
GRAPH_BASE = os.getenv("GRAPH_BASE", "https://graph.microsoft.com/v1.0")
OUTLOOK_USER_ID = os.getenv("OUTLOOK_USER_ID", "")


# ====== Validations ======



# ====== Helpers ======

async def get_graph_app_token() -> str:
    """
    Obtiene un token de app (client credentials).
    Requiere permisos de aplicación (Application) en Graph y admin consent.
    """
    token_url = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": GRAPH_CLIENT_ID,
        "client_secret": GRAPH_CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": GRAPH_SCOPE,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(token_url, data=data)
        resp.raise_for_status()
        return resp.json()["access_token"]

def parse_resource_path(resource: str) -> tuple[str | None, str | None]:
    """
    Intenta extraer userId y messageId desde el string 'resource' de la notificación.
    Ejemplos de 'resource':
      - "Users/{userId}/MailFolders('inbox')/Messages('ABC123')"
      - "Users/{userId}/Messages('ABC123')"
    """
    user_id, message_id = None, None
    try:
        # Normalizá para búsquedas simples
        r = resource.replace('"', "'")
        # userId entre "Users/" y la siguiente "/"
        if "Users/" in r:
            user_part = r.split("Users/")[1]
            user_id = user_part.split("/")[0]
        # messageId entre "Messages('" y "')"
        if "Messages('" in r:
            message_id = r.split("Messages('")[1].split("')")[0]
    except Exception:
        pass
    return user_id, message_id

async def fetch_message(user_id: str, message_id: str, token: str) -> dict:
    """
    Lee el mensaje desde Graph.
    Ajustá $select si querés traer más/menos campos.
    """
    url = f"{GRAPH_BASE}/users/{user_id}/messages/{message_id}?$select=subject,from,receivedDateTime,bodyPreview,isRead,webLink"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()

def format_soft_skills(soft_skills: dict) -> str:
    """Formatea las habilidades blandas para el email"""
    if not soft_skills:
        return "No disponible"
    
    formatted = []
    skill_names = {
        "communication": "Comunicación",
        "leadership": "Liderazgo",
        "teamwork": "Trabajo en Equipo",
        "adaptability": "Adaptabilidad",
        "problem_solving": "Resolución de Problemas",
        "time_management": "Gestión del Tiempo",
        "emotional_intelligence": "Inteligencia Emocional",
        "continuous_learning": "Aprendizaje Continuo"
    }
    
    for key, value in soft_skills.items():
        skill_name = skill_names.get(key, key.replace("_", " ").title())
        if isinstance(value, str) and value:
            formatted.append(f"• {skill_name}: {value}")
        elif isinstance(value, (int, float)):
            formatted.append(f"• {skill_name}: {value}/10")
    
    return "\n".join(formatted) if formatted else "No disponible"

def format_technical_questions(questions: list) -> str:
    """Formatea las preguntas técnicas para el email"""
    if not questions:
        return "No disponible"
    
    formatted = []
    for i, q in enumerate(questions, 1):
        question_text = q.get('question', 'N/A')
        answered = q.get('answered', 'N/A')
        formatted.append(f"  {i}. {question_text} - Contestada: {answered}")
    
    return "\n".join(formatted) if formatted else "No disponible"

def load_email_template(template_name: str) -> str:
    """
    Carga una plantilla de email desde el directorio templates/email
    
    Args:
        template_name: Nombre del archivo de plantilla (ej: 'evaluation_match.html')
        
    Returns:
        Contenido de la plantilla como string
    """
    template_path = Path(__file__).parent / "templates" / "email" / template_name
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        evaluation_logger.log_error("Email Template", f"Plantilla no encontrada: {template_path}")
        return ""
    except Exception as e:
        evaluation_logger.log_error("Email Template", f"Error cargando plantilla: {str(e)}")
        return ""

def render_email_template(template_name: str, **kwargs) -> str:
    """
    Carga y renderiza una plantilla de email con las variables proporcionadas
    
    Args:
        template_name: Nombre del archivo de plantilla
        **kwargs: Variables para reemplazar en la plantilla
        
    Returns:
        Plantilla renderizada con las variables reemplazadas
    """
    template = load_email_template(template_name)
    if not template:
        return ""
    
    try:
        return template.format(**kwargs)
    except KeyError as e:
        evaluation_logger.log_error("Email Template", f"Variable faltante en plantilla: {e}")
        return template
    except Exception as e:
        evaluation_logger.log_error("Email Template", f"Error renderizando plantilla: {str(e)}")
        return template

def b64decode(s: str) -> str:
    """
    Decodifica string Base64 con padding tolerante
    
    Args:
        s: String en Base64
        
    Returns:
        String decodificado
    """
    pad = '=' * (-len(s) % 4)
    return base64.b64decode(s + pad).decode("utf-8", "replace")


app = FastAPI(
    title="Candidate Evaluation API",
    description="API para disparar el proceso de análisis de candidatos",
    version="1.0.0",
)

# Storage para runs (en producción usar Redis o DB)
matching_runs: Dict[str, dict] = {}

class AnalysisRequest(BaseModel):
    jd_interview_id: str = None

class SingleMeetRequest(BaseModel):
    meet_id: str

class AnalysisResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str | None = None
    results_file: str | None = None
    result: dict | None = None
    jd_interview_id: str | None = None
    evaluation_id: str | None = None

class CVRequest(BaseModel):
    filename: str
    client_id: str = None
    user_id: str = None

class CVAnalysisResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str = None
    filename: str = None
    candidate_data: dict = None
    candidate_created: bool | None = None
    candidate_error: str | None = None
    candidate_result: dict | None = None
    candidate_status: str | None = None

class MatchingRequest(BaseModel):
    user_id: str = None
    client_id: str = None

class MatchingResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str = None
    matches: list = None
    total_matches: int = None

class RunStatusResponse(BaseModel):
    status: str
    runId: str = None
    progress: float = None
    message: str = None
    result: dict = None
    error: str = None

@app.post("/analyze", response_model=AnalysisResponse)
async def trigger_analysis(request: AnalysisRequest = None):
    """
    Endpoint que dispara el proceso completo de análisis de candidatos
    
    Args:
        request: Objeto con jd_interview_id opcional para filtrar evaluaciones
    """
    try:
        start_time = datetime.now()
        
        # Verificar variables de entorno
        required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            evaluation_logger.log_error("API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(
                status_code=500, 
                detail=f"Variables de entorno faltantes: {missing_vars}"
            )
        
        # Log inicio del proceso
        jd_interview_id = request.jd_interview_id if request else None
        if jd_interview_id:
            if not is_valid_uuid(jd_interview_id):
                evaluation_logger.log_error("API", f"jd_interview_id inválido recibido: {jd_interview_id}")
                raise HTTPException(status_code=400, detail=f"jd_interview_id inválido: {jd_interview_id}")
            evaluation_logger.log_task_start("API", f"Iniciando proceso de análisis filtrado por jd_interview_id: {jd_interview_id}")
        else:
            evaluation_logger.log_task_start("API", "Iniciando proceso de análisis completo")

        # Preparar variables de evaluación (se insertará al final)
        evaluation_id = None
        client_id = None
                        
        # Crear y ejecutar crew (filtrado o completo)
        if jd_interview_id:
            try:
                supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
                
                jd_response = supabase.table('jd_interviews').select('client_id').eq('id', jd_interview_id).limit(1).execute()
                if jd_response.data:
                    jd_record = jd_response.data[0]
                    client_id = jd_record.get('client_id')
                    evaluation_logger.log_task_progress("API", f"client_id obtenido para jd_interview {jd_interview_id}: {client_id}")
                    
                    if client_id:
                        client_response = supabase.table('clients').select('email').eq('id', client_id).limit(1).execute()
                        if client_response.data:
                            client_email = client_response.data[0].get('email')
                            evaluation_logger.log_task_progress("API", f"Email del cliente encontrado: {client_email}")
                            print(f"[API] Email encontrado para jd_interview {jd_interview_id}: {client_email}")
                        else:
                            evaluation_logger.log_task_progress("API", f"No se encontró email para client_id: {client_id}")
                    else:
                        evaluation_logger.log_task_progress("API", f"El jd_interview {jd_interview_id} no tiene client_id asociado")
                else:
                    evaluation_logger.log_task_progress("API", f"No se encontró jd_interview con ID: {jd_interview_id}")
            except Exception as fetch_error:
                evaluation_logger.log_error("API", f"Error obteniendo email del cliente: {str(fetch_error)}")

        # Guardar email original si existe
        original_email = os.getenv("REPORT_TO_EMAIL")
        email_override_set = False
        
        if client_email:
            os.environ["REPORT_TO_EMAIL"] = client_email
            email_override_set = True
            evaluation_logger.log_task_progress("API", f"Email del cliente seteado para envío de reporte: {client_email}")

        try:
            # Crear y ejecutar crew (filtrado o completo)
            if jd_interview_id:
                crew = create_filtered_data_processing_crew(jd_interview_id)
            else:
                crew = create_data_processing_crew()
            
            print("=" * 80)
            print("🚀 INICIANDO EJECUCIÓN DEL CREW (Data Processing)")
            print("=" * 80)
            
            result = crew.kickoff()
            
            # Calcular tiempo de ejecución
            end_time = datetime.now()
            execution_time = str(end_time - start_time)
            
            evaluation_logger.log_task_complete("API", f"Análisis completado en {execution_time}")
            
            # Procesar resultado
            result_text = str(result)
            if hasattr(result, 'raw'):
                result_text = result.raw
            
            # Intentar parsear el resultado como JSON
            result_dict = None
            try:
                result_dict = json.loads(result_text)
            except json.JSONDecodeError:
                # Intentar extraer JSON del texto usando regex
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    try:
                        result_dict = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        result_dict = {"raw_result": result_text[:1000]}
                else:
                    result_dict = {"raw_result": result_text[:1000]}
            
            # Generar filename con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_results_{timestamp}.json"
            
            # Guardar resultado en archivo
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result_dict, f, indent=2, ensure_ascii=False)
            except Exception as file_error:
                evaluation_logger.log_error("API", f"Error guardando resultado en archivo: {str(file_error)}")
                filename = None
            
            return AnalysisResponse(
                status="success",
                message="Análisis completado exitosamente",
                timestamp=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                execution_time=execution_time,
                results_file=filename,
                result=result_dict,
                jd_interview_id=jd_interview_id
            )
        finally:
            # Restaurar email original si se cambió
            if email_override_set:
                if original_email:
                    os.environ["REPORT_TO_EMAIL"] = original_email
                else:
                    os.environ.pop("REPORT_TO_EMAIL", None)
                evaluation_logger.log_task_progress("API", "Email original restaurado")
        
    except Exception as e:
        evaluation_logger.log_error("API", f"Error en análisis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el análisis: {str(e)}")

@app.post("/read-cv", response_model=CVAnalysisResponse)
async def read_cv(request: CVRequest):
    """
    Endpoint para analizar un CV desde S3 y extraer datos del candidato
    
    Args:
        request: Objeto con el nombre del archivo en S3
        
    Returns:
        CVAnalysisResponse con los datos extraídos del candidato
    """
    try:
        start_time = datetime.now()
        # Verificar variables de entorno
        required_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            evaluation_logger.log_error("CV API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(
                status_code=500, 
                detail=f"Variables de entorno faltantes: {missing_vars}"
            )
        
        # Log inicio del proceso
        evaluation_logger.log_task_start("CV API", f"Iniciando análisis de CV: {request.filename}")
        
        # Crear y ejecutar crew
        crew = create_cv_analysis_crew(request.filename, user_id=request.user_id, client_id=request.client_id)
        
        print("=" * 80)
        print("🚀 INICIANDO EJECUCIÓN DEL CREW (CV Analysis)")
        print("=" * 80)
        
        result = crew.kickoff()
        
        # Calcular tiempo de ejecución
        end_time = datetime.now()
        execution_time = str(end_time - start_time)
        
        evaluation_logger.log_task_complete("CV API", f"Análisis completado en {execution_time}")
        
        # Extraer el resultado
        result_text = str(result)
        if hasattr(result, 'raw'):
            result_text = result.raw
        
        # Intentar detectar y parsear JSON del resultado de create_candidate (si el agente lo incluyó)
        candidate_created = None
        candidate_error = None
        candidate_result = None
        try:
            import re, json as _json
            # Buscar posibles bloques JSON en el texto
            json_like = re.findall(r"\{[\s\S]*?\}", result_text)
            parsed = []
            for block in json_like:
                try:
                    obj = _json.loads(block)
                    parsed.append(obj)
                except Exception:
                    continue
            # Heurística: quedarnos con el último que tenga 'success' o 'error_type'
            for obj in reversed(parsed):
                if isinstance(obj, dict) and ("success" in obj or "error_type" in obj or "email" in obj):
                    candidate_result = obj
                    break
            if candidate_result is not None:
                if 'success' in candidate_result:
                    candidate_created = bool(candidate_result.get('success'))
                if not candidate_created:
                    candidate_error = candidate_result.get('error') or candidate_result.get('error_type')
        except Exception:
            # Si falla el parseo, lo ignoramos
            pass

        # Determinar estado legible
        candidate_status = None
        if candidate_result is not None:
            error_type = (candidate_result.get('error_type') or '').lower()
            if candidate_created is True:
                candidate_status = 'created'
            elif error_type == 'alreadyexists':
                candidate_status = 'exists'
            elif candidate_created is False and not error_type:
                candidate_status = 'failed'
        
        # Mensaje claro
        base_message = "Análisis de CV completado exitosamente"
        if candidate_status == 'created':
            base_message += " - Candidato agregado"
        elif candidate_status == 'exists':
            base_message += " - Candidato ya existía"
        elif candidate_status == 'failed':
            base_message += " - No se pudo crear el candidato"

        return CVAnalysisResponse(
            status="success",
            message=base_message,
            timestamp=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=execution_time,
            filename=request.filename,
            candidate_data={"analysis": result_text},
            candidate_created=candidate_created,
            candidate_error=candidate_error,
            candidate_result=candidate_result,
            candidate_status=candidate_status
        )
        
    except Exception as e:
        evaluation_logger.log_error("CV API", f"Error en análisis de CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el análisis del CV: {str(e)}")

def do_matching_long_task(run_id: str, user_id: Optional[str], client_id: Optional[str]):
    """
    Ejecuta el proceso de matching en background
    """
    try:
        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.0,
            "message": "Iniciando proceso de matching...",
            "runId": run_id
        }
        
        start_time = datetime.now()
        
        # Verificar variables de entorno
        required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            matching_runs[run_id] = {
                "status": "error",
                "error": f"Variables de entorno faltantes: {missing_vars}",
                "runId": run_id
            }
            return
        
        # Log inicio del proceso
        if user_id and client_id:
            evaluation_logger.log_task_start("Matching API", f"Iniciando proceso de matching filtrado por user_id: {user_id}, client_id: {client_id}")
            print(f"[MATCHING API] 🚀 Iniciando matching con filtros - user_id: {user_id}, client_id: {client_id}")
        else:
            evaluation_logger.log_task_start("Matching API", "Iniciando proceso de matching (sin filtros)")
            print(f"[MATCHING API] 🚀 Iniciando matching SIN filtros (todos los candidatos)")
        
        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.2,
            "message": "Creando crew de matching...",
            "runId": run_id
        }
        
        print(f"[MATCHING API] 📋 Creando crew de matching...")
        # Crear y ejecutar crew de matching
        crew = create_candidate_matching_crew(user_id=user_id, client_id=client_id)
        print(f"[MATCHING API] ✅ Crew creado, iniciando matching...")
        
        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.4,
            "message": "Ejecutando matching...",
            "runId": run_id
        }
        
        result = crew.kickoff()
        
        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.7,
            "message": "Procesando resultados...",
            "runId": run_id
        }
        
        # Calcular tiempo de ejecución
        end_time = datetime.now()
        execution_time = str(end_time - start_time)
        
        evaluation_logger.log_task_complete("Matching API", f"Matching completado en {execution_time}")
        
        # Procesar resultado
        result_text = str(result)
        if hasattr(result, 'raw'):
            result_text = result.raw
        
        # Log del resultado para debugging
        evaluation_logger.log_task_progress("Matching API", f"Longitud del resultado: {len(result_text)} caracteres")
        evaluation_logger.log_task_progress("Matching API", f"Primeros 500 caracteres: {result_text[:500]}")
        evaluation_logger.log_task_progress("Matching API", f"Últimos 200 caracteres: {result_text[-200:]}")
        if '"matches"' in result_text:
            evaluation_logger.log_task_progress("Matching API", "El resultado contiene 'matches'")
        else:
            evaluation_logger.log_task_progress("Matching API", "⚠️ El resultado NO contiene 'matches'")
        
        # Intentar parsear el resultado como JSON
        matches_data = None
        try:
            matches_data = json.loads(result_text)
            evaluation_logger.log_task_progress("Matching API", "Resultado parseado como JSON exitosamente")
        except json.JSONDecodeError:
            evaluation_logger.log_task_progress("Matching API", "Resultado no es JSON válido, intentando extraer datos del texto")
            
            # Intentar extraer JSON del texto usando múltiples estrategias
            json_extracted = None
            
            # Estrategia 1: Buscar JSON dentro de bloques de código markdown (```json ... ```)
            markdown_json_pattern = r'```(?:json)?\s*(\{.*?"matches".*?\})\s*```'
            markdown_matches = re.findall(markdown_json_pattern, result_text, re.DOTALL)
            if markdown_matches:
                try:
                    json_extracted = json.loads(markdown_matches[0])
                    evaluation_logger.log_task_progress("Matching API", "JSON extraído de bloque markdown exitosamente")
                except json.JSONDecodeError:
                    pass
            
            # Estrategia 2: Buscar JSON que contenga "matches" usando búsqueda de llaves balanceadas
            if not json_extracted:
                # Encontrar todas las posiciones donde aparece "matches"
                matches_positions = [m.start() for m in re.finditer(r'"matches"', result_text)]
                for match_pos in matches_positions:
                    # Buscar hacia atrás para encontrar el { inicial
                    start_pos = result_text.rfind('{', 0, match_pos)
                    if start_pos == -1:
                        continue
                    
                    # Buscar hacia adelante para encontrar el } final balanceado
                    brace_count = 0
                    end_pos = -1
                    for i in range(start_pos, len(result_text)):
                        if result_text[i] == '{':
                            brace_count += 1
                        elif result_text[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i
                                break
                    
                    if end_pos != -1:
                        potential_json = result_text[start_pos:end_pos + 1]
                        try:
                            json_extracted = json.loads(potential_json)
                            evaluation_logger.log_task_progress("Matching API", "JSON extraído del texto usando búsqueda balanceada exitosamente")
                            break
                        except json.JSONDecodeError:
                            continue
            
            # Estrategia 3: Buscar desde el primer { hasta el último } que contenga "matches"
            if not json_extracted:
                first_brace = result_text.find('{')
                last_brace = result_text.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    potential_json = result_text[first_brace:last_brace + 1]
                    if '"matches"' in potential_json:
                        try:
                            json_extracted = json.loads(potential_json)
                            evaluation_logger.log_task_progress("Matching API", "JSON extraído usando estrategia de búsqueda de llaves exitosamente")
                        except json.JSONDecodeError:
                            pass
            
            matches_data = json_extracted
            if not matches_data:
                evaluation_logger.log_task_progress("Matching API", "No se pudo extraer JSON válido del texto")
        
        # Extraer la lista de matches
        matches_list = []
        total_matches = 0
        if matches_data:
            if isinstance(matches_data, dict) and 'matches' in matches_data:
                matches_list = matches_data['matches']
                total_matches = len(matches_list)
                evaluation_logger.log_task_progress("Matching API", f"Matches extraídos del dict: {total_matches}")
            elif isinstance(matches_data, list):
                matches_list = matches_data
                total_matches = len(matches_list)
                evaluation_logger.log_task_progress("Matching API", f"Matches extraídos de la lista: {total_matches}")
            else:
                evaluation_logger.log_task_progress("Matching API", "Formato de datos no reconocido")
        else:
            evaluation_logger.log_task_progress("Matching API", "No se pudieron extraer matches del resultado")
            matches_data = {
                "matches": [],
                "raw_result": result_text[:1000] + "..." if len(result_text) > 1000 else result_text
            }
        
        # Guardar resultado
        result_data = {
            "status": "success",
            "message": "Matching de candidatos completado exitosamente",
            "timestamp": start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "execution_time": execution_time,
            "matches": matches_list,
            "total_matches": total_matches
        }
        
        matching_runs[run_id] = {
            "status": "done",
            "progress": 1.0,
            "message": "Matching completado exitosamente",
            "result": result_data,
            "runId": run_id
        }
        
    except Exception as e:
        error_msg = str(e)
        evaluation_logger.log_error("Matching API", f"Error en matching: {error_msg}")
        matching_runs[run_id] = {
            "status": "error",
            "error": error_msg,
            "runId": run_id
        }

@app.post("/match-candidates")
async def match_candidates(request: MatchingRequest = None):
    """
    Endpoint para iniciar matching entre candidatos (tech_stack) y entrevistas (job_description)
    Retorna inmediatamente con un runId para consultar el estado
    
    Args:
        request: Objeto con user_id y client_id opcionales para filtrar candidatos
    
    Returns:
        JSON con runId para consultar el estado del proceso
    """
    try:
        user_id = request.user_id if request else None
        client_id = request.client_id if request else None
        
        # Generar runId único
        run_id = str(uuid.uuid4())
        
        # Inicializar estado
        matching_runs[run_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "Proceso en cola...",
            "runId": run_id
        }
        
        # Ejecutar en background usando threading
        thread = threading.Thread(
            target=do_matching_long_task,
            args=(run_id, user_id, client_id),
            daemon=True
        )
        thread.start()
        
        # Retornar inmediatamente con runId
        return Response(
            content=json.dumps({
                "runId": run_id,
                "status": "queued",
                "message": "Matching iniciado, consulta el estado con GET /match-candidates/{runId}"
            }),
            status_code=202,
            media_type="application/json"
        )
        
    except Exception as e:
        evaluation_logger.log_error("Matching API", f"Error iniciando matching: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error iniciando matching: {str(e)}")

@app.get("/match-candidates/{run_id}")
async def get_matching_status(run_id: str):
    """
    Endpoint para consultar el estado del proceso de matching
    
    Args:
        run_id: ID del proceso de matching
    
    Returns:
        Estado del proceso: queued, running, done, o error
    """
    if run_id not in matching_runs:
        raise HTTPException(status_code=404, detail="runId not found")
    
    run_data = matching_runs[run_id]
    
    # Formatear respuesta según el estado (formato compatible con RunStatus del frontend)
    if run_data["status"] == "done":
        return {
            "status": "done",
            "result": run_data.get("result")
        }
    elif run_data["status"] == "error":
        return {
            "status": "error",
            "error": run_data.get("error", "Unknown error")
        }
    else:
        # queued o running
        return {
            "status": run_data["status"],
            "progress": run_data.get("progress", 0.0),
            "message": run_data.get("message", "")
        }

@app.get("/status")
async def get_status():
    """
    Endpoint simple para verificar el estado de la API
    """
    return {
        "status": "active",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "service": "Candidate Evaluation API"
    }

def get_access_token():
    tenant = GRAPH_TENANT_ID
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        'client_id': GRAPH_CLIENT_ID,
        'client_secret': GRAPH_CLIENT_SECRET,
        'scope': GRAPH_SCOPE or 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, data=data)
    return response.json()['access_token']

def get_email_details(message_id):
    """Obtiene los detalles completos del email"""
    token = get_access_token()
    
    # URL para obtener el mensaje específico
    base = GRAPH_BASE or "https://graph.microsoft.com/v1.0"
    user_id = OUTLOOK_USER_ID
    url = f"{base}/users/{user_id}/messages/{message_id}"
        
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(url, headers=headers)
    return response.json()

@app.post("/webhook")
async def outlook_webhook(request: Request):
    # Validación de Microsoft
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        print("✅ Webhook validado por Microsoft")
        return Response(content=validation_token, status_code=200)
        # Nota: se quita el return para permitir continuar con el flujo
    
    # Notificación real de email
    try:
        data = await request.json()
        
        _events = len(data.get('value', [])) if isinstance(data, dict) else 0
        print(f"📧 Notificación recibida - {_events} evento(s)")
        
        if 'value' in data:
            for notification in data['value']:
                # Extraer ID del mensaje y user_id
                resource_data = notification.get('resourceData', {})
                message_id = resource_data.get('id')
                user_id = resource_data.get('userId')
                
                # Si no hay user_id en resourceData, intentar parsear desde resource
                if not user_id:
                    resource = notification.get('resource', '')
                    if resource:
                        p_user, p_msg = parse_resource_path(resource)
                        user_id = user_id or p_user
                        message_id = message_id or p_msg
                
                # Si no hay user_id, usar el configurado
                if not user_id:
                    user_id = OUTLOOK_USER_ID
                
                if not message_id:
                    print(f"❓ No se pudo extraer message_id desde: {notification}")
                    continue
                
                print(f"Message ID: {message_id}, User ID: {user_id}")
                
                # Log conciso del email (mostrar info clave y preview corta)
                try:
                    from tools.email_tools import GraphEmailMonitor
                    _monitor_preview = GraphEmailMonitor()
                    _msg = _monitor_preview.fetch_message(user_id, message_id)
                    _subject = _msg.get('subject', '')
                    _from_data = _msg.get('from', {}) or {}
                    _from_email = (_from_data.get('emailAddress') or {}).get('address', '')
                    _from_name = (_from_data.get('emailAddress') or {}).get('name', '')
                    _sender_str = f"{_from_name} <{_from_email}>" if _from_email else (_from_name or 'Unknown')
                    _recv = _msg.get('receivedDateTime', '')
                    _body_text = _monitor_preview.extract_text_from_body(_msg.get('body') or {})
                    if not _body_text:
                        _body_text = _msg.get('bodyPreview', '')

                    print(f"📧 Email: '{_subject}' | De: {_sender_str} | Fecha: {_recv}")
                    preview_len = 300
                    if _body_text:
                        _trunc = '…' if len(_body_text) > preview_len else ''
                        _slice = (_body_text or '')[:preview_len]
                        print(f"📝 Preview ({min(len(_body_text), preview_len)}): {_slice}{_trunc}")
                except Exception as _e_log:
                    print(f"⚠️ No se pudo mostrar contenido: {str(_e_log)}")

                # Procesar el email usando GraphEmailMonitor
                try:
                    from tools.email_tools import GraphEmailMonitor
                    monitor = GraphEmailMonitor()
                    result = monitor.process_email_from_graph(message_id, user_id)
                    
                    if result:
                        print(f"✅ Email procesado exitosamente: {result.get('subject', '')}")
                    else:
                        print(f"⚠️ Email no procesado (no es -JD o error)")
                        
                except Exception as e:
                    print(f"❌ Error procesando email: {str(e)}")
                    evaluation_logger.log_error("Webhook", f"Error procesando email {message_id}: {str(e)}")
                
        return {"status": "ok"}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        evaluation_logger.log_error("Webhook", f"Error en webhook: {str(e)}")
        return {"status": "error"}

def _build_emotion_sentiment_summary(emotion_analysis: dict | None) -> dict | None:
    """
    Construye un pequeño resumen textual de emociones a partir de emotion_analysis
    proveniente de la tabla conversations.emotion_analysis (Prosody / Burst).
    """
    if not isinstance(emotion_analysis, dict):
        return None

    prosody = emotion_analysis.get("prosody") or {}
    burst = emotion_analysis.get("burst") or {}

    prosody_summary = prosody.get("summary") or []
    burst_summary = burst.get("summary") or []

    def summarize(label: str, items: list[dict]) -> str:
        if not items:
            return f"No se detectaron emociones predominantes en {label}."

        # Ordenar por averageScore descendente y tomar top 3
        ordered = sorted(
            items,
            key=lambda x: x.get("averageScore", 0) or 0,
            reverse=True,
        )[:3]

        def display_name(item: dict) -> str:
            return item.get("nameTranslated") or item.get("name") or "N/A"

        names = [display_name(it) for it in ordered]
        top_score = ordered[0].get("averageScore", 0) or 0

        if top_score >= 0.6:
            intensity = "muy alta"
        elif top_score >= 0.3:
            intensity = "moderada"
        else:
            intensity = "baja"

        if len(names) == 1:
            names_text = names[0]
        elif len(names) == 2:
            names_text = f"{names[0]} y {names[1]}"
        else:
            names_text = f"{', '.join(names[:-1])} y {names[-1]}"

        return f"En {label} predominaron {names_text}, con una intensidad emocional {intensity}."

    prosody_text = summarize("la voz continua (prosody)", prosody_summary)
    burst_text = summarize("los vocal bursts (burst)", burst_summary)

    return {
        "raw_emotion_analysis": emotion_analysis,
        "prosody_summary_text": prosody_text,
        "burst_summary_text": burst_text,
    }


@app.post("/evaluate-meet", response_model=AnalysisResponse)
async def evaluate_single_meet(request: SingleMeetRequest):
    """
    Endpoint que evalúa un solo meet para determinar si el candidato es un posible match
    basado en la JD del meet
    
    Args:
        request: Objeto con meet_id del meet a evaluar
    """
    tracker = None
    try:
        meet_id = request.meet_id
        evaluation_logger.log_task_start("API", f"Iniciando evaluación de meet: {meet_id}")
        
        # Inicializar tracker de tokens
        tracker = TokenTracker(log_dir="logs/token_tracking")
        run_id = tracker.start_run(
            crew_name="SingleMeetEvaluationCrew",
            meta={"meet_id": meet_id}
        )
        print(f"▶ RunID: {run_id}")
        
        start_time = datetime.now()
        
        # Crear y ejecutar crew de evaluación individual        
        #COMENTADO PARA PROBAR CON DATOS MOCKEADOS
        crew = create_single_meet_evaluation_crew(meet_id)
        
        print("=" * 80)
        print("🚀 INICIANDO EJECUCIÓN DEL CREW (Single Meet Evaluation)")
        print("=" * 80)
        
        result = crew.kickoff()
        
        #RECORDAR DESCOMENTAR LA LINEA QUE HACE EL FULL_RESULT = RESULT
        print("Cargando datos mockados desde utils/data.json")
        #result = json.load(open("utils/data.json", "r", encoding="utf-8"))
        #print("result: ", result)
        
        #Descomentar para trackeo de tokens del crew
        # Registrar uso de tokens del crew
        tracker.add_crew_result(
            result=result,
            step_name="crew.kickoff",
            agent=None,
            task=None,
            extra={
                "usage_metrics": getattr(crew, "usage_metrics", None),
                "result_meta": getattr(result, "raw", None) and {"has_raw": True}
            }
        )
        
        end_time = datetime.now()
        execution_time = end_time - start_time
        
        evaluation_logger.log_task_complete("API", f"Evaluación de meet completada - Tiempo: {execution_time}")
        
        # Extraer el contenido del resultado del crew
        result_str = str(result)
        # Intentar extraer JSON del resultado si es un CrewOutput
        if hasattr(result, 'raw'):
            result_str = result.raw
        elif hasattr(result, 'content'):
            result_str = result.content
        else:
            result_str = str(result)
            
        # Intentar parsear como JSON (puede venir en formato ```json ... ```)
        full_result = None
        try:
            # Buscar JSON dentro de markdown code blocks
            json_match = re.search(r'```json\s*(\{.*\})\s*```', result_str, re.DOTALL)
            if json_match:
                full_result = json.loads(json_match.group(1))
            else:
                # Intentar parsear directamente
                #full_result = result
                full_result = json.loads(result_str) #Descomentar para usar el resultado original
                
        except (json.JSONDecodeError, AttributeError):
            # Si no es JSON válido, intentar extraer cualquier JSON del texto
            try:
                # Buscar cualquier objeto JSON en el texto
                json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
                if json_match:
                    full_result = json.loads(json_match.group(0))
                else:
                    # Si todo falla, continuar con valores por defecto sin romper la API
                    evaluation_logger.log_error("API", "No se pudo parsear el resultado como JSON (sin bloque JSON detectable)")
                    full_result = {}
            except Exception as parse_err:
                # Continuar con valores por defecto sin lanzar 500
                evaluation_logger.log_error("API", f"No se pudo parsear el resultado como JSON: {parse_err}")
                full_result = {}
        
        # Extraer solo los campos finales del match_evaluation
        result_data: dict[str, Any] = {
            "final_recommendation": None,
            "justification": None,
            "is_potential_match": None,
            "compatibility_score": None,
            # Campo para exponer en el resultado final el resumen de emociones de voz
            "emotion_sentiment_summary": None,
        }
        
        # Buscar en match_evaluation
        if isinstance(full_result, dict):
            match_eval = full_result.get("match_evaluation", {})
            if isinstance(match_eval, dict):
                result_data["final_recommendation"] = match_eval.get("final_recommendation")
                result_data["justification"] = match_eval.get("justification")
                result_data["is_potential_match"] = match_eval.get("is_potential_match")
                result_data["compatibility_score"] = match_eval.get("compatibility_score")
        
        # ===== Verificar si el agente procesó emotion_analysis =====
        # El agente ahora recibe emotion_analysis a través de get_meet_evaluation_data
        # y debe procesarlo en su análisis. Solo verificamos si lo hizo y agregamos datos raw si falta.
        try:
            if isinstance(full_result, dict):
                conversation_analysis = full_result.get("conversation_analysis") or {}
                emotion_summary = conversation_analysis.get("emotion_sentiment_summary")
                
                # Si el agente no procesó los datos de emociones, intentar obtenerlos y agregarlos como fallback
                if not emotion_summary or not emotion_summary.get("prosody_summary_text"):
                    url = os.getenv("SUPABASE_URL")
                    key = os.getenv("SUPABASE_KEY")
                    if url and key:
                        supabase = create_client(url, key)

                        # Tomar la conversación más reciente asociada al meet
                        conv_resp = (
                            supabase.table("conversations")
                            .select("emotion_analysis")
                            .eq("meet_id", meet_id)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                        )

                        if conv_resp.data and len(conv_resp.data) > 0:
                            emotion_analysis = conv_resp.data[0].get("emotion_analysis")
                            if emotion_analysis:
                                # Solo agregar datos raw si el agente no los procesó
                                if not emotion_summary:
                                    conversation_analysis["emotion_sentiment_summary"] = {
                                        "raw_emotion_analysis": emotion_analysis,
                                        "prosody_summary_text": None,
                                        "burst_summary_text": None,
                                    }
                                    full_result["conversation_analysis"] = conversation_analysis
                                    evaluation_logger.log_task_progress(
                                        "API",
                                        "Datos raw de emotion_analysis agregados (el agente no los procesó)",
                                    )
                                elif not emotion_summary.get("raw_emotion_analysis"):
                                    # Agregar solo raw_emotion_analysis si falta
                                    emotion_summary["raw_emotion_analysis"] = emotion_analysis
                                    conversation_analysis["emotion_sentiment_summary"] = emotion_summary
                                    full_result["conversation_analysis"] = conversation_analysis
                
                # Exponer resumen en result_data si existe
                if emotion_summary:
                    result_data["emotion_sentiment_summary"] = {
                        "prosody_summary_text": emotion_summary.get("prosody_summary_text"),
                        "burst_summary_text": emotion_summary.get("burst_summary_text"),
                    }
        except Exception as emotion_err:
            evaluation_logger.log_error(
                "API",
                f"Error al verificar/agregar emotion_analysis: {emotion_err}",
            )

        # Guardar evaluación en la base de datos - MEET_EVALUATIONS
        if isinstance(full_result, dict) and full_result:
            try:
                # Convertir full_result a JSON string para la función
                full_result_json = json.dumps(full_result, ensure_ascii=False)
                
                # Acceder a la función subyacente del Tool
                func_to_call = None
                if hasattr(save_meet_evaluation, '__wrapped__'):
                    func_to_call = save_meet_evaluation.__wrapped__
                elif hasattr(save_meet_evaluation, 'func'):
                    func_to_call = save_meet_evaluation.func
                elif hasattr(save_meet_evaluation, '_func'):
                    func_to_call = save_meet_evaluation._func
                else:
                    # Intentar llamar directamente
                    func_to_call = save_meet_evaluation
                
                if func_to_call:
                    save_result = func_to_call(full_result_json)
                    save_result_data = json.loads(save_result) if isinstance(save_result, str) else save_result
                    
                    if save_result_data.get("success"):
                        evaluation_id = save_result_data.get("evaluation_id")
                        action = save_result_data.get("action", "created")
                        evaluation_logger.log_task_complete("API", f"Evaluación guardada en meet_evaluation: {evaluation_id} (acción: {action})")
                        print(f"✅ Evaluación guardada en meet_evaluation: {evaluation_id}")
                    else:
                        error_msg = save_result_data.get("error", "Error desconocido")
                        evaluation_logger.log_error("API", f"Error guardando evaluación en meet_evaluation: {error_msg}")
                        print(f"⚠️ Error guardando evaluación: {error_msg}")
                else:
                    evaluation_logger.log_error("API", "No se pudo acceder a la función subyacente de save_meet_evaluation")
                    print("⚠️ No se pudo acceder a la función subyacente de save_meet_evaluation")
            except Exception as save_error:
                evaluation_logger.log_error("API", f"Error al guardar evaluación en meet_evaluation: {str(save_error)}")
                print(f"⚠️ Error al guardar evaluación: {str(save_error)}")
                import traceback
                evaluation_logger.log_error("API", f"Traceback: {traceback.format_exc()}")
        
        # Si es un posible match, enviar email del cliente del JD interview
        email_sent = False
        if result_data.get("is_potential_match") is True:
            try:
                # Obtener datos del meet para conseguir jd_interviews_id
                url = os.getenv("SUPABASE_URL")
                key = os.getenv("SUPABASE_KEY")
                supabase = create_client(url, key)
                
                # Obtener el meet con jd_interview y client
                meet_response = supabase.table('meets').select(
                    '''
                    jd_interviews_id,
                    jd_interviews(
                        interview_name,
                        client_id,
                        clients(
                            email,
                            name,
                            responsible,
                            phone
                        )
                    )
                    '''
                ).eq('id', meet_id).execute()
                
                if meet_response.data and len(meet_response.data) > 0:
                    meet = meet_response.data[0]
                    jd_interviews_id = meet.get('jd_interviews_id')
                    jd_interview = meet.get('jd_interviews')
                    
                    if jd_interview:
                        interview_name = jd_interview.get('interview_name', 'N/A')
                        client = jd_interview.get('clients')
                        
                        if client and client.get('email'):
                            client_email = client.get('email')
                            client_name = client.get('name', 'N/A')
                            client_responsible = client.get('responsible', 'N/A')
                            client_phone = client.get('phone', 'N/A')
                            
                            # Obtener datos completos para el email
                            candidate_data = full_result.get("candidate", {})
                            conversation_data = full_result.get("conversation_analysis", {})
                            emotion_summary = conversation_data.get("emotion_sentiment_summary", {}) if isinstance(conversation_data, dict) else {}
                            prosody_summary_text = emotion_summary.get("prosody_summary_text")
                            burst_summary_text = emotion_summary.get("burst_summary_text")
                            
                            # Obtener la conversación completa del meet
                            conversation_response = supabase.table('conversations').select(
                                'conversation_data'
                            ).eq('meet_id', meet_id).execute()
                            
                            conversation_text = "No disponible"
                            if conversation_response.data and len(conversation_response.data) > 0:
                                conv_data = conversation_response.data[0].get('conversation_data', {})
                                if isinstance(conv_data, dict):
                                    # Formatear conversación como texto
                                    messages = conv_data.get('messages', [])
                                    if messages:
                                        conv_lines = []
                                        for msg in messages:
                                            role = msg.get('role', 'unknown')
                                            content = msg.get('content', '')
                                            if role == 'user':
                                                conv_lines.append(f"👤 Candidato: {content}")
                                            elif role == 'assistant' or role == 'ai':
                                                conv_lines.append(f"🤖 Entrevistador: {content}")
                                            else:
                                                conv_lines.append(f"{role}: {content}")
                                        conversation_text = "\n\n".join(conv_lines)
                                elif isinstance(conv_data, str):
                                    conversation_text = conv_data
                            
                            # Crear asunto del email
                            subject = f"✅ Match Potencial - {interview_name} - Score: {result_data.get('compatibility_score', 0)}%"
                            
                            # Preparar datos para la plantilla
                            tech_stack = candidate_data.get('tech_stack', [])
                            tech_stack_str = ', '.join(tech_stack) if isinstance(tech_stack, list) else str(tech_stack)
                            
                            technical_assessment = conversation_data.get('technical_assessment', {})
                            
                            # Renderizar plantilla de email
                            body = render_email_template(
                                "evaluation_match.html",
                                interview_name=interview_name,
                                compatibility_score=result_data.get('compatibility_score', 0),
                                final_recommendation=result_data.get('final_recommendation', 'N/A'),
                                candidate_name=candidate_data.get('name', 'N/A'),
                                candidate_email=candidate_data.get('email', 'N/A'),
                                candidate_phone=candidate_data.get('phone', 'N/A'),
                                candidate_tech_stack=tech_stack_str,
                                candidate_cv_url=candidate_data.get('cv_url', 'N/A'),
                                soft_skills_formatted=format_soft_skills(conversation_data.get('soft_skills', {})),
                                emotion_prosody_summary_text=prosody_summary_text or "No se detectaron emociones predominantes en la voz continua.",
                                emotion_burst_summary_text=burst_summary_text or "No se detectaron emociones predominantes en los vocal bursts.",
                                knowledge_level=technical_assessment.get('knowledge_level', 'N/A'),
                                practical_experience=technical_assessment.get('practical_experience', 'N/A'),
                                technical_questions_formatted=format_technical_questions(technical_assessment.get('technical_questions', [])),
                                justification=result_data.get('justification', 'No disponible'),
                                conversation_text=conversation_text,
                                client_name=client_name,
                                client_responsible=client_responsible,
                                client_phone=client_phone,
                                client_email=client_email,
                                meet_id=meet_id,
                                jd_interviews_id=jd_interviews_id
                            )
                            
                            # Enviar email
                            email_api_url = os.getenv("EMAIL_API_URL")
                            
                            payload = {
                                "to_email": client_email,
                                "subject": subject,
                                "body": body
                            }
                            
                            #COMENTADO PARA PROBAR CON DATOS MOCKEADOS
                            #response = requests.post(
                            #     email_api_url,
                            #     json=payload,
                            #     headers={'Content-Type': 'application/json'},
                            #     timeout=30
                            # )
                            
                            response.raise_for_status()
                            email_sent = True
                            evaluation_logger.log_task_complete("Envío Email Match", f"Email enviado exitosamente a {client_email}")
                        else:
                            evaluation_logger.log_error("Envío Email Match", "No se encontró email del cliente en la tabla clients")
                    else:
                        evaluation_logger.log_error("Envío Email Match", "No se encontró jd_interview para el meet")
                        
            except Exception as email_error:
                evaluation_logger.log_error("Envío Email Match", f"Error enviando email de match: {str(email_error)}")
                # No fallar la respuesta por error en el email
        
        # Finalizar tracking de tokens
        if tracker:
            try:
                out_path = tracker.finish_run()
                print(f"✅ Token tracking completado. Log guardado en: {out_path}")
            except Exception as tracker_error:
                evaluation_logger.log_error("API", f"Error finalizando token tracker: {str(tracker_error)}")
        
        return AnalysisResponse(
            status="success",
            message=f"Evaluación del meet {meet_id} completada exitosamente" + (f" - Email enviado" if email_sent else ""),
            timestamp=end_time.strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=str(execution_time),
            result=result_data
        )
        
    except Exception as e:
        evaluation_logger.log_error("API", f"Error en evaluación de meet: {str(e)}")
        # Finalizar tracking incluso si hay error
        if tracker:
            try:
                tracker.finish_run()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Error en la evaluación: {str(e)}")
    
    
# ====== Procesamiento ======

async def handle_outlook_notifications(payload: dict):
    """
    Procesa cada notificación usando GraphEmailMonitor.
    - Verifica clientState
    - Maneja lifecycle notifications (si las configuraste)
    - Obtiene userId y messageId
    - Procesa el email usando GraphEmailMonitor
    """
    try:
        from tools.email_tools import GraphEmailMonitor
        monitor = GraphEmailMonitor()
        
        values = payload.get("value", [])
        for n in values:
            # Lifecycle notifications (opcional)
            # Ej: {"lifecycleEvent": "reauthorizationRequired"} etc.
            lifecycle_event = n.get("lifecycleEvent")
            if lifecycle_event:
                print(f"♻️ Lifecycle event: {lifecycle_event} (subscriptionId={n.get('subscriptionId')})")
                # TODO: manejar renovación/reauthorization si hace falta
                continue

            # Seguridad: validar clientState si lo usaste al crear la suscripción
            if GRAPH_CLIENT_STATE and n.get("clientState") and n["clientState"] != GRAPH_CLIENT_STATE:
                print("⚠️ clientState inválido; ignorando notificación")
                continue

            change_type = n.get("changeType")  # created, updated, deleted
            resource = n.get("resource", "")
            resource_data = n.get("resourceData", {})

            # Priorizar resourceData.id si estás usando includeResourceData=false (Graph igual suele mandar id)
            user_id = resource_data.get("userId")
            message_id = resource_data.get("id")

            if not user_id or not message_id:
                # Intentar parsear desde 'resource'
                p_user, p_msg = parse_resource_path(resource)
                user_id = user_id or p_user
                message_id = message_id or p_msg

            # Si no hay user_id, usar el configurado
            if not user_id:
                user_id = OUTLOOK_USER_ID

            print(f"🔎 changeType={change_type} userId={user_id} messageId={message_id}")

            # Si no hay ids suficientes, log y continuar
            if not user_id or not message_id:
                print(f"❓ No se pudo extraer userId/messageId desde: resourceData={resource_data} resource='{resource}'")
                continue

            # Procesar el email usando GraphEmailMonitor
            try:
                result = monitor.process_email_from_graph(message_id, user_id)
                if result:
                    print(f"✅ Email procesado exitosamente: {result.get('subject', '')}")
                else:
                    print(f"⚠️ Email no procesado (no es -JD o error)")
            except Exception as ex:
                print(f"❌ Error procesando mensaje {message_id}: {str(ex)}")
                evaluation_logger.log_error("Handle Notifications", f"Error procesando mensaje {message_id}: {str(ex)}")

    except Exception as e:
        print(f"❌ Error procesando notificaciones: {str(e)}")
        evaluation_logger.log_error("Handle Notifications", f"Error procesando notificaciones: {str(e)}")

class CreateAgentRequest(BaseModel):
    jd_interview_id: str

class UpdateAgentRequest(BaseModel):
    jd_interview_id: str

class CreateAgentResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    jd_interview_id: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None

class TokenEstimationResponse(BaseModel):
    status: str
    message: str
    meet_id: str

class ChatbotRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []

class ChatbotResponse(BaseModel):
    response: str
    sources: Optional[List[Dict[str, Any]]] = []
    model: Optional[str] = None
    estimated_input_tokens: Optional[int] = None
    estimated_completion_tokens: Optional[int] = None
    estimated_total_tokens: Optional[int] = None
    estimated_input_cost_usd: Optional[float] = None
    estimated_completion_cost_usd: Optional[float] = None
    estimated_total_cost_usd: Optional[float] = None
    timestamp: Optional[str] = None

class CandidateInfoResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    candidate: Optional[Dict[str, Any]] = None
    candidates: Optional[List[Dict[str, Any]]] = None  # Para búsquedas por nombre
    related_meets: Optional[List[Dict[str, Any]]] = None
    related_evaluations: Optional[List[Dict[str, Any]]] = None

@app.post("/estimate-meet-tokens", response_model=TokenEstimationResponse)
async def estimate_meet_tokens(request: SingleMeetRequest):
    """
    Endpoint que estima el consumo de tokens antes de ejecutar el crew de evaluación de un meet
    
    Args:
        request: Objeto con meet_id del meet a evaluar
        
    Returns:
        Estimación de tokens y costo aproximado
    """
    try:
        meet_id = request.meet_id
        evaluation_logger.log_task_start("API", f"Estimando tokens para meet: {meet_id}")
        
        # Obtener datos del meet para estimar tokens
        func_to_call = None
        if hasattr(get_meet_evaluation_data, '__wrapped__'):
            func_to_call = get_meet_evaluation_data.__wrapped__
        elif hasattr(get_meet_evaluation_data, 'func'):
            func_to_call = get_meet_evaluation_data.func
        elif hasattr(get_meet_evaluation_data, '_func'):
            func_to_call = get_meet_evaluation_data._func
        elif callable(get_meet_evaluation_data) and not hasattr(get_meet_evaluation_data, 'name'):
            func_to_call = get_meet_evaluation_data
        
        if not func_to_call:
            raise HTTPException(status_code=500, detail="No se pudo acceder a la función get_meet_evaluation_data")
        
        meet_data_json = func_to_call(meet_id)
        meet_data = json.loads(meet_data_json) if isinstance(meet_data_json, str) else meet_data_json
        
        # Obtener información del agente y tareas
        evaluator_agent = create_single_meet_evaluator_agent()
        extraction_task = create_single_meet_extraction_task(evaluator_agent, meet_id)
        evaluation_task = create_single_meet_evaluation_task(evaluator_agent, extraction_task)

        model = "gpt-5-nano"
        # ===== TAREA 1: EXTRACTION TASK =====
        # System message con backstory del agente
        system_message = {
            "role": "system",
            "content": f"""Eres un {evaluator_agent.role}.
            
{evaluator_agent.backstory}

Tu objetivo: {evaluator_agent.goal}"""
        }
        
        # User message para extraction_task
        extraction_user_message = {
            "role": "user",
            "content": extraction_task.description
        }
        
        extraction_messages = [system_message, extraction_user_message]
        extraction_input_tokens = estimate_task_tokens(extraction_messages, model)
        
        # Completion de extraction_task = los datos del meet (que ya tenemos)
        extraction_output = json.dumps(meet_data, indent=2, ensure_ascii=False) if meet_data else ""
        extraction_completion_tokens = estimate_completion_tokens(extraction_output, model)
        
        # ===== DESGLOSE DEL CONTEXTO =====
        context_breakdown = breakdown_context_tokens(meet_data, model)
        
        # Calcular tokens de las descripciones de las tareas y backstory
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        
        # Tokens del backstory (compartido en ambas tareas)
        backstory_tokens = len(enc.encode(system_message["content"]))
        
        # Tokens de descripción de cada tarea
        extraction_task_description_tokens = len(enc.encode(extraction_task.description))
        evaluation_task_description_tokens = len(enc.encode(evaluation_task.description))
        
        # Desglose del completion de extraction_task (los datos del meet)
        extraction_completion_breakdown = breakdown_context_tokens(meet_data, model)
        
        # ===== TAREA 2: EVALUATION TASK =====
        # User message con descripción de la tarea de evaluación + contexto (resultado de extraction_task)
        evaluation_user_message_content = f"""{evaluation_task.description}

## CONTEXTO - DATOS DEL MEET (resultado de la tarea anterior):
{extraction_output}

## SALIDA ESPERADA:
{evaluation_task.expected_output}"""
        
        evaluation_user_message = {
            "role": "user",
            "content": evaluation_user_message_content
        }
        
        evaluation_messages = [system_message, evaluation_user_message]
        evaluation_input_tokens = estimate_task_tokens(evaluation_messages, model)
        
        # Completion de evaluation_task = JSON de evaluación completo
        evaluation_completion_tokens = estimate_completion_tokens(evaluation_task.expected_output, model)
        
        # Desglose del completion de evaluation_task (basado en expected_output)
        # El expected_output es un JSON grande con análisis completo
        evaluation_completion_text = evaluation_task.expected_output
        evaluation_completion_breakdown = {
            "total": evaluation_completion_tokens,
            "estimated_soft_skills": int(evaluation_completion_tokens * 0.30),  # ~30% para análisis de habilidades blandas
            "estimated_technical": int(evaluation_completion_tokens * 0.25),  # ~25% para análisis técnico
            "estimated_jd_analysis": int(evaluation_completion_tokens * 0.15),  # ~15% para análisis de JD
            "estimated_match_evaluation": int(evaluation_completion_tokens * 0.20),  # ~20% para evaluación de match
            "estimated_structure": int(evaluation_completion_tokens * 0.10),  # ~10% para estructura JSON
        }
        
        # ===== TOTALES =====
        total_input_tokens = extraction_input_tokens + evaluation_input_tokens
        total_completion_tokens = extraction_completion_tokens + evaluation_completion_tokens
        
        # Calcular costos separados
        cost_breakdown = estimate_cost(total_input_tokens, total_completion_tokens, model)
        
        # Mostrar estimación detallada
        print(f"\n{'='*60}")
        print(f"📊 ESTIMACIÓN DE TOKENS PARA MEET: {meet_id}")
        print(f"{'='*60}")
        print(f"Modelo: {model}\n")
        
        print(f"📋 TAREA 1: EXTRACTION")
        print(f"  Input tokens: {extraction_input_tokens:,}")
        print(f"  Completion tokens: {extraction_completion_tokens:,}")
        print(f"  Subtotal: {extraction_input_tokens + extraction_completion_tokens:,} tokens")
        
        print(f"\n  🔍 Desglose Input (Tarea 1):")
        print(f"    Backstory del agente: {backstory_tokens:,} tokens (~{backstory_tokens/extraction_input_tokens*100:.1f}%)")
        print(f"    Descripción de la tarea: {extraction_task_description_tokens:,} tokens (~{extraction_task_description_tokens/extraction_input_tokens*100:.1f}%)")
        
        print(f"\n  🔍 Desglose Completion (Tarea 1):")
        print(f"    Conversation data: {extraction_completion_breakdown['conversation_data']:,} tokens (~{extraction_completion_breakdown['conversation_data']/extraction_completion_tokens*100:.1f}%)")
        print(f"    Job description: {extraction_completion_breakdown['job_description']:,} tokens (~{extraction_completion_breakdown['job_description']/extraction_completion_tokens*100:.1f}%)")
        print(f"    Tech stack: {extraction_completion_breakdown['tech_stack']:,} tokens (~{extraction_completion_breakdown['tech_stack']/extraction_completion_tokens*100:.1f}%)")
        print(f"    Resto del JSON: {extraction_completion_breakdown['resto_json']:,} tokens (~{extraction_completion_breakdown['resto_json']/extraction_completion_tokens*100:.1f}%)")
        print(f"    Total datos: {extraction_completion_breakdown['total_context']:,} tokens\n")
        
        print(f"📋 TAREA 2: EVALUATION")
        print(f"  Input tokens: {evaluation_input_tokens:,}")
        print(f"  Completion tokens: {evaluation_completion_tokens:,}")
        print(f"  Subtotal: {evaluation_input_tokens + evaluation_completion_tokens:,} tokens")
        
        print(f"\n  🔍 Desglose Input (Tarea 2):")
        print(f"    Backstory del agente: {backstory_tokens:,} tokens (~{backstory_tokens/evaluation_input_tokens*100:.1f}%)")
        print(f"    Descripción de la tarea: {evaluation_task_description_tokens:,} tokens (~{evaluation_task_description_tokens/evaluation_input_tokens*100:.1f}%)")
        print(f"    Conversation data: {context_breakdown['conversation_data']:,} tokens (~{context_breakdown['conversation_data']/evaluation_input_tokens*100:.1f}%)")
        print(f"    Job description: {context_breakdown['job_description']:,} tokens (~{context_breakdown['job_description']/evaluation_input_tokens*100:.1f}%)")
        print(f"    Tech stack: {context_breakdown['tech_stack']:,} tokens (~{context_breakdown['tech_stack']/evaluation_input_tokens*100:.1f}%)")
        print(f"    Resto del JSON (estructura/metadatos): {context_breakdown['resto_json']:,} tokens (~{context_breakdown['resto_json']/evaluation_input_tokens*100:.1f}%)")
        print(f"    Total contexto: {context_breakdown['total_context']:,} tokens (~{context_breakdown['total_context']/evaluation_input_tokens*100:.1f}%)")
        
        print(f"\n  🔍 Desglose Completion (Tarea 2):")
        print(f"    Análisis habilidades blandas: ~{evaluation_completion_breakdown['estimated_soft_skills']:,} tokens (~{evaluation_completion_breakdown['estimated_soft_skills']/evaluation_completion_tokens*100:.1f}%)")
        print(f"    Análisis técnico: ~{evaluation_completion_breakdown['estimated_technical']:,} tokens (~{evaluation_completion_breakdown['estimated_technical']/evaluation_completion_tokens*100:.1f}%)")
        print(f"    Análisis JD: ~{evaluation_completion_breakdown['estimated_jd_analysis']:,} tokens (~{evaluation_completion_breakdown['estimated_jd_analysis']/evaluation_completion_tokens*100:.1f}%)")
        print(f"    Evaluación de match: ~{evaluation_completion_breakdown['estimated_match_evaluation']:,} tokens (~{evaluation_completion_breakdown['estimated_match_evaluation']/evaluation_completion_tokens*100:.1f}%)")
        print(f"    Estructura JSON: ~{evaluation_completion_breakdown['estimated_structure']:,} tokens (~{evaluation_completion_breakdown['estimated_structure']/evaluation_completion_tokens*100:.1f}%)")
        print(f"    Total completion: {evaluation_completion_tokens:,} tokens\n")
        
        print(f"📊 TOTALES")
        print(f"  Input tokens totales: {total_input_tokens:,}")
        print(f"  Completion tokens totales: {total_completion_tokens:,}")
        print(f"  Total tokens: {cost_breakdown['total_tokens']:,}\n")
        
        print(f"💰 COSTOS")
        print(f"  Costo Input: ${cost_breakdown['input_cost']:.4f} USD")
        print(f"  Costo Completion: ${cost_breakdown['output_cost']:.4f} USD")
        print(f"  Costo Total: ${cost_breakdown['total_cost']:.4f} USD")
        print(f"{'='*60}\n")
        
        evaluation_logger.log_task_complete(
            "API", 
            f"Estimación completada: {cost_breakdown['total_tokens']:,} tokens totales "
            f"({total_input_tokens:,} input + {total_completion_tokens:,} completion) | "
            f"${cost_breakdown['total_cost']:.4f} USD"
        )
        
        return TokenEstimationResponse(
            status="success",
            message=f"Estimación de tokens calculada exitosamente",
            meet_id=meet_id,
            model=model,
            estimated_input_tokens=total_input_tokens,
            estimated_completion_tokens=total_completion_tokens,
            estimated_total_tokens=cost_breakdown['total_tokens'],
            estimated_input_cost_usd=cost_breakdown['input_cost'],
            estimated_completion_cost_usd=cost_breakdown['output_cost'],
            estimated_total_cost_usd=cost_breakdown['total_cost'],
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error al estimar tokens: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("API", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.patch("/update-elevenlabs-agent")
async def update_elevenlabs_agent_endpoint(request: UpdateAgentRequest):
    """
    Endpoint que actualiza SOLO el prompt de un agente de ElevenLabs
    basado en el jd_interview_id (usa la JD actualizada).
    """
    try:
        start_time = datetime.now()
        jd_interview_id = request.jd_interview_id

        evaluation_logger.log_task_start(
            "Actualizar Agente ElevenLabs",
            f"Actualizando prompt para jd_interview_id: {jd_interview_id}"
        )

        required_env_vars = ["SUPABASE_URL", "SUPABASE_KEY", "ELEVENLABS_API_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            error_msg = f"Variables de entorno faltantes: {missing_vars}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

        # 1. Obtener datos del jd_interview (incluye JD y agent_id)
        jd_response = supabase.table("jd_interviews").select("*").eq("id", jd_interview_id).limit(1).execute()
        if not jd_response.data or len(jd_response.data) == 0:
            error_msg = f"No se encontró jd_interview con ID: {jd_interview_id}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        jd_data = jd_response.data[0]
        job_description = jd_data.get("job_description", "")
        interview_name = jd_data.get("interview_name", "")
        client_id = jd_data.get("client_id")
        agent_id = jd_data.get("agent_id")

        if not job_description:
            error_msg = f"El jd_interview {jd_interview_id} no tiene job_description"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        if not agent_id:
            error_msg = f"El jd_interview {jd_interview_id} no tiene agent_id asociado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        if not client_id:
            error_msg = f"El jd_interview {jd_interview_id} no tiene client_id asociado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # 2. Obtener email del cliente (para generar prompt coherente)
        func_to_call = None
        if hasattr(get_client_email, "__wrapped__"):
            func_to_call = get_client_email.__wrapped__
        elif hasattr(get_client_email, "func"):
            func_to_call = get_client_email.func
        elif hasattr(get_client_email, "_func"):
            func_to_call = get_client_email._func
        else:
            error_msg = "No se pudo acceder a la función get_client_email"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        client_email_result = func_to_call(client_id)
        client_email_data = json.loads(client_email_result) if isinstance(client_email_result, str) else client_email_result

        if "error" in client_email_data:
            error_msg = f"Error obteniendo email del cliente: {client_email_data.get('error')}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        sender_email = client_email_data.get("email", "")
        if not sender_email:
            error_msg = f"El cliente {client_id} no tiene email configurado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # 3. Generar nuevo prompt base a partir de la JD actualizada
        prompt_data = generate_elevenlabs_prompt_from_jd(
            interview_name=interview_name,
            job_description=job_description,
            sender_email=sender_email,
        )
        generated_prompt = prompt_data.get("prompt", "").strip()
        if not generated_prompt:
            error_msg = "No se pudo generar un nuevo prompt para ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        # 3b. Asegurar que se mantenga la misma estructura obligatoria de entrevista
        estructura_obligatoria = """

**ESTRUCTURA OBLIGATORIA DE LA ENTREVISTA:**

Debes realizar EXACTAMENTE las siguientes preguntas en este orden:

1. **2 PREGUNTAS DE HABILIDADES BLANDAS:**
   - Realiza 2 preguntas sobre habilidades blandas del candidato
   - Ejemplos: comunicación, trabajo en equipo, liderazgo, resolución de problemas, adaptabilidad, gestión del tiempo
   - Estas preguntas deben evaluar las competencias interpersonales y profesionales del candidato
   - Haz una pregunta a la vez y espera la respuesta antes de continuar

2. **5 PREGUNTAS TÉCNICAS DEL PUESTO:**
   - Realiza 5 preguntas técnicas específicas basadas en la descripción del puesto
   - Las preguntas deben estar directamente relacionadas con las tecnologías, herramientas y conocimientos técnicos mencionados en la descripción del puesto
   - Sé específico y técnico, evaluando el conocimiento real del candidato
   - Haz una pregunta a la vez y espera la respuesta antes de continuar

**REGLAS IMPORTANTES:**
- Mantén un tono profesional pero amigable
- Evalúa las respuestas del candidato de manera objetiva
- Guía la conversación de manera estructurada
- Responde en español de manera clara y concisa
- NO hagas más de 2 preguntas de habilidades blandas
- NO hagas más de 5 preguntas técnicas
- Al finalizar las 7 preguntas, agradece al candidato y cierra la entrevista"""

        full_prompt_text = generated_prompt + estructura_obligatoria

        # 4. Actualizar el agente en ElevenLabs usando solo el prompt
        update_result = update_elevenlabs_agent_prompt(agent_id=str(agent_id), prompt_text=full_prompt_text)
        if not update_result:
            error_msg = "No se pudo actualizar el agente de ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        execution_time = str(datetime.now() - start_time)
        evaluation_logger.log_task_complete(
            "Actualizar Agente ElevenLabs",
            f"Agente {agent_id} actualizado exitosamente en {execution_time}"
        )
        
        # Indexar JD Interview actualizada en knowledge base (indexación incremental)
        try:
            from tools.vector_tools import index_jd_interview
            index_jd_interview(jd_data)
            evaluation_logger.log_task_progress("Actualizar Agente ElevenLabs", f"JD Interview re-indexada en knowledge base: {jd_interview_id}")
        except Exception as index_error:
            # No fallar si falla la indexación
            evaluation_logger.log_error("Actualizar Agente ElevenLabs", f"Error re-indexando JD Interview: {str(index_error)}")

        return {
            "status": "success",
            "message": "Agente de ElevenLabs actualizado correctamente con la JD actualizada",
            "jd_interview_id": jd_interview_id,
            "agent_id": str(agent_id),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error al actualizar agente de ElevenLabs: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("API", error_msg)
        import traceback
        evaluation_logger.log_error("API", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/create-elevenlabs-agent", response_model=CreateAgentResponse)
async def create_elevenlabs_agent_endpoint(request: CreateAgentRequest):
    """
    Endpoint que crea un agente de ElevenLabs basado en un jd_interview_id
    y actualiza el registro en jd_interviews con el agent_id generado.
    
    Args:
        request: Objeto con jd_interview_id del registro a procesar
        
    Returns:
        Respuesta con el estado de la operación y el agent_id creado
    """
    try:
        start_time = datetime.now()
        jd_interview_id = request.jd_interview_id
        
        evaluation_logger.log_task_start("Crear Agente ElevenLabs", f"Creando agente para jd_interview_id: {jd_interview_id}")
        
        # Verificar variables de entorno
        required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'ELEVENLABS_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            evaluation_logger.log_error("API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(
                status_code=500, 
                detail=f"Variables de entorno faltantes: {missing_vars}"
            )
        
        # Conectar a Supabase
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        
        # 1. Obtener datos del jd_interview
        print(f"📊 Obteniendo datos del jd_interview: {jd_interview_id}")
        jd_response = supabase.table('jd_interviews').select('*').eq('id', jd_interview_id).limit(1).execute()
        
        if not jd_response.data or len(jd_response.data) == 0:
            error_msg = f"No se encontró jd_interview con ID: {jd_interview_id}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
        
        jd_data = jd_response.data[0]
        job_description = jd_data.get('job_description', '')
        interview_name = jd_data.get('interview_name', '')
        client_id = jd_data.get('client_id')
        
        if not job_description:
            error_msg = f"El jd_interview {jd_interview_id} no tiene job_description"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        if not client_id:
            error_msg = f"El jd_interview {jd_interview_id} no tiene client_id asociado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        # 2. Obtener email del cliente
        print(f"📧 Obteniendo email del cliente: {client_id}")
        # Acceder a la función subyacente del Tool
        func_to_call = None
        if hasattr(get_client_email, '__wrapped__'):
            func_to_call = get_client_email.__wrapped__
        elif hasattr(get_client_email, 'func'):
            func_to_call = get_client_email.func
        elif hasattr(get_client_email, '_func'):
            func_to_call = get_client_email._func
        else:
            error_msg = "No se pudo acceder a la función get_client_email"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        client_email_result = func_to_call(client_id)
        client_email_data = json.loads(client_email_result) if isinstance(client_email_result, str) else client_email_result
        
        if 'error' in client_email_data:
            error_msg = f"Error obteniendo email del cliente: {client_email_data.get('error')}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        sender_email = client_email_data.get('email', '')
        if not sender_email:
            error_msg = f"El cliente {client_id} no tiene email configurado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        # 3. Crear agente de ElevenLabs
        print(f"🤖 Creando agente de ElevenLabs...")
        print(f"   - Interview Name: {interview_name}")
        print(f"   - Job Description: {job_description[:100]}...")
        print(f"   - Sender Email: {sender_email}")
        
        # Generar nombre temporal del agente (se actualizará con el generado por CrewAI)
        agent_name_temp = interview_name or f"Agente {jd_interview_id[:8]}"
        
        elevenlabs_result = create_elevenlabs_agent(
            agent_name=agent_name_temp,
            interview_name=interview_name,
            job_description=job_description,
            sender_email=sender_email
        )
        
        if not elevenlabs_result:
            error_msg = "No se pudo crear el agente de ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        # 4. Extraer agent_id del resultado
        agent_id_elevenlabs = None
        agent_name_final = agent_name_temp
        
        if isinstance(elevenlabs_result, dict):
            # Intentar obtener el agent_id de diferentes campos posibles
            agent_id_elevenlabs = (
                elevenlabs_result.get('agent_id') or 
                elevenlabs_result.get('id') or 
                elevenlabs_result.get('agentId') or
                elevenlabs_result.get('_id')
            )
            # Obtener nombre del agente si está disponible
            agent_name_final = elevenlabs_result.get('name', agent_name_temp)
        elif hasattr(elevenlabs_result, 'agent_id'):
            agent_id_elevenlabs = elevenlabs_result.agent_id
        elif hasattr(elevenlabs_result, 'id'):
            agent_id_elevenlabs = elevenlabs_result.id
        
        if not agent_id_elevenlabs:
            error_msg = "No se pudo extraer el agent_id del resultado de ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        print(f"✅ Agente creado exitosamente:")
        print(f"   - Agent ID: {agent_id_elevenlabs}")
        print(f"   - Agent Name: {agent_name_final}")
        
        # 5. Actualizar el registro en jd_interviews con el agent_id
        print(f"💾 Actualizando jd_interviews con agent_id...")
        update_data = {
            'agent_id': str(agent_id_elevenlabs)
        }
        
        update_response = supabase.table('jd_interviews').update(update_data).eq('id', jd_interview_id).execute()
        
        if not update_response.data:
            error_msg = f"No se pudo actualizar el registro jd_interview {jd_interview_id}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        print(f"✅ Registro actualizado exitosamente en jd_interviews")
        
        # Indexar JD Interview actualizada en knowledge base (indexación incremental)
        try:
            from tools.vector_tools import index_jd_interview
            updated_jd = update_response.data[0]
            index_jd_interview(updated_jd)
            evaluation_logger.log_task_progress("Crear Agente ElevenLabs", f"JD Interview re-indexada en knowledge base: {jd_interview_id}")
        except Exception as index_error:
            # No fallar si falla la indexación
            evaluation_logger.log_error("Crear Agente ElevenLabs", f"Error re-indexando JD Interview: {str(index_error)}")
        
        execution_time = str(datetime.now() - start_time)
        evaluation_logger.log_task_complete("Crear Agente ElevenLabs", f"Agente creado y guardado exitosamente: {agent_id_elevenlabs}")
        
        return CreateAgentResponse(
            status="success",
            message=f"Agente de ElevenLabs creado y guardado exitosamente",
            timestamp=datetime.now().isoformat(),
            jd_interview_id=jd_interview_id,
            agent_id=str(agent_id_elevenlabs),
            agent_name=agent_name_final
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error al crear agente de ElevenLabs: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("API", error_msg)
        import traceback
        evaluation_logger.log_error("API", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/chatbot", response_model=ChatbotResponse)
async def chatbot_endpoint(request: ChatbotRequest):
    """
    Endpoint del chatbot que usa búsqueda vectorial (RAG) para responder preguntas
    sobre candidatos, entrevistas y el sistema.
    
    Args:
        request: Objeto con el mensaje del usuario y el historial de conversación
        
    Returns:
        Respuesta del chatbot con contexto relevante de la base de datos
    """
    try:
        start_time = datetime.now()
        message = request.message
        conversation_history = request.conversation_history or []
        
        evaluation_logger.log_task_start("Chatbot", f"Procesando mensaje: {message[:50]}...")
        
        # Verificar variables de entorno
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY no configurada")
        
        # 1. Verificar si hay chunks en la base de datos
        total_chunks = 0
        try:
            supabase = get_supabase_client()
            count_result = supabase.table('knowledge_chunks').select('id', count='exact').limit(1).execute()
            total_chunks = count_result.count if hasattr(count_result, 'count') else 0
            evaluation_logger.log_task_progress("Chatbot", f"Total de chunks en BD: {total_chunks}")
        except Exception as e:
            evaluation_logger.log_error("Chatbot", f"Error contando chunks: {str(e)}")
        
        # 2. Buscar chunks relevantes usando búsqueda vectorial
        similar_chunks = []
        if total_chunks > 0:
            try:
                # Intentar con diferentes thresholds, empezando por el más permisivo
                thresholds = [0.3, 0.4, 0.5]  # Probar con thresholds más bajos
                for threshold in thresholds:
                    similar_chunks = search_similar_chunks(
                        query_text=message,
                        match_threshold=threshold,
                        match_count=10,
                        entity_type_filter=None
                    )
                    if len(similar_chunks) > 0:
                        evaluation_logger.log_task_progress("Chatbot", f"Encontrados {len(similar_chunks)} chunks con threshold {threshold}")
                        break
                    else:
                        evaluation_logger.log_task_progress("Chatbot", f"No se encontraron chunks con threshold {threshold}, intentando siguiente...")
                
                if len(similar_chunks) == 0:
                    evaluation_logger.log_task_progress("Chatbot", "No se encontraron chunks con ningún threshold, pero hay datos en BD")
            except Exception as e:
                evaluation_logger.log_error("Chatbot", f"Error en búsqueda vectorial: {str(e)}")
                import traceback
                evaluation_logger.log_error("Chatbot", f"Traceback: {traceback.format_exc()}")
        else:
            evaluation_logger.log_task_progress("Chatbot", "No hay chunks indexados en la base de datos")
        
        # 3. Construir contexto a partir de los chunks
        context_parts = []
        sources = []
        for chunk in similar_chunks:
            content = chunk.get('content', '')
            entity_type = chunk.get('entity_type', '')
            entity_id = chunk.get('entity_id', '')
            metadata = chunk.get('metadata', {})
            
            context_parts.append(content)
            sources.append({
                'entity_type': entity_type,
                'entity_id': entity_id,
                'metadata': metadata,
                'content_preview': content[:100] + '...' if len(content) > 100 else content
            })
        
        context = "\n\n".join(context_parts) if context_parts else "No se encontró información relevante en la base de datos."
        
        # 4. Construir mensajes para OpenAI
        has_context = len(context_parts) > 0
        
        if has_context:
            system_prompt = """Eres un asistente experto en el sistema de reclutamiento Agora HR. 
Ayudas a los usuarios con preguntas sobre candidatos, entrevistas, matching, y funcionalidades del sistema.

INSTRUCCIONES:
- Responde en español de manera clara y concisa
- Usa el contexto proporcionado para dar respuestas precisas basadas en los datos reales
- Proporciona información específica de los candidatos, tecnologías, experiencias, etc. cuando esté disponible en el contexto
- Sé profesional y amigable
- Si el contexto menciona IDs o datos técnicos, puedes referenciarlos pero enfócate en la información útil para el usuario"""
        elif total_chunks > 0:
            # Hay chunks pero no se encontraron resultados relevantes
            system_prompt = """Eres un asistente experto en el sistema de reclutamiento Agora HR. 
Ayudas a los usuarios con preguntas sobre candidatos, entrevistas, matching, y funcionalidades del sistema.

IMPORTANTE: Hay datos indexados en la base de conocimiento ({total_chunks} chunks), pero la búsqueda no encontró resultados relevantes para esta consulta específica.

INSTRUCCIONES:
- Responde en español de manera clara y concisa
- Explica que hay datos indexados pero que la consulta no encontró coincidencias específicas
- Sugiere reformular la pregunta de manera diferente
- Proporciona información general sobre cómo funciona el sistema
- Sé profesional y amigable""".format(total_chunks=total_chunks)
        else:
            system_prompt = """Eres un asistente experto en el sistema de reclutamiento Agora HR. 
Ayudas a los usuarios con preguntas sobre candidatos, entrevistas, matching, y funcionalidades del sistema.

IMPORTANTE: Actualmente no hay datos indexados en la base de conocimiento, por lo que no puedo acceder a información específica de candidatos o entrevistas.

INSTRUCCIONES:
- Responde en español de manera clara y concisa
- Explica que los datos aún no están indexados y que necesita ejecutar el script de indexación inicial
- Proporciona información general sobre cómo funciona el sistema
- Sé profesional y amigable
- Sugiere que ejecute el script: python agents/candidate-evaluation/scripts/index_initial_data.py"""
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Agregar historial de conversación
        for msg in conversation_history[-5:]:  # Últimos 5 mensajes
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role in ['user', 'assistant'] and content:
                messages.append({"role": role, "content": content})
        
        # Agregar contexto y pregunta actual
        if context_parts:
            messages.append({
                "role": "system",
                "content": f"CONTEXTO RELEVANTE DE LA BASE DE DATOS:\n{context}\n\nUsa esta información para responder la pregunta del usuario de manera específica y detallada."
            })
        else:
            # Si no hay contexto, agregar información sobre el estado del sistema
            messages.append({
                "role": "system",
                "content": "NOTA: No se encontraron datos indexados en la base de conocimiento. Esto significa que aún no se han indexado los candidatos y JD Interviews. Para que el chatbot funcione correctamente, es necesario ejecutar el script de indexación inicial."
            })
        
        messages.append({
            "role": "user",
            "content": message
        })
        
        # 4. Llamar a OpenAI
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        bot_response = response.choices[0].message.content
        
        # Extraer información de tokens y costos de la respuesta de OpenAI
        usage = response.usage
        model_used = response.model
        
        execution_time = str(datetime.now() - start_time)
        evaluation_logger.log_task_complete("Chatbot", f"Respuesta generada en {execution_time}")
        
        return ChatbotResponse(
            response=bot_response,
            sources=sources[:3] if sources else [],  # Máximo 3 fuentes
            model=model_used,
            estimated_input_tokens=usage.prompt_tokens if usage else None,
            estimated_completion_tokens=usage.completion_tokens if usage else None,
            estimated_total_tokens=usage.total_tokens if usage else None,
            estimated_input_cost_usd=None,  # Opcional, se puede calcular después
            estimated_completion_cost_usd=None,  # Opcional, se puede calcular después
            estimated_total_cost_usd=None,  # Opcional, se puede calcular después
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error en chatbot: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("Chatbot", error_msg)
        import traceback
        evaluation_logger.log_error("Chatbot", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/get-candidate-info/{candidate_id}", response_model=CandidateInfoResponse)
async def get_candidate_info_by_id(
    candidate_id: str,
    include_related: bool = True
):
    """
    Endpoint para obtener información de candidatos por ID (path parameter).
    Diseñado para ser usado como herramienta por ElevenLabs Agents.
    
    Args:
        candidate_id: ID único del candidato (UUID) - path parameter
        include_related: Si True, incluye información de meets y evaluaciones relacionadas
        
    Returns:
        Información del candidato con datos completos
    """
    return await get_candidate_info(
        candidate_id=candidate_id,
        meet_id=None,
        token=None,
        email=None,
        name=None,
        include_related=include_related
    )

@app.get("/get-candidate-info", response_model=CandidateInfoResponse)
async def get_candidate_info(
    candidate_id: Optional[str] = None,
    meet_id: Optional[str] = None,
    token: Optional[str] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    include_related: bool = True
):
    """
    Endpoint para obtener información de candidatos.
    Diseñado para ser usado como herramienta por ElevenLabs Agents.
    
    Args:
        candidate_id: ID único del candidato (UUID)
        meet_id: ID del meet (obtiene el candidate_id desde el meet)
        token: Token del meet (obtiene el candidate_id desde el meet)
        email: Email del candidato
        name: Nombre del candidato (puede devolver múltiples resultados)
        include_related: Si True, incluye información de meets y evaluaciones relacionadas
        
    Returns:
        Información del candidato(s) con datos completos
    """
    try:
        start_time = datetime.now()
        evaluation_logger.log_task_start("Get Candidate Info", f"Buscando candidato - id: {candidate_id}, meet_id: {meet_id}, token: {token}, email: {email}, name: {name}")
        
        # Validar que se proporcione al menos un parámetro
        if not candidate_id and not meet_id and not token and not email and not name:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionarse al menos uno de los siguientes parámetros: candidate_id, meet_id, token, email, o name"
            )
        
        supabase = get_supabase_client()
        candidates_data = []
        
        # Limpiar y validar UUIDs de entrada
        cleaned_candidate_id = clean_uuid(candidate_id)
        cleaned_meet_id = clean_uuid(meet_id)
        cleaned_token = token.strip() if token else None
        
        resolved_candidate_id = cleaned_candidate_id
        
        # Si se proporciona meet_id o token, obtener el candidate_id desde el meet
        if cleaned_meet_id or cleaned_token:
            evaluation_logger.log_task_progress("Get Candidate Info", f"Obteniendo candidate_id desde meet - meet_id: {cleaned_meet_id}, token: {cleaned_token}")
            try:
                meet_query = supabase.table('meets').select('candidate_id')
                if cleaned_meet_id:
                    meet_query = meet_query.eq('id', cleaned_meet_id)
                elif cleaned_token:
                    meet_query = meet_query.eq('token', cleaned_token)
                
                meet_response = meet_query.limit(1).execute()
                
                if meet_response.data and len(meet_response.data) > 0:
                    candidate_id_from_meet = meet_response.data[0].get('candidate_id')
                    # Limpiar también el candidate_id obtenido de la BD
                    resolved_candidate_id = clean_uuid(candidate_id_from_meet) if candidate_id_from_meet else None
                    evaluation_logger.log_task_progress("Get Candidate Info", f"Candidate ID obtenido desde meet: {resolved_candidate_id}")
                else:
                    evaluation_logger.log_task_progress("Get Candidate Info", "No se encontró el meet con los parámetros proporcionados")
            except Exception as e:
                evaluation_logger.log_error("Get Candidate Info", f"Error obteniendo candidate_id desde meet: {str(e)}")
        
        # Buscar por candidate_id (prioridad - puede venir directamente o desde meet)
        if resolved_candidate_id:
            evaluation_logger.log_task_progress("Get Candidate Info", f"Buscando por ID: {resolved_candidate_id}")
            response = supabase.table('candidates').select('*').eq('id', resolved_candidate_id).limit(1).execute()
            if response.data:
                candidates_data = response.data
        # Buscar por email
        elif email:
            evaluation_logger.log_task_progress("Get Candidate Info", f"Buscando por email: {email}")
            response = supabase.table('candidates').select('*').eq('email', email).limit(1).execute()
            if response.data:
                candidates_data = response.data
        # Buscar por name (puede devolver múltiples)
        elif name:
            evaluation_logger.log_task_progress("Get Candidate Info", f"Buscando por nombre: {name}")
            response = supabase.table('candidates').select('*').ilike('name', f'%{name}%').limit(10).execute()
            if response.data:
                candidates_data = response.data
        
        if not candidates_data:
            evaluation_logger.log_task_complete("Get Candidate Info", "No se encontraron candidatos")
            return CandidateInfoResponse(
                status="not_found",
                message="No se encontraron candidatos con los criterios proporcionados",
                timestamp=datetime.now().isoformat()
            )
        
        # Procesar candidatos - Respuesta acortada: solo nombre, skills y experiencia
        processed_candidates = []
        for candidate_row in candidates_data:
            # Extraer nombre completo
            full_name = candidate_row.get('name', '')
            
            # Extraer skills (tech_stack)
            tech_stack = candidate_row.get('tech_stack', [])
            skills = tech_stack if isinstance(tech_stack, list) else []
            
            # Extraer experiencia desde observations
            observations = candidate_row.get('observations', {})
            experience = None
            if isinstance(observations, dict):
                # Buscar work_experience en observations
                work_experience = observations.get('work_experience')
                if work_experience:
                    experience = work_experience
                # Si no hay work_experience, intentar con otros campos relevantes
                elif observations.get('other'):
                    experience = observations.get('other')
            
            # Construir respuesta simplificada
            candidate_info = {
                "name": full_name,
                "skills": skills,
                "experience": experience
            }
            
            processed_candidates.append(candidate_info)
        
        execution_time = str(datetime.now() - start_time)
        evaluation_logger.log_task_complete("Get Candidate Info", f"Información obtenida exitosamente en {execution_time}")
        
        # Si es búsqueda por ID, meet_id, token o email (un solo resultado)
        if resolved_candidate_id or candidate_id or meet_id or token or email:
            return CandidateInfoResponse(
                status="success",
                message=f"Información del candidato obtenida exitosamente",
                timestamp=datetime.now().isoformat(),
                candidate=processed_candidates[0] if processed_candidates else None
            )
        # Si es búsqueda por nombre (múltiples resultados)
        else:
            return CandidateInfoResponse(
                status="success",
                message=f"Se encontraron {len(processed_candidates)} candidatos",
                timestamp=datetime.now().isoformat(),
                candidates=processed_candidates
            )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error obteniendo información del candidato: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("Get Candidate Info", error_msg)
        import traceback
        evaluation_logger.log_error("Get Candidate Info", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)