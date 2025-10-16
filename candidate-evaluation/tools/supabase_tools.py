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
            id,
            candidate_id,
            meet_id,
            conversation_data,
            candidates(name),
            meets(job_description)
            '''
        ).limit(limit).execute()
        
        conversations = []
        for row in response.data:
            conversation = {
                "conversation_id": row['id'],
                "candidate_id": row['candidate_id'],
                "meet_id": row['meet_id'],
                "conversation_data": row['conversation_data'],
                "candidate_name": row['candidates']['name'] if row['candidates'] else None,
                "job_description_url": row['meets']['job_description'] if row['meets'] else None
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
        
    Returns:
        JSON string con el resultado del envío
    """
    try:
        evaluation_logger.log_task_start("Envío de Email", "Email Sender")
        evaluation_logger.log_task_progress("Envío de Email", f"Preparando email: {subject}")
        
        email_api_url = os.getenv("EMAIL_API_URL", "http://127.0.0.1:8004/send-simple-email")
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
def get_jd_interview_data(interview_id: str = None) -> str:
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
                "email_source": row.get('email_source'),
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