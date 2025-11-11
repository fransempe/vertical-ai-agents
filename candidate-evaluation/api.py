#!/usr/bin/env python3
"""
API simple para disparar el proceso de análisis de candidatos
"""

import os
import json
import base64
import re
import requests
from datetime import datetime
from contextlib import asynccontextmanager
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
from uuid import UUID


GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "")
GRAPH_CLIENT_STATE = os.getenv("GRAPH_CLIENT_STATE", "")  # Debe coincidir con el usado al crear la suscripción
GRAPH_SCOPE = os.getenv("GRAPH_SCOPE", "https://graph.microsoft.com/.default")
GRAPH_BASE = os.getenv("GRAPH_BASE", "https://graph.microsoft.com/v1.0")
OUTLOOK_USER_ID = os.getenv("OUTLOOK_USER_ID", "")


# ====== Validations ======

def _is_valid_uuid(value: str | None) -> bool:
    if not value or not isinstance(value, (str, bytes)):
        return False
    try:
        UUID(str(value))
        return True
    except Exception:
        return False


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

class CVAnalysisResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str = None
    filename: str = None
    candidate_data: dict = None
    candidate_created: bool | None = None
    candidate_error: str | None = None
    candidate_result: dict = None
    candidate_status: str | None = None

class MatchingResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str = None
    matches: list = None
    total_matches: int = None

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
            if not _is_valid_uuid(jd_interview_id):
                evaluation_logger.log_error("API", f"jd_interview_id inválido recibido: {jd_interview_id}")
                raise HTTPException(status_code=400, detail=f"jd_interview_id inválido: {jd_interview_id}")
            evaluation_logger.log_task_start("API", f"Iniciando proceso de análisis filtrado por jd_interview_id: {jd_interview_id}")
        else:
            evaluation_logger.log_task_start("API", "Iniciando proceso de análisis completo")

        # Preparar variables de evaluación (se insertará al final)
        evaluation_id = None
        client_id = None
        
        result = None

        client_email = None
        previous_report_email = os.environ.get("REPORT_TO_EMAIL")
        email_override_set = False

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

            # Ejecutar el crew y obtener resultado
            result = crew.kickoff()
            
            # Calcular tiempo de ejecución
            end_time = datetime.now()
            execution_time = str(end_time - start_time)
            
            evaluation_logger.log_task_complete("API", f"Proceso completado en {execution_time}")
            
            try:
                # Si es un CrewOutput, extraer su contenido
                if hasattr(result, 'raw'):
                    try:
                        # Intentar parsear el raw como JSON
                        result_dict = json.loads(result.raw)
                    except json.JSONDecodeError:
                        # Si no es JSON válido, crear un dict con el contenido raw
                        result_dict = {"raw_result": result.raw}
                else:
                    # Si no es CrewOutput, intentar convertir a dict
                    try:
                        result_dict = json.loads(str(result))
                    except json.JSONDecodeError:
                        result_dict = {"raw_result": str(result)}
            except Exception:
                # Fallback en caso de cualquier error
                result_dict = {"raw_result": str(result)}
    
            return AnalysisResponse(
                status="success",
                message="Análisis completado exitosamente",
                timestamp=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                execution_time=execution_time,
                results_file=None,
                result=result_dict,
                jd_interview_id=jd_interview_id,
                evaluation_id=None,
            )
        finally:
            if email_override_set:
                if previous_report_email is None:
                    os.environ.pop("REPORT_TO_EMAIL", None)
                else:
                    os.environ["REPORT_TO_EMAIL"] = previous_report_email
                evaluation_logger.log_task_progress("API", "Email del cliente restaurado al valor previo en REPORT_TO_EMAIL")
        
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
        crew = create_cv_analysis_crew(request.filename)
        
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

@app.post("/match-candidates", response_model=MatchingResponse)
async def match_candidates():
    """
    Endpoint para realizar matching entre candidatos (tech_stack) y entrevistas (job_description)
    
    Returns:
        MatchingResponse con los matches encontrados entre candidatos y entrevistas
    """
    try:
        start_time = datetime.now()
        
        # Verificar variables de entorno
        required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            evaluation_logger.log_error("Matching API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(
                status_code=500, 
                detail=f"Variables de entorno faltantes: {missing_vars}"
            )
        
        # Log inicio del proceso
        evaluation_logger.log_task_start("Matching API", "Iniciando proceso de matching")
        
        # Crear y ejecutar crew de matching
        crew = create_candidate_matching_crew()
        result = crew.kickoff()
        
        # Calcular tiempo de ejecución
        end_time = datetime.now()
        execution_time = str(end_time - start_time)
        
        evaluation_logger.log_task_complete("Matching API", f"Matching completado en {execution_time}")
        
        # Procesar resultado
        result_text = str(result)
        if hasattr(result, 'raw'):
            result_text = result.raw
        
        # Log del resultado para debugging
        evaluation_logger.log_task_progress("Matching API", f"Resultado del agente: {result_text[:500]}...")
        
        # Intentar parsear el resultado como JSON
        matches_data = None
        try:
            matches_data = json.loads(result_text)
            evaluation_logger.log_task_progress("Matching API", "Resultado parseado como JSON exitosamente")
        except json.JSONDecodeError:
            evaluation_logger.log_task_progress("Matching API", "Resultado no es JSON válido, intentando extraer datos del texto")
            
            # Intentar extraer JSON del texto usando regex
            import re
            json_pattern = r'\{.*"matches".*\}'
            json_matches = re.findall(json_pattern, result_text, re.DOTALL)
            
            if json_matches:
                try:
                    matches_data = json.loads(json_matches[0])
                    evaluation_logger.log_task_progress("Matching API", "JSON extraído del texto exitosamente")
                except json.JSONDecodeError:
                    evaluation_logger.log_task_progress("Matching API", "No se pudo extraer JSON válido del texto")
                    matches_data = None
        
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
        
        return MatchingResponse(
            status="success",
            message="Matching de candidatos completado exitosamente",
            timestamp=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=execution_time,
            matches=matches_list,
            total_matches=total_matches
        )
        
    except Exception as e:
        evaluation_logger.log_error("Matching API", f"Error en matching: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el matching: {str(e)}")

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

@app.post("/evaluate-meet", response_model=AnalysisResponse)
async def evaluate_single_meet(request: SingleMeetRequest):
    """
    Endpoint que evalúa un solo meet para determinar si el candidato es un posible match
    basado en la JD del meet
    
    Args:
        request: Objeto con meet_id del meet a evaluar
    """
    try:
        meet_id = request.meet_id
        evaluation_logger.log_task_start("API", f"Iniciando evaluación de meet: {meet_id}")
        
        start_time = datetime.now()
        
        # Crear y ejecutar crew de evaluación individual
        crew = create_single_meet_evaluation_crew(meet_id)
        
        print("=" * 80)
        print("🚀 INICIANDO EJECUCIÓN DEL CREW (Single Meet Evaluation)")
        print("=" * 80)
        
        result = crew.kickoff()
        
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
                full_result = json.loads(result_str)
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
        result_data = {
            "final_recommendation": None,
            "justification": None,
            "is_potential_match": None,
            "compatibility_score": None
        }
        
        # Buscar en match_evaluation
        if isinstance(full_result, dict):
            match_eval = full_result.get("match_evaluation", {})
            if isinstance(match_eval, dict):
                result_data["final_recommendation"] = match_eval.get("final_recommendation")
                result_data["justification"] = match_eval.get("justification")
                result_data["is_potential_match"] = match_eval.get("is_potential_match")
                result_data["compatibility_score"] = match_eval.get("compatibility_score")
        
        # Si es un posible match, enviar email al cliente del JD interview
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
                            
                            # Crear cuerpo del email
                            body = f"""
Hola,

Te informamos que hemos identificado un candidato potencial para la posición: **{interview_name}**

📊 **RESULTADO DE LA EVALUACIÓN:**

🎯 **Match Potencial:** ✅ SÍ
📈 **Score de Compatibilidad:** {result_data.get('compatibility_score', 0)}%
📋 **Recomendación Final:** {result_data.get('final_recommendation', 'N/A')}

---

👤 **DATOS DEL CANDIDATO:**
• Nombre: {candidate_data.get('name', 'N/A')}
• Email: {candidate_data.get('email', 'N/A')}
• Teléfono: {candidate_data.get('phone', 'N/A')}
• Tech Stack: {candidate_data.get('tech_stack', 'N/A')}
• CV URL: {candidate_data.get('cv_url', 'N/A')}

---

💬 **ANÁLISIS DE CONVERSACIÓN:**

**Habilidades Blandas:**
{format_soft_skills(conversation_data.get('soft_skills', {}))}

**Evaluación Técnica:**
• Nivel de Conocimiento: {conversation_data.get('technical_assessment', {}).get('knowledge_level', 'N/A')}
• Experiencia Práctica: {conversation_data.get('technical_assessment', {}).get('practical_experience', 'N/A')}

**Preguntas Técnicas:**
{format_technical_questions(conversation_data.get('technical_assessment', {}).get('technical_questions', []))}

---

📝 **JUSTIFICACIÓN:**
{result_data.get('justification', 'No disponible')}

---

💬 **CONVERSACIÓN COMPLETA:**

{conversation_text}

---

🏢 **DATOS DEL CLIENTE:**
• Cliente: {client_name}
• Responsable: {client_responsible}
• Teléfono: {client_phone}
• Email: {client_email}

---

🔍 **DETALLES ADICIONALES:**
• Meet ID: {meet_id}
• JD Interview ID: {jd_interviews_id}

Saludos,
Sistema de Evaluación de Candidatos
                            """
                            
                            # Enviar email
                            email_api_url = os.getenv("EMAIL_API_URL", "http://127.0.0.1:8004/send-simple-email")
                            
                            payload = {
                                "to_email": client_email,
                                "subject": subject,
                                "body": body
                            }
                            
                            response = requests.post(
                                email_api_url,
                                json=payload,
                                headers={'Content-Type': 'application/json'},
                                timeout=30
                            )
                            
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
        
        return AnalysisResponse(
            status="success",
            message=f"Evaluación del meet {meet_id} completada exitosamente" + (f" - Email enviado" if email_sent else ""),
            timestamp=end_time.strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=str(execution_time),
            result=result_data
        )
        
    except Exception as e:
        evaluation_logger.log_error("API", f"Error en evaluación de meet: {str(e)}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)