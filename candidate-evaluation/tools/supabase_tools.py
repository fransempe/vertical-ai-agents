import os
import json
import requests
import time
from datetime import datetime
from typing import List, Dict, Any
from crewai.tools import tool
from supabase import create_client, Client
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.logger import evaluation_logger

load_dotenv()

def _fetch_url_with_retries(url: str, max_retries: int = 3) -> requests.Response:
    """
    Función auxiliar para hacer fetch de URLs con reintentos limitados
    
    Args:
        url: URL a obtener
        max_retries: Número máximo de reintentos
        
    Returns:
        Response object de requests
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Backoff exponencial: 1s, 2s, 4s
                evaluation_logger.log_task_progress("Análisis Job Description", f"Reintento {attempt + 1}/{max_retries} en {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                raise e
        except requests.exceptions.RequestException as e:
            raise e
    
    raise requests.exceptions.RequestException("Máximo número de reintentos alcanzado")

class SupabaseExtractorTool:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase = create_client(url, key)

@tool
def extract_supabase_conversations(limit: int = 100) -> str:
    """
    Extrae datos de conversaciones de Supabase con joins a candidatos y meets.
    
    Args:
        limit: Número máximo de conversaciones a extraer
        
    Returns:
        JSON string con los datos de conversaciones
    """
    try:
        evaluation_logger.log_task_start("Extracción de Conversaciones", "Data Extractor")
        evaluation_logger.log_task_progress("Extracción de Conversaciones", f"Conectando a Supabase, límite: {limit}")
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)
        
        response = supabase.table('conversations').select(
            '''
            meet_id,
            candidate_id,
            conversation_data,
            candidates(id, name, email, phone, cv_url, tech_stack)
            '''
        ).limit(limit).execute()
        
        conversations = []
        for row in response.data:
            conversation = {
                "meet_id": row['meet_id'],
                "candidate_id": row['candidate_id'],
                "conversation_data": row['conversation_data'],
                "candidate": {
                    "id": row['candidates']['id'] if row['candidates'] else None,
                    "name": row['candidates']['name'] if row['candidates'] else None,
                    "email": row['candidates']['email'] if row['candidates'] else None,
                    "phone": row['candidates']['phone'] if row['candidates'] else None,
                    "cv_url": row['candidates']['cv_url'] if row['candidates'] else None,
                    "tech_stack": row['candidates']['tech_stack'] if row['candidates'] else None
                }
            }
            conversations.append(conversation)
        
        evaluation_logger.log_task_complete("Extracción de Conversaciones", f"{len(conversations)} conversaciones extraídas exitosamente")
        return json.dumps(conversations, indent=2)
        
    except Exception as e:
        evaluation_logger.log_error("Extracción de Conversaciones", str(e))
        return json.dumps({"error": f"Error extracting data: {str(e)}"}, indent=2)

@tool
def fetch_job_description(job_description: str) -> str:
    """
    Obtiene la URL de la descripción del trabajo desde el campo job_description de la tabla meets.
    
    Args:
        job_description: URL de la descripción del trabajo
        
    Returns:
        JSON string con el contenido de la descripción del trabajo
    """
    try:
        evaluation_logger.log_task_start("Análisis Job Description", "Job Description Analyzer")
        evaluation_logger.log_task_progress("Análisis Job Description", f"Obteniendo contenido desde: {job_description}")
        
        # Validar URL
        if not job_description or not job_description.strip():
            evaluation_logger.log_error("Análisis Job Description", "URL vacía o inválida")
            return json.dumps({"error": "job_description vacía o inválida", "success": False}, indent=2)
        
        # Verificar que sea una URL válida
        if not job_description.startswith(('http://', 'https://')):
            evaluation_logger.log_error("Análisis Job Description", "URL no válida - debe empezar con http:// o https://")
            return json.dumps({"error": "URL no válida - debe empezar con http:// o https://", "success": False}, indent=2)
        
        # Usar la función auxiliar con reintentos limitados
        response = _fetch_url_with_retries(job_description, max_retries=3)
        
        # Verificar que el contenido sea HTML/texto
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            evaluation_logger.log_error("Análisis Job Description", f"Tipo de contenido no soportado: {content_type}")
            return json.dumps({"error": f"Tipo de contenido no soportado: {content_type}", "success": False}, indent=2)
        
        evaluation_logger.log_task_complete("Análisis Job Description", f"Contenido obtenido exitosamente, {len(response.text)} caracteres")
        
        return json.dumps({
            "job_description": job_description,
            "content": response.text,
            "status_code": response.status_code,
            "content_type": response.headers.get('content-type', ''),
            "success": True
        }, indent=2)
        
    except requests.exceptions.Timeout:
        evaluation_logger.log_error("Análisis Job Description", "Timeout - la URL tardó demasiado en responder")
        return json.dumps({"error": "Timeout - la URL tardó demasiado en responder", "success": False}, indent=2)
    except requests.exceptions.ConnectionError:
        evaluation_logger.log_error("Análisis Job Description", "Error de conexión - no se pudo conectar a la URL")
        return json.dumps({"error": "Error de conexión - no se pudo conectar a la URL", "success": False}, indent=2)
    except requests.exceptions.HTTPError as e:
        evaluation_logger.log_error("Análisis Job Description", f"Error HTTP {e.response.status_code}: {str(e)}")
        return json.dumps({"error": f"Error HTTP {e.response.status_code}: {str(e)}", "success": False}, indent=2)
    except requests.exceptions.RequestException as e:
        evaluation_logger.log_error("Análisis Job Description", f"Error de petición: {str(e)}")
        return json.dumps({"error": f"Error fetching job description: {str(e)}", "success": False}, indent=2)
    except Exception as e:
        evaluation_logger.log_error("Análisis Job Description", f"Error inesperado: {str(e)}")
        return json.dumps({"error": f"Unexpected error: {str(e)}", "success": False}, indent=2)

@tool
def send_evaluation_email(subject: str, body: str) -> str:
    """
    Envía un email con los resultados de evaluación usando la API local.
    
    Args:
        subject: Asunto del email
        body: Cuerpo del email con los resultados
        jd_interview_id: ID del jd_interview asociado al análisis
    Returns:
        JSON string con el resultado del envío
    """
    try:
        evaluation_logger.log_task_start("Envío de Email", "Email Sender")
        evaluation_logger.log_task_progress("Envío de Email", f"Preparando email: {subject}")
        
        email_api_url = os.getenv("EMAIL_API_URL", "http://127.0.0.1:8004/send-simple-email")
        
        # Detectar destinatario dinámicamente desde el cuerpo del reporte si hay algún email
        to_email = os.getenv("REPORT_TO_EMAIL", "")
        try:
            import re as _re
            # Buscar el primer email en el cuerpo
            email_match = _re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", body or "")
            if not to_email and email_match:
                to_email = email_match.group(0)
        except Exception:
            pass
        # Fallback final si no se detecta ninguno
        if not to_email:
            to_email = "flocklab.id@gmail.com"
        
        payload = {
            "to_email": to_email,
            "subject": subject,
            "body": body
        }
        
        evaluation_logger.log_task_progress("Envío de Email", f"Enviando a {to_email} via {email_api_url}")
        
        response = requests.post(
            email_api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        response.raise_for_status()
        
        evaluation_logger.log_email_sent(to_email, subject, "success")
        evaluation_logger.log_task_complete("Envío de Email", f"Email enviado exitosamente con código {response.status_code}")
        
        return json.dumps({
            "status": "success",
            "message": f"Email enviado exitosamente a {to_email}",
            "subject": subject,
            "status_code": response.status_code
        }, indent=2)
        
    except requests.exceptions.RequestException as e:
        evaluation_logger.log_email_sent("flocklab.id@gmail.com", subject, f"error: {str(e)}")
        evaluation_logger.log_error("Envío de Email", f"Error de petición: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error enviando email: {str(e)}"
        }, indent=2)
    except Exception as e:
        evaluation_logger.log_error("Envío de Email", f"Error inesperado: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error inesperado: {str(e)}"
        }, indent=2)

@tool
def send_match_notification_email(to_email: str, subject: str, body: str) -> str:
    """
    Envía un email de notificación de match a un destinatario específico.
    
    Args:
        to_email: Email del destinatario
        subject: Asunto del email
        body: Cuerpo del email con los resultados
        
    Returns:
        JSON string con el resultado del envío
    """
    try:
        evaluation_logger.log_task_start("Envío de Email de Match", "Match Email Sender")
        evaluation_logger.log_task_progress("Envío de Email de Match", f"Preparando email: {subject}")
        
        email_api_url = os.getenv("EMAIL_API_URL", "http://127.0.0.1:8004/send-simple-email")
        
        payload = {
            "to_email": to_email,
            "subject": subject,
            "body": body
        }
        
        evaluation_logger.log_task_progress("Envío de Email de Match", f"Enviando a {to_email} via {email_api_url}")
        
        response = requests.post(
            email_api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        response.raise_for_status()
        
        evaluation_logger.log_email_sent(to_email, subject, "success")
        evaluation_logger.log_task_complete("Envío de Email de Match", f"Email enviado exitosamente con código {response.status_code}")
        
        return json.dumps({
            "status": "success",
            "message": f"Email enviado exitosamente a {to_email}",
            "subject": subject,
            "status_code": response.status_code
        }, indent=2)
        
    except requests.exceptions.RequestException as e:
        evaluation_logger.log_email_sent(to_email, subject, f"error: {str(e)}")
        evaluation_logger.log_error("Envío de Email de Match", f"Error de petición: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error enviando email: {str(e)}"
        }, indent=2)
    except Exception as e:
        evaluation_logger.log_error("Envío de Email de Match", f"Error inesperado: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error inesperado: {str(e)}"
        }, indent=2)

@tool
def get_all_jd_interviews() -> str:
    """
    Obtiene TODAS las entrevistas de la tabla jd_interviews para matching.
    
    Returns:
        JSON string con todos los datos de jd_interviews
    """
    try:
        evaluation_logger.log_task_start("Obtener Todas las JD Interviews", "JD Interviews Extractor")
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)
        
        # Obtener TODAS las entrevistas
        response = supabase.table('jd_interviews').select('*').execute()
        
        interviews = []
        for row in response.data:
            interview = {
                "id": row.get('id'),
                "interview_name": row.get('interview_name'),
                "agent_id": row.get('agent_id'),
                "job_description": row.get('job_description'),
                "client_id": row.get('client_id'),
                "created_at": row.get('created_at')
            }
            interviews.append(interview)
        
        evaluation_logger.log_task_complete("Obtener Todas las JD Interviews", f"{len(interviews)} entrevistas obtenidas")
        return json.dumps(interviews, indent=2)
        
    except Exception as e:
        evaluation_logger.log_error("Obtener Todas las JD Interviews", f"Error obteniendo datos: {str(e)}")
        return json.dumps({"error": f"Error obteniendo datos de jd_interviews: {str(e)}"}, indent=2)

@tool
def get_jd_interviews_data(interview_id: str = None) -> str:
    """
    Obtiene datos de la tabla jd_interviews, incluyendo job_description para análisis dinámico.
    
    Args:
        interview_id: ID específico de la entrevista (opcional, si no se proporciona obtiene todas)
        
    Returns:
        JSON string con los datos de jd_interviews
    """
    try:
        evaluation_logger.log_task_start("Obtener JD Interview Data", "JD Interview Data Extractor")
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)
        
        if interview_id:
            response = supabase.table('jd_interviews').select('*').eq('id', interview_id).execute()
        else:
            response = supabase.table('jd_interviews').select('*').execute()
        
        interviews = []
        for row in response.data:
            interview = {
                "id": row.get('id'),
                "interview_name": row.get('interview_name'),
                "agent_id": row.get('agent_id'),
                "job_description": row.get('job_description'),
                "client_id": row.get('client_id'),
                "created_at": row.get('created_at')
            }
            interviews.append(interview)
        
        evaluation_logger.log_task_complete("Obtener JD Interview Data", f"{len(interviews)} registros obtenidos")
        return json.dumps(interviews, indent=2)
        
    except Exception as e:
        evaluation_logger.log_error("Obtener JD Interview Data", f"Error obteniendo datos: {str(e)}")
        return json.dumps({"error": f"Error obteniendo datos de jd_interviews: {str(e)}"}, indent=2)

@tool
def get_current_date() -> str:
    """
    Obtiene la fecha actual del sistema en formato DD/MM/YYYY para usar en el asunto del email.
    
    Returns:
        String con la fecha actual en formato DD/MM/YYYY
    """
    try:
        current_date = datetime.now()
        formatted_date = current_date.strftime("%d/%m/%Y")
        
        evaluation_logger.log_task_start("Obtener Fecha Actual", "Date Helper")
        evaluation_logger.log_task_complete("Obtener Fecha Actual", f"Fecha obtenida: {formatted_date}")
        
        return json.dumps({
            "current_date": formatted_date,
            "date_format": "DD/MM/YYYY",
            "example_subject": f"Reporte de Evaluación de Candidatos - {formatted_date}"
        }, indent=2)
    except Exception as e:
        evaluation_logger.log_error("Obtener Fecha Actual", f"Error obteniendo fecha: {str(e)}")
        return json.dumps({
            "error": f"Error obteniendo fecha actual: {str(e)}",
            "fallback_date": "18/01/2025"
        }, indent=2)

@tool
def get_conversations_by_jd_interview(jd_interview_id: str, limit: int = 100) -> str:
    """
    Obtiene conversaciones filtradas por jd_interview_id.
    
    Flujo:
    1. Obtener jd_interview por ID
    2. Buscar meets que tengan jd_interviews_id = jd_interview_id
    3. Obtener conversaciones de esos meets
    
    Args:
        jd_interview_id: ID de la entrevista a filtrar
        limit: Número máximo de conversaciones a extraer
        
    Returns:
        JSON string con las conversaciones filtradas
    """
    try:
        evaluation_logger.log_task_start("Obtener Conversaciones por JD Interview", "Conversations Filtered Extractor")
        evaluation_logger.log_task_progress("Obtener Conversaciones por JD Interview", f"Filtrando por jd_interview_id: {jd_interview_id}")
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)
        
        # 1. Obtener jd_interview por ID
        jd_interview_response = supabase.table('jd_interviews').select('*').eq('id', jd_interview_id).execute()
        
        if not jd_interview_response.data:
            evaluation_logger.log_error("Obtener Conversaciones por JD Interview", f"No se encontró jd_interview con ID: {jd_interview_id}")
            return json.dumps({"error": f"No se encontró jd_interview con ID: {jd_interview_id}"}, indent=2)
        
        jd_interview = jd_interview_response.data[0]
        evaluation_logger.log_task_progress("Obtener Conversaciones por JD Interview", f"JD Interview encontrado: {jd_interview.get('interview_name', 'N/A')}")
        
        # 1.5. Obtener datos del cliente usando client_id del jd_interview
        client_id = jd_interview.get('client_id')
        client_data = None
        if client_id:
            try:
                client_response = supabase.table('clients').select('id, name, email, responsible').eq('id', client_id).limit(1).execute()
                if client_response.data and len(client_response.data) > 0:
                    client_data = client_response.data[0]
                    evaluation_logger.log_task_progress("Obtener Conversaciones por JD Interview", f"Cliente encontrado: {client_data.get('name', 'N/A')}")
            except Exception as client_error:
                evaluation_logger.log_error("Obtener Conversaciones por JD Interview", f"Error obteniendo datos del cliente: {str(client_error)}")
        
        # 2. Buscar meets que tengan jd_interviews_id = jd_interview_id
        meets_response = supabase.table('meets').select('*').eq('jd_interviews_id', jd_interview_id).execute()
        
        if not meets_response.data:
            evaluation_logger.log_task_progress("Obtener Conversaciones por JD Interview", f"No se encontraron meets para jd_interview_id: {jd_interview_id}")
            return json.dumps({
                "message": f"No se han presentado candidatos para esta entrevista (jd_interview_id: {jd_interview_id})",
                "jd_interview_id": jd_interview_id,
                "jd_interview_name": jd_interview.get('interview_name'),
                "jd_interview_agent_id": jd_interview.get('agent_id'),
                "client": client_data,
                "conversations": [],
                "total_conversations": 0
            }, indent=2, ensure_ascii=False)
        
        meet_ids = [meet['id'] for meet in meets_response.data]
        evaluation_logger.log_task_progress("Obtener Conversaciones por JD Interview", f"Encontrados {len(meet_ids)} meets")
        
        # 3. Obtener conversaciones de esos meets
        conversations = []
        for meet_id in meet_ids:
            conversations_response = supabase.table('conversations').select(
                '''
                meet_id,
                candidate_id,
                conversation_data,
                candidates(id, name, email, phone, cv_url, tech_stack)
                '''
            ).eq('meet_id', meet_id).limit(limit).execute()
            
            for row in conversations_response.data:
                conversation = {
                    "meet_id": row['meet_id'],
                    "candidate_id": row['candidate_id'],
                    "conversation_data": row['conversation_data'],
                    "candidate": {
                        "id": row['candidates']['id'] if row['candidates'] else None,
                        "name": row['candidates']['name'] if row['candidates'] else None,
                        "email": row['candidates']['email'] if row['candidates'] else None,
                        "phone": row['candidates']['phone'] if row['candidates'] else None,
                        "cv_url": row['candidates']['cv_url'] if row['candidates'] else None,
                        "tech_stack": row['candidates']['tech_stack'] if row['candidates'] else None
                    },
                    "jd_interview_id": jd_interview_id,
                    "jd_interview_name": jd_interview.get('interview_name'),
                    "jd_interview_agent_id": jd_interview.get('agent_id'),
                    "client": client_data
                }
                conversations.append(conversation)
        
        # Si no se encontraron conversaciones, devolver mensaje informativo
        if not conversations:
            evaluation_logger.log_task_progress("Obtener Conversaciones por JD Interview", f"No se encontraron conversaciones para jd_interview_id: {jd_interview_id}")
            return json.dumps({
                "message": f"No se han presentado candidatos para esta entrevista (jd_interview_id: {jd_interview_id})",
                "jd_interview_id": jd_interview_id,
                "jd_interview_name": jd_interview.get('interview_name'),
                "jd_interview_agent_id": jd_interview.get('agent_id'),
                "client": client_data,
                "conversations": [],
                "total_conversations": 0
            }, indent=2, ensure_ascii=False)
            
        print("conversations: ", conversations)
        
        evaluation_logger.log_task_complete("Obtener Conversaciones por JD Interview", f"{len(conversations)} conversaciones filtradas obtenidas")
        return json.dumps(conversations, indent=2, ensure_ascii=False)
        
    except Exception as e:
        evaluation_logger.log_error("Obtener Conversaciones por JD Interview", f"Error obteniendo conversaciones filtradas: {str(e)}")
        return json.dumps({"error": f"Error obteniendo conversaciones filtradas: {str(e)}"}, indent=2)

@tool
def get_meet_evaluation_data(meet_id: str) -> str:
    """
    Obtiene datos completos de un meet específico para evaluación individual.
    Incluye: meet, conversación, candidato y JD interview asociado.
    
    Args:
        meet_id: ID del meet a evaluar
        
    Returns:
        JSON string con todos los datos necesarios para la evaluación
    """
    try:
        evaluation_logger.log_task_start("Obtener Datos de Meet", f"Obteniendo datos del meet: {meet_id}")
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)
        
        # 1. Obtener el meet con su jd_interviews_id
        meet_response = supabase.table('meets').select(
            '''
            *,
            jd_interviews(id, interview_name, agent_id, job_description, client_id, created_at)
            '''
        ).eq('id', meet_id).execute()
        
        if not meet_response.data:
            evaluation_logger.log_error("Obtener Datos de Meet", f"No se encontró el meet con ID: {meet_id}")
            return json.dumps({"error": f"No se encontró el meet con ID: {meet_id}"}, indent=2)
        
        meet = meet_response.data[0]
        
        # 2. Obtener la conversación del meet
        conversation_response = supabase.table('conversations').select(
            '''
            meet_id,
            candidate_id,
            conversation_data,
            candidates(id, name, email, phone, cv_url, tech_stack)
            '''
        ).eq('meet_id', meet_id).execute()
        
        client_response = supabase.table('clients').select('*').eq('id', meet.get('jd_interviews').get('client_id')).execute()
        print("client_id: ", meet.get('jd_interviews').get('client_id'))
        print("client: ", client_response.data)
        
        client_data = None
        if client_response.data and len(client_response.data) > 0:
            client_data = client_response.data[0]
            os.environ["REPORT_TO_EMAIL"] = client_data.get('email')
        else:
            os.environ["REPORT_TO_EMAIL"] = "flocklab.id@gmail.com"
        
        conversation = None
        if conversation_response.data and len(conversation_response.data) > 0:
            row = conversation_response.data[0]
            conversation = {
                "meet_id": row['meet_id'],
                "candidate_id": row['candidate_id'],
                "conversation_data": row['conversation_data'],
                "candidate": {
                    "id": row['candidates']['id'] if row['candidates'] else None,
                    "name": row['candidates']['name'] if row['candidates'] else None,
                    "email": row['candidates']['email'] if row['candidates'] else None,
                    "phone": row['candidates']['phone'] if row['candidates'] else None,
                    "cv_url": row['candidates']['cv_url'] if row['candidates'] else None,
                    "tech_stack": row['candidates']['tech_stack'] if row['candidates'] else None
                }
            }
        
        # 3. Obtener JD interview
        jd_interview = meet.get('jd_interviews', None) if meet.get('jd_interviews') else None
        
        # Construir respuesta completa
        result = {
            "meet": {
                "id": meet.get('id'),
                "jd_interviews_id": meet.get('jd_interviews_id'),
                "created_at": meet.get('created_at'),
                "updated_at": meet.get('updated_at')
            },
            "conversation": conversation,
            "jd_interview": jd_interview,
            "client": client_data
        }
        
        print("resultado de meet completa: ", result)
        
        evaluation_logger.log_task_complete("Obtener Datos de Meet", f"Datos obtenidos exitosamente para meet: {meet_id}")
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        evaluation_logger.log_error("Obtener Datos de Meet", f"Error obteniendo datos: {str(e)}")
        return json.dumps({"error": f"Error obteniendo datos: {str(e)}"}, indent=2)


@tool
def get_candidates_data(limit: int = 100) -> str:
    """
    Obtiene datos de candidatos desde la tabla 'candidates' incluyendo tech_stack.
    
    Args:
        limit: Número máximo de candidatos a extraer
        
    Returns:
        JSON string con los datos de candidatos
    """
    try:
        evaluation_logger.log_task_start("Obtener Candidatos", "Candidates Data Extractor")
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)
        
        response = supabase.table('candidates').select('*').limit(limit).execute()
        
        candidates = []
        for row in response.data:
            candidate = {
                "id": row.get('id'),
                "name": row.get('name'),
                "email": row.get('email'),
                "phone": row.get('phone'),
                "cv_url": row.get('cv_url'),
                "tech_stack": row.get('tech_stack'),
                "created_at": row.get('created_at')
            }
            candidates.append(candidate)
        
        evaluation_logger.log_task_complete("Obtener Candidatos", f"{len(candidates)} candidatos obtenidos")
        return json.dumps(candidates, indent=2)
        
    except Exception as e:
        evaluation_logger.log_error("Obtener Candidatos", f"Error obteniendo datos: {str(e)}")
        return json.dumps({"error": f"Error obteniendo datos de candidates: {str(e)}"}, indent=2)

@tool
def create_candidate(name: str, email: str, phone: str, cv_url: str, tech_stack: str) -> str:
    """
    Crea (o actualiza por email) un candidato en la tabla 'candidates'.

    Args:
        name: Nombre completo del candidato
        email: Email del candidato (clave única preferida)
        phone: Teléfono del candidato
        cv_url: URL del CV (en S3)
        tech_stack: Tecnologías del candidato. Puede ser:
            - JSON array string (e.g. "[\"Python\", \"AWS\"]")
            - Lista separada por comas (e.g. "Python, AWS")

    Returns:
        JSON string con el resultado de la operación
    """
    try:
        evaluation_logger.log_task_start("Crear Candidato", "Supabase")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)

        # Normalizar tech_stack a lista
        parsed_stack = []
        if tech_stack:
            try:
                maybe_json = json.loads(tech_stack)
                if isinstance(maybe_json, list):
                    parsed_stack = [str(x).strip() for x in maybe_json if str(x).strip()]
                else:
                    parsed_stack = [str(maybe_json).strip()]
            except json.JSONDecodeError:
                parsed_stack = [t.strip() for t in tech_stack.split(',') if t.strip()]

        # Construir payload base
        payload = {
            "name": name or None,
            "email": email or None,
            "phone": phone or None,
            "cv_url": cv_url or None,
            "tech_stack": parsed_stack if parsed_stack else None,
        }

        # Validar email básico (si viene)
        email_value = (email or "").strip()
        is_valid_email = False
        if email_value:
            import re
            email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
            is_valid_email = re.match(email_regex, email_value) is not None

        if is_valid_email:
            # Chequear existencia previa por email
            try:
                existing = supabase.table('candidates').select('*').eq('email', email_value).limit(1).execute()
                if existing.data and len(existing.data) > 0:
                    # Ya existe → devolver error explícito
                    return json.dumps({
                        "success": False,
                        "error": "Candidate already exists with this email",
                        "error_type": "AlreadyExists",
                        "email": email_value,
                        "existing": existing.data[0]
                    }, indent=2, ensure_ascii=False)
            except Exception as qe:
                # Si falla la consulta, continuar con insert para no bloquear (pero loggear)
                evaluation_logger.log_error("Crear Candidato", f"Error verificando existencia por email: {str(qe)}")

            # Insertar nuevo registro (no upsert)
            response = supabase.table('candidates').insert(payload).execute()
        else:
            # Email ausente o inválido → se permite dar de alta igual
            response = supabase.table('candidates').insert(payload).execute()

        evaluation_logger.log_task_complete("Crear Candidato", "Registro creado/actualizado en candidates")
        return json.dumps({
            "success": True,
            "action": "upsert" if email else "insert",
            "data": response.data
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        evaluation_logger.log_error("Crear Candidato", f"Error: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"Error creando candidato: {str(e)}"
        }, indent=2)

@tool
def save_interview_evaluation(jd_interview_id: str, summary: str, candidates: str, ranking: str, candidates_count: int = None) -> str:
    """
    Guarda una evaluación de entrevista en la tabla interview_evaluations.
    
    Args:
        jd_interview_id: ID del jd_interview (UUID)
        summary: JSON string con el full_report completo (el informe completo)
        candidates: JSON string con objeto donde cada clave es candidate_id y valor es {name, score, recommendation}
        ranking: JSON string con array de objetos {candidate_id, name, score}
        candidates_count: Cantidad de candidatos (opcional, se calcula si no se proporciona)
        
    Returns:
        JSON string con el resultado de la operación
    """
    try:
        evaluation_logger.log_task_start("Guardar Evaluación", f"Preparando guardado para jd_interview_id: {jd_interview_id}")
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)

        # Obtener client_id desde jd_interviews
        evaluation_logger.log_task_progress("Guardar Evaluación", f"Buscando client_id para jd_interview_id: {jd_interview_id}")
        
        try:
            jd_resp = supabase.table('jd_interviews').select('id, client_id, interview_name').eq('id', jd_interview_id).limit(1).execute()
            
            if jd_resp.data and len(jd_resp.data) > 0:
                jd_record = jd_resp.data[0]
                evaluation_logger.log_task_progress("Guardar Evaluación", f"JD Interview encontrado: {jd_record}")
                client_id = jd_record.get('client_id')
                
                if not client_id:
                    evaluation_logger.log_error("Guardar Evaluación", f"⚠️ jd_interview existe pero client_id es NULL. Record: {jd_record}")
                    return json.dumps({
                        "success": False,
                        "error": "No se pudo determinar client_id para el jd_interview_id proporcionado"
                    }, indent=2)
            else:
                evaluation_logger.log_error("Guardar Evaluación", f"❌ No se encontró jd_interview con id: {jd_interview_id}")
                return json.dumps({
                    "success": False,
                    "error": f"No se encontró jd_interview con id: {jd_interview_id}"
                }, indent=2)
        except Exception as query_error:
            evaluation_logger.log_error("Guardar Evaluación", f"Error consultando jd_interviews: {str(query_error)}")
            return json.dumps({
                "success": False,
                "error": f"Error consultando jd_interviews: {str(query_error)}"
            }, indent=2)

        # Parsear los datos JSON (aceptar tanto strings como objetos)
        try:
            if isinstance(summary, str):
                summary_dict = json.loads(summary)
            elif isinstance(summary, dict):
                summary_dict = summary
            else:
                summary_dict = {}
            
            if isinstance(candidates, str):
                candidates_dict = json.loads(candidates)
            elif isinstance(candidates, dict):
                candidates_dict = candidates
            else:
                candidates_dict = {}
            
            if isinstance(ranking, str):
                ranking_list = json.loads(ranking)
            elif isinstance(ranking, list):
                ranking_list = ranking
            else:
                ranking_list = []
                
            evaluation_logger.log_task_progress("Guardar Evaluación", f"Datos parseados: summary={type(summary_dict).__name__}, candidates={type(candidates_dict).__name__}, ranking={type(ranking_list).__name__}")
        except json.JSONDecodeError as parse_error:
            evaluation_logger.log_error("Guardar Evaluación", f"Error parseando JSON: {str(parse_error)}")
            return json.dumps({
                "success": False,
                "error": f"Error parseando JSON: {str(parse_error)}"
            }, indent=2)
        except Exception as parse_error:
            evaluation_logger.log_error("Guardar Evaluación", f"Error procesando datos: {str(parse_error)}")
            return json.dumps({
                "success": False,
                "error": f"Error procesando datos: {str(parse_error)}"
            }, indent=2)

        # Calcular candidates_count si no se proporciona
        if candidates_count is None:
            if isinstance(candidates_dict, dict):
                candidates_count = len(candidates_dict.keys())
            elif isinstance(candidates_dict, list):
                candidates_count = len(candidates_dict)
            else:
                candidates_count = 0

        # Validar y formatear datos según el formato requerido
        # Validar summary tiene estructura correcta con kpis y notes
        if isinstance(summary_dict, dict):
            # Si ya tiene kpis y notes en formato correcto, mantenerlo
            if 'kpis' in summary_dict and isinstance(summary_dict['kpis'], dict) and 'notes' in summary_dict:
                # Ya está en formato correcto, mantenerlo
                pass
            else:
                # Necesita construir kpis y notes
                original_summary = summary_dict.copy()
                
                # Calcular kpis desde candidates si están disponibles
                if isinstance(candidates_dict, dict) and len(candidates_dict) > 0:
                    scores = []
                    for cand_data in candidates_dict.values():
                        if isinstance(cand_data, dict):
                            score = cand_data.get('score', 0)
                            if isinstance(score, (int, float)):
                                scores.append(score)
                    
                    avg_score = sum(scores) / len(scores) if scores else 0.0
                    completed_interviews = len(candidates_dict)
                    
                    # Construir summary con estructura correcta
                    new_summary = {
                        'kpis': {
                            'completed_interviews': completed_interviews,
                            'avg_score': round(avg_score, 1)
                        },
                        'notes': original_summary.get('notes', f'Evaluación final - {completed_interviews} candidatos evaluados')
                    }
                    # Mantener otros campos del summary original si existen (excepto kpis y notes que ya están)
                    for key, value in original_summary.items():
                        if key not in ['kpis', 'notes']:
                            new_summary[key] = value
                    summary_dict = new_summary
                else:
                    # Si no hay candidates, crear estructura mínima
                    summary_dict = {
                        'kpis': {
                            'completed_interviews': 0,
                            'avg_score': 0.0
                        },
                        'notes': summary_dict.get('notes', 'Evaluación sin candidatos')
                    }
        else:
            # Si summary no es dict, crear estructura desde cero
            completed_interviews = len(candidates_dict.keys()) if isinstance(candidates_dict, dict) else (candidates_count if candidates_count else 0)
            summary_dict = {
                'kpis': {
                    'completed_interviews': completed_interviews,
                    'avg_score': 0.0
                },
                'notes': f'Evaluación final - {completed_interviews} candidatos evaluados'
            }
        
        # Validar candidates - asegurar formato correcto
        if isinstance(candidates_dict, dict):
            formatted_candidates = {}
            for cand_id, cand_data in candidates_dict.items():
                if isinstance(cand_data, dict):
                    formatted_candidates[str(cand_id)] = {
                        'name': str(cand_data.get('name', '')),
                        'score': int(cand_data.get('score', 0)) if isinstance(cand_data.get('score'), (int, float)) else 0,
                        'recommendation': str(cand_data.get('recommendation', 'Condicional'))
                    }
            candidates_dict = formatted_candidates
        
        # Validar ranking - asegurar formato correcto
        if isinstance(ranking_list, list):
            formatted_ranking = []
            for rank_item in ranking_list:
                if isinstance(rank_item, dict):
                    # Extraer campos base
                    candidate_id = str(rank_item.get('candidate_id', ''))
                    name = str(rank_item.get('name', ''))
                    score = int(rank_item.get('score', 0)) if isinstance(rank_item.get('score'), (int, float)) else 0
                    
                    # Extraer campos adicionales
                    analisis = str(rank_item.get('analisis', rank_item.get('analysis', rank_item.get('match_analysis', ''))))
                    nivel_matcheo = str(rank_item.get('nivel_matcheo', rank_item.get('match_level', rank_item.get('compatibility_level', ''))))
                    fortalezas_clave = rank_item.get('fortalezas_clave', rank_item.get('strengths', rank_item.get('fortalezas', [])))
                    
                    # Normalizar fortalezas_clave a lista
                    if isinstance(fortalezas_clave, str):
                        # Si es string, intentar parsear como JSON o split por comas
                        try:
                            fortalezas_clave = json.loads(fortalezas_clave)
                        except:
                            fortalezas_clave = [f.strip() for f in fortalezas_clave.split(',') if f.strip()]
                    elif not isinstance(fortalezas_clave, list):
                        fortalezas_clave = []
                    
                    # Si no hay nivel_matcheo, derivarlo del score
                    if not nivel_matcheo:
                        if score >= 80:
                            nivel_matcheo = "EXCELENTE"
                        elif score >= 70:
                            nivel_matcheo = "BUENO"
                        elif score >= 60:
                            nivel_matcheo = "MODERADO"
                        else:
                            nivel_matcheo = "DÉBIL"
                    
                    formatted_ranking.append({
                        'candidate_id': candidate_id,
                        'name': name,
                        'score': score,
                        'analisis': analisis if analisis else f'Candidato con score de {score}',
                        'nivel_matcheo': nivel_matcheo,
                        'fortalezas_clave': [str(f) for f in fortalezas_clave[:4]]  # Máximo 4 fortalezas
                    })
            ranking_list = formatted_ranking
        
        # Preparar payload
        insert_payload = {
            'client_id': str(client_id),
            'jd_interview_id': str(jd_interview_id),
            'summary': summary_dict,
            'candidates': candidates_dict if isinstance(candidates_dict, dict) else {},
            'ranking': ranking_list if isinstance(ranking_list, list) else [],
            'candidates_count': int(candidates_count) if candidates_count is not None else 0
        }
        
        evaluation_logger.log_task_progress("Guardar Evaluación", f"Preparando insert: summary={summary_dict}, candidates={len(candidates_dict.keys()) if isinstance(candidates_dict, dict) else 0} elementos, ranking={len(ranking_list)} elementos")
        evaluation_logger.log_task_progress("Guardar Evaluación", f"Verificando si ya existe registro para jd_interview_id: {jd_interview_id}")
        
        # Verificar si ya existe un registro con este jd_interview_id
        try:
            existing = supabase.table('interview_evaluations').select('id').eq('jd_interview_id', jd_interview_id).order('created_at', desc=True).limit(1).execute()
            
            if existing.data and len(existing.data) > 0:
                # Ya existe, actualizar en lugar de insertar
                evaluation_id = existing.data[0].get('id')
                evaluation_logger.log_task_progress("Guardar Evaluación", f"Registro existente encontrado (ID: {evaluation_id}), actualizando...")
                
                # Actualizar el registro existente
                update_payload = {
                    'summary': summary_dict,
                    'candidates': candidates_dict if isinstance(candidates_dict, dict) else {},
                    'ranking': ranking_list if isinstance(ranking_list, list) else [],
                    'candidates_count': int(candidates_count) if candidates_count is not None else 0
                }
                
                upd = supabase.table('interview_evaluations').update(update_payload).eq('id', evaluation_id).execute()
                
                if upd.data and len(upd.data) > 0:
                    evaluation_logger.log_task_complete("Guardar Evaluación", f"✅ interview_evaluations actualizado exitosamente: {evaluation_id}")
                    return json.dumps({
                        "success": True,
                        "evaluation_id": evaluation_id,
                        "message": "Evaluación actualizada exitosamente",
                        "action": "updated"
                    }, indent=2)
                else:
                    evaluation_logger.log_error("Guardar Evaluación", "Update ejecutado pero no retornó datos")
                    return json.dumps({
                        "success": False,
                        "error": "Update ejecutado pero no retornó datos"
                    }, indent=2)
            else:
                # No existe, insertar nuevo registro
                evaluation_logger.log_task_progress("Guardar Evaluación", f"No existe registro previo, insertando nuevo registro para jd_interview_id: {jd_interview_id}")
                
                ins = supabase.table('interview_evaluations').insert(insert_payload).execute()
                
                if ins.data and len(ins.data) > 0:
                    evaluation_id = ins.data[0].get('id')
                    evaluation_logger.log_task_complete("Guardar Evaluación", f"✅ interview_evaluations creado exitosamente: {evaluation_id}")
                    return json.dumps({
                        "success": True,
                        "evaluation_id": evaluation_id,
                        "message": "Evaluación guardada exitosamente",
                        "action": "created"
                    }, indent=2)
                else:
                    evaluation_logger.log_error("Guardar Evaluación", "Insert ejecutado pero no retornó datos")
                    return json.dumps({
                        "success": False,
                        "error": "Insert ejecutado pero no retornó datos"
                    }, indent=2)
                    
        except Exception as db_error:
            evaluation_logger.log_error("Guardar Evaluación", f"Error en operación de BD: {str(db_error)}")
            import traceback
            evaluation_logger.log_error("Guardar Evaluación", f"Traceback: {traceback.format_exc()}")
            return json.dumps({
                "success": False,
                "error": f"Error en base de datos: {str(db_error)}"
            }, indent=2)
            
    except Exception as e:
        evaluation_logger.log_error("Guardar Evaluación", f"❌ Error creando interview_evaluations: {str(e)}")
        import traceback
        evaluation_logger.log_error("Guardar Evaluación", f"Traceback: {traceback.format_exc()}")
        return json.dumps({
            "success": False,
            "error": f"Error creando interview_evaluations: {str(e)}"
        }, indent=2)