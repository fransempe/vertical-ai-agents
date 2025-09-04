import os
import json
import requests
from typing import List, Dict, Any
from crewai.tools import tool
from supabase import create_client, Client
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.logger import evaluation_logger

load_dotenv()

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
    Obtiene la descripción del trabajo desde el campo job_description de la tabla meets.
    
    Args:
        job_description: Descripción del trabajo
        
    Returns:
        JSON string con el contenido de la descripción del trabajo
    """
    try:
        evaluation_logger.log_task_start("Análisis Job Description", "Job Description Analyzer")
        evaluation_logger.log_task_progress("Análisis Job Description", f"Obteniendo contenido desde: {job_description}")
        
        if not job_description or not job_description.strip():
            evaluation_logger.log_error("Análisis Job Description", "URL vacía o inválida")
            return json.dumps({"error": "job_description vacía o inválida"}, indent=2)
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(job_description, headers=headers, timeout=30)
        response.raise_for_status()
        
        evaluation_logger.log_task_complete("Análisis Job Description", f"Contenido obtenido exitosamente, {len(response.text)} caracteres")
        
        return json.dumps({
            "job_description": job_description,
            "content": response.text,
            "status_code": response.status_code,
            "content_type": response.headers.get('content-type', '')
        }, indent=2)
        
    except requests.exceptions.RequestException as e:
        evaluation_logger.log_error("Análisis Job Description", f"Error de petición: {str(e)}")
        return json.dumps({"error": f"Error fetching job description: {str(e)}"}, indent=2)
    except Exception as e:
        evaluation_logger.log_error("Análisis Job Description", f"Error inesperado: {str(e)}")
        return json.dumps({"error": f"Unexpected error: {str(e)}"}, indent=2)

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
        to_email = "francisco.sempe@flockit.com.ar"
        
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
        evaluation_logger.log_email_sent("francisco.sempe@flockit.com.ar", subject, f"error: {str(e)}")
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