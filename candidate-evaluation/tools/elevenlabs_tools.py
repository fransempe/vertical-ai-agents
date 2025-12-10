import os
from typing import Optional, Dict, Any
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.logger import evaluation_logger
from agents import create_elevenlabs_prompt_generator_agent
from tasks import create_elevenlabs_prompt_generation_task
from crewai import Crew, Process

load_dotenv()


def generate_elevenlabs_prompt_from_jd(interview_name: str, job_description: str, sender_email: str) -> Dict[str, Any]:
    """
    Genera un prompt específico para ElevenLabs usando un agente de CrewAI basado en la JD,
    y extrae los datos del cliente.
    
    Args:
        interview_name: Nombre de la entrevista/búsqueda
        job_description: Descripción del trabajo
        sender_email: Email del remitente
        
    Returns:
        Diccionario con 'prompt' y 'cliente' (nombre, responsable, email, telefono)
    """
    try:
        evaluation_logger.log_task_start("Generar Prompt ElevenLabs", f"Generando prompt y extrayendo datos del cliente para: {interview_name}")
        
        # Crear agente y tarea
        agent = create_elevenlabs_prompt_generator_agent()
        task = create_elevenlabs_prompt_generation_task(agent, interview_name, job_description, sender_email)
        
        # Crear crew y ejecutar
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False
        )
        
        result = crew.kickoff()
        
        # Extraer el resultado
        result_text = str(result).strip()
        
        # Intentar parsear como JSON
        import json
        try:
            # Buscar JSON en el resultado
            json_match = None
            if result_text.startswith('{'):
                json_match = result_text
            else:
                # Buscar JSON dentro del texto
                import re
                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                matches = re.findall(json_pattern, result_text, re.DOTALL)
                if matches:
                    json_match = matches[-1]  # Tomar el último match (más probable que sea el completo)
            
            if json_match:
                result_data = json.loads(json_match)
                prompt_text = result_data.get('prompt', '').strip()
                cliente_data = result_data.get('cliente', {})
                agent_name = result_data.get('agent_name', '').strip()
                
                evaluation_logger.log_task_complete("Generar Prompt ElevenLabs", f"Prompt, datos del cliente y nombre del agente generados exitosamente")
                return {
                    'prompt': prompt_text,
                    'cliente': {
                        'nombre': cliente_data.get('nombre') or '',
                        'responsable': cliente_data.get('responsable') or '',
                        'email': cliente_data.get('email') or sender_email,
                        'telefono': cliente_data.get('telefono') or ''
                    },
                    'agent_name': agent_name
                }
        except (json.JSONDecodeError, KeyError) as e:
            evaluation_logger.log_error("Generar Prompt ElevenLabs", f"Error parseando JSON: {str(e)}")
            # Si falla el parseo, intentar extraer solo el prompt
            prompt_text = result_text.strip()
            if prompt_text.startswith('"') and prompt_text.endswith('"'):
                prompt_text = prompt_text[1:-1]
            if prompt_text.startswith("'") and prompt_text.endswith("'"):
                prompt_text = prompt_text[1:-1]
        
        # Fallback: retornar solo el prompt si no se pudo parsear
        evaluation_logger.log_task_progress("Generar Prompt ElevenLabs", "No se pudo parsear JSON, usando fallback")
        return {
            'prompt': prompt_text if 'prompt_text' in locals() else f"""Actúa como un entrevistador técnico profesional y amable que realiza entrevistas para la siguiente búsqueda:

Búsqueda: {interview_name}

Descripción del puesto:
{job_description}""",
            'cliente': {
                'nombre': '',
                'responsable': '',
                'email': sender_email,
                'telefono': ''
            },
            'agent_name': interview_name
        }
        
    except Exception as e:
        evaluation_logger.log_error("Generar Prompt ElevenLabs", f"Error generando prompt: {str(e)}")
        import traceback
        evaluation_logger.log_error("Generar Prompt ElevenLabs", f"Traceback: {traceback.format_exc()}")
        # Retornar prompt por defecto si falla
        return {
            'prompt': f"""Actúa como un entrevistador técnico profesional y amable que realiza entrevistas para la siguiente búsqueda:

Búsqueda: {interview_name}

Descripción del puesto:
{job_description}""",
            'cliente': {
                'nombre': '',
                'responsable': '',
                'email': sender_email,
                'telefono': ''
            },
            'agent_name': interview_name
        }


def create_elevenlabs_agent(
    agent_name: str,
    interview_name: str,
    job_description: str,
    sender_email: str,
    first_message: str = None,
    language: str = "es",
    voice_id: str = "bN1bDXgDIGX5lw0rtY2B",  # Melanie
    model_id: str = "eleven_flash_v2_5",
    llm: str = "gemini-2.5-flash"
) -> Optional[Dict[str, Any]]:
    """
    Crea un agente de voz en ElevenLabs para una búsqueda de trabajo.
    
    Args:
        agent_name: Nombre del agente (ej: "Agente ReactJS")
        interview_name: Nombre de la entrevista/búsqueda
        job_description: Descripción del trabajo (se usará en el prompt)
        first_message: Mensaje inicial del agente (opcional)
        language: Idioma del agente (default: "es")
        voice_id: ID de la voz a usar (default: Melanie)
        model_id: Modelo TTS a usar (default: "eleven_flash_v2_5")
        llm: Modelo LLM a usar (default: "gemini-2.5-flash")
        
    Returns:
        Diccionario con la respuesta de ElevenLabs o None si falla
    """
    try:
        evaluation_logger.log_task_start("Crear Agente ElevenLabs", f"Creando agente: {agent_name}")
        
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            evaluation_logger.log_error("Crear Agente ElevenLabs", "ELEVENLABS_API_KEY no configurada")
            return None
        
        # Inicializar cliente
        client = ElevenLabs(api_key=api_key)
        
        # Generar prompt específico y extraer datos del cliente usando el agente de CrewAI
        result_data = generate_elevenlabs_prompt_from_jd(interview_name, job_description, sender_email)
        generated_prompt = result_data.get('prompt', '')
        cliente_data = result_data.get('cliente', {})
        
        # Usar el nombre del agente generado por el agente de CrewAI, o el proporcionado como fallback
        generated_agent_name = result_data.get('agent_name', '').strip()
        if generated_agent_name:
            agent_name = generated_agent_name
            evaluation_logger.log_task_progress("Crear Agente ElevenLabs", f"Usando nombre de agente generado: {agent_name}")
        
        # Generar mensaje inicial si no se proporciona (después de obtener el nombre generado)
        if not first_message:
            first_message = "Hola, soy Clara, la entrevistadora del equipo de recruiting. ¿Estás listo para empezar?"
        
        # Estructura obligatoria de la entrevista
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
        
        # Concatenar el prompt generado con la estructura obligatoria
        prompt_text = generated_prompt + estructura_obligatoria
        
        # Preparar datos del agente
        eleven_labs_data = {
            "name": agent_name,
            "conversation_config": {
                "agent": {
                    "first_message": first_message,
                    "prompt": {
                        "prompt": prompt_text,
                        "llm": llm
                    },
                    "language": language
                },
                "tts": {
                    "model_id": model_id,
                    "voice_id": voice_id
                }
            }
        }
        
        # Crear agente
        response = client.conversational_ai.agents.create(**eleven_labs_data)
        
        evaluation_logger.log_task_complete(
            "Crear Agente ElevenLabs", 
            f"Agente creado exitosamente: {agent_name}"
        )
        
        # Convertir respuesta a diccionario si es necesario
        result_dict = None
        if hasattr(response, 'dict'):
            result_dict = response.dict()
        elif hasattr(response, '__dict__'):
            result_dict = response.__dict__
        else:
            result_dict = {"agent_id": str(response) if response else None, "name": agent_name}
        
        # Agregar datos del cliente al resultado
        if result_dict and isinstance(result_dict, dict):
            result_dict['cliente_data'] = cliente_data
        
        return result_dict
            
    except Exception as e:
        evaluation_logger.log_error("Crear Agente ElevenLabs", f"Error creando agente: {str(e)}")
        import traceback
        evaluation_logger.log_error("Crear Agente ElevenLabs", f"Traceback: {traceback.format_exc()}")
        return None

