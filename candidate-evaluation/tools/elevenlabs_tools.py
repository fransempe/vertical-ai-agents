import os
import sys
from typing import Any

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from os import getenv

from crewai import Crew, Process

from agents import create_elevenlabs_prompt_generator_agent
from tasks import create_elevenlabs_prompt_generation_task
from utils.logger import evaluation_logger

load_dotenv()

DEFAULT_ELEVENLABS_VOICE_ID = "bN1bDXgDIGX5lw0rtY2B"  # Melanie


def generate_elevenlabs_prompt_from_jd(interview_name: str, job_description: str, sender_email: str) -> dict[str, Any]:
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
        evaluation_logger.log_task_start(
            "Generar Prompt ElevenLabs", f"Generando prompt y extrayendo datos del cliente para: {interview_name}"
        )

        # Crear agente y tarea
        agent = create_elevenlabs_prompt_generator_agent()
        task = create_elevenlabs_prompt_generation_task(agent, interview_name, job_description, sender_email)

        # Crear crew y ejecutar
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

        result = crew.kickoff()

        # Extraer el resultado
        result_text = str(result).strip()

        # Intentar parsear como JSON
        import json

        try:
            # Buscar JSON en el resultado
            json_match = None
            if result_text.startswith("{"):
                json_match = result_text
            else:
                # Buscar JSON dentro del texto
                import re

                json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
                matches = re.findall(json_pattern, result_text, re.DOTALL)
                if matches:
                    json_match = matches[-1]  # Tomar el último match (más probable que sea el completo)

            if json_match:
                result_data = json.loads(json_match)
                prompt_text = result_data.get("prompt", "").strip()
                cliente_data = result_data.get("cliente", {})
                agent_name = result_data.get("agent_name", "").strip()

                evaluation_logger.log_task_complete(
                    "Generar Prompt ElevenLabs", "Prompt, datos del cliente y nombre del agente generados exitosamente"
                )
                return {
                    "prompt": prompt_text,
                    "cliente": {
                        "nombre": cliente_data.get("nombre") or "",
                        "responsable": cliente_data.get("responsable") or "",
                        "email": cliente_data.get("email") or sender_email,
                        "telefono": cliente_data.get("telefono") or "",
                    },
                    "agent_name": agent_name,
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
            "prompt": prompt_text
            if "prompt_text" in locals()
            else f"""Actúa como un entrevistador técnico profesional y amable que realiza entrevistas para la siguiente búsqueda:

Búsqueda: {interview_name}

Descripción del puesto:
{job_description}""",
            "cliente": {"nombre": "", "responsable": "", "email": sender_email, "telefono": ""},
            "agent_name": interview_name,
        }

    except Exception as e:
        evaluation_logger.log_error("Generar Prompt ElevenLabs", f"Error generando prompt: {str(e)}")
        import traceback

        evaluation_logger.log_error("Generar Prompt ElevenLabs", f"Traceback: {traceback.format_exc()}")
        # Retornar prompt por defecto si falla
        return {
            "prompt": f"""Actúa como un entrevistador técnico profesional y amable que realiza entrevistas para la siguiente búsqueda:

Búsqueda: {interview_name}

Descripción del puesto:
{job_description}""",
            "cliente": {"nombre": "", "responsable": "", "email": sender_email, "telefono": ""},
            "agent_name": interview_name,
        }


def create_elevenlabs_agent(
    agent_name: str,
    interview_name: str,
    job_description: str,
    sender_email: str,
    first_message: str = None,
    language: str = "es",
    voice_id: str | None = None,
    model_id: str = "eleven_flash_v2_5",
    llm: str = "gemini-2.5-flash",
) -> dict[str, Any] | None:
    """
    Crea un agente de voz en ElevenLabs para una búsqueda de trabajo.

    Args:
        agent_name: Nombre del agente (ej: "Agente ReactJS")
        interview_name: Nombre de la entrevista/búsqueda
        job_description: Descripción del trabajo (se usará en el prompt)
        first_message: Mensaje inicial del agente (opcional)
        language: Idioma del agente (default: "es")
        voice_id: ID de la voz a usar (default: ELEVENLABS_VOICE_ID o Melanie)
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

        voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID") or DEFAULT_ELEVENLABS_VOICE_ID

        # Inicializar cliente
        client = ElevenLabs(api_key=api_key)

        # Generar prompt específico y extraer datos del cliente usando el agente de CrewAI
        result_data = generate_elevenlabs_prompt_from_jd(interview_name, job_description, sender_email)
        generated_prompt = result_data.get("prompt", "")
        cliente_data = result_data.get("cliente", {})

        # Usar el nombre del agente generado por el agente de CrewAI, o el proporcionado como fallback.
        # Evitar nombres inválidos como "null - Búsqueda XXX" o que contengan "null".
        generated_agent_name = (result_data.get("agent_name") or "").strip()
        if generated_agent_name:
            # Si el LLM devolvió algo que contiene "null" lo consideramos inválido y usamos el fallback original.
            if "null" in generated_agent_name.lower():
                evaluation_logger.log_task_progress(
                    "Crear Agente ElevenLabs",
                    f"Nombre de agente generado inválido detectado ('{generated_agent_name}'); usando fallback: {agent_name}",
                )
            else:
                agent_name = generated_agent_name
                evaluation_logger.log_task_progress(
                    "Crear Agente ElevenLabs",
                    f"Usando nombre de agente generado: {agent_name}",
                )

        # Asegurar que el nombre del agente incluya el nombre del cliente cuando esté disponible.
        client_name = (cliente_data.get("nombre") or "").strip()
        if client_name and client_name.lower() not in agent_name.lower():
            original_name = agent_name
            agent_name = f"{client_name} - {agent_name}"
            evaluation_logger.log_task_progress(
                "Crear Agente ElevenLabs",
                f"Añadiendo nombre de cliente al agente: '{original_name}' -> '{agent_name}'",
            )

        # Generar mensaje inicial si no se proporciona (después de obtener el nombre generado)
        if not first_message:
            first_message = "Hola, soy Mauricio, el entrevistador del equipo de recruiting. ¿Estás listo para empezar?"

        # Estructura obligatoria de la entrevista
        estructura_obligatoria = """

Antes de la primera pregunta, llama SIEMPRE a get_candidate_info usando el candidate_id provisto. 
El first message debe ir acompañado al nombre sin el apellido del candidato.
Cuando preguntes sobre la experiencia y responsabilidades, apóyate en la información devuelta por get-candidate-info.

Actúa como un entrevistador técnico profesional y amable, especializado en el rol específico descrito en la job_description de esta búsqueda.
Tu tarea es adaptar dinámicamente la entrevista al puesto concreto (nivel, responsabilidades y stack/skills requeridos),
centrándote siempre en:
- La experiencia del candidato en funciones relevantes para ese rol.
- Su capacidad para cumplir las responsabilidades clave del puesto.
- Sus conocimientos técnicos y de dominio según lo que exige la descripción del trabajo.
La entrevista debe tener un tono profesional pero cercano, enfocado en evaluar ajuste al rol buscado en particular.

Además, utiliza SIEMPRE la información disponible en la job_description para responder dudas del candidato sobre:
- El cliente/empresa (tipo de cliente, sector, contexto del rol) cuando el candidato pregunte por ello.
- El puesto a cubrir (título del rol, responsabilidades principales, tecnologías clave y nivel de seniority requerido).
- El proceso de selección, explicando claramente:
  1) Que esta es una entrevista virtual inicial (con el agente de voz).
  2) Que luego habrá una entrevista con un recruiter humano.
  3) Que después se realizará un análisis de la entrevista (evaluación y feedback interno).

Si la job_description no trae suficiente información sobre alguno de estos puntos, explícalo de forma honesta y clara, sin inventar datos.

**ESTRUCTURA OBLIGATORIA DE LA ENTREVISTA:**

Debes realizar EXACTAMENTE las siguientes preguntas en este orden:

1. **1 PREGUNTA DE RESPONSABILIDADES EN EXPERIENCIA LABORAL:**
   - Realiza 1 pregunta sobre experiencia laboral del candidato
   - Leer del JSON del get-candidate-info las propiedades "responsibilities" y "experiencia" y tomar algunas de las responsabilidades que tuvo el candidato para poder preguntar sobre esa responsabilidad.

2. **1 PREGUNTA DE HABILIDADES BLANDAS:**
   - Realiza 1 pregunta breve sobre habilidades blandas del candidato
   - Ejemplos: comunicación, trabajo en equipo, liderazgo, resolución de problemas, adaptabilidad, gestión del tiempo
   - Esta preguntas deben evaluar las competencias interpersonales y profesionales del candidato
   - Haz una pregunta a la vez y espera la respuesta antes de continuar

3. **10 A 15 PREGUNTAS TÉCNICAS DEL PUESTO:**
   - Realiza entre 10 y 15 preguntas técnicas específicas basadas en la descripción del puesto
   - Las preguntas deben estar directamente relacionadas con las tecnologías, herramientas y conocimientos técnicos mencionados en la descripción del puesto
   - Sé específico y técnico, evaluando el conocimiento real del candidato
   - Haz una pregunta a la vez y espera la respuesta antes de continuar

4. **3 PREGUNTAS EN INGLÉS PARA EVALUAR IDIOMA:**
   - Al finalizar las preguntas técnicas, avisá claramente al candidato que ahora vas a cambiar a inglés para evaluar su nivel de idioma.
   - Decí algo similar a: "Ahora vamos a cambiar a inglés para hacer tres preguntas breves y evaluar tu nivel de idioma."
   - Elegí de forma random EXACTAMENTE 3 preguntas del siguiente banco, sin repetir, una a la vez, esperando la respuesta antes de continuar:
     1. "What is your current role and what are your main responsibilities?"
     2. "Can you describe a challenging project you worked on and how you handled it?"
     3. "What has been your biggest professional learning in the last year?"
     4. "What are you expecting from your next professional challenge?"
     5. "Based on the role description, why do you think this position is a good match for you?"
   - Pedí que responda en inglés y mantené esta parte de la entrevista en inglés.

**REGLAS IMPORTANTES:**
- Mantén un tono profesional pero amigable
- Evalúa las respuestas del candidato de manera objetiva
- Guía la conversación de manera estructurada
- Responde en español de manera clara y concisa
- NO hagas más de 1 pregunta sobre la experiencia del candidato 
- NO hagas más de 1 pregunta de habilidades blandas y que sea breve
- Haz como mínimo 10 y como máximo 15 preguntas técnicas. NO hagas menos de 10 ni más de 15.
- Hacé EXACTAMENTE 3 preguntas en inglés, elegidas de forma random del banco indicado. NO hagas más ni menos que 3.
- En total deben ser entre 15 y 20 preguntas evaluativas: 1 de experiencia, 1 de habilidades blandas, entre 10 y 15 técnicas y 3 en inglés.
- Al finalizar las preguntas evaluativas, agrega SIEMPRE una pregunta final de cierre: "¿Tenés alguna pregunta o alguna duda?"
- Hacia el final de la entrevista, incentiva activamente al candidato a realizar preguntas sobre el proceso, el rol o el cliente
- Antes de cerrar la entrevista, indicá explícitamente: "Para finalizar la entrevista con éxito, hacé click en Finalizar y luego cierra la ventana del navegador"
- Después de esa indicación, agradece al candidato y cierra la entrevista"""

        # Concatenar el prompt generado con la estructura obligatoria
        prompt_text = generated_prompt + estructura_obligatoria
        english_language_preset_prompt = """
You are Mauricio, the AI recruiter conducting the English assessment section of the interview.

When switching to English, clearly tell the candidate that you will now ask three brief questions in English to evaluate their language level.
Ask the candidate to answer in English and keep this part of the interview in English.

Randomly choose EXACTLY 3 questions from this bank, without repeating questions, one at a time, waiting for the candidate's answer before continuing:
1. "What is your current role and what are your main responsibilities?"
2. "Can you describe a challenging project you worked on and how you handled it?"
3. "What has been your biggest professional learning in the last year?"
4. "What are you expecting from your next professional challenge?"
5. "Based on the role description, why do you think this position is a good match for you?"

Do not ask more or fewer than 3 English questions. After the candidate answers, switch back to Spanish for the final closing question and interview closing instructions.
"""
        tool_id = getenv("ELEVENLABS_TOOL_ID")
        # Preparar datos del agente (configuración de conversación, TTS y tools en el prompt)
        eleven_labs_data = {
            "name": agent_name,
            "conversation_config": {
                "conversation": {
                    "max_duration_seconds": 7200,
                },
                "agent": {
                    "first_message": first_message,
                    "prompt": {
                        "prompt": prompt_text,
                        "llm": llm,
                        # Asociar tools dentro del prompt, según esquema de ElevenLabs
                        "tool_ids": [tool_id],
                    },
                    "language": language,
                },
                "language_presets": {
                    "en": {
                        "overrides": {
                            "agent": {
                                "first_message": (
                                    "Now we'll switch to English for three short questions "
                                    "to evaluate your language level."
                                ),
                                "prompt": {
                                    "prompt": english_language_preset_prompt,
                                    "llm": llm,
                                    "tool_ids": [tool_id],
                                },
                            }
                        }
                    }
                },
                "tts": {"model_id": model_id, "voice_id": voice_id},
            },
        }

        # Crear agente usando la configuración anterior
        response = client.conversational_ai.agents.create(**eleven_labs_data)

        evaluation_logger.log_task_complete("Crear Agente ElevenLabs", f"Agente creado exitosamente: {agent_name}")

        # Convertir respuesta a diccionario si es necesario
        result_dict = None
        if hasattr(response, "dict"):
            result_dict = response.dict()
        elif hasattr(response, "__dict__"):
            result_dict = response.__dict__
        else:
            result_dict = {"agent_id": str(response) if response else None, "name": agent_name}

        # Agregar datos del cliente al resultado
        if result_dict and isinstance(result_dict, dict):
            result_dict["cliente_data"] = cliente_data

        return result_dict

    except Exception as e:
        evaluation_logger.log_error("Crear Agente ElevenLabs", f"Error creando agente: {str(e)}")
        import traceback

        evaluation_logger.log_error("Crear Agente ElevenLabs", f"Traceback: {traceback.format_exc()}")
        return None


def update_elevenlabs_agent_prompt(agent_id: str, prompt_text: str) -> dict[str, Any] | None:
    """
    Actualiza únicamente el prompt de un agente existente de ElevenLabs.

    Args:
        agent_id: ID del agente en ElevenLabs
        prompt_text: Nuevo prompt completo a aplicar al agente

    Returns:
        Diccionario con la respuesta de ElevenLabs o None si falla
    """
    try:
        evaluation_logger.log_task_start("Actualizar Agente ElevenLabs", f"Actualizando prompt del agente: {agent_id}")

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY no está configurada")

        client = ElevenLabs(api_key=api_key, base_url="https://api.elevenlabs.io")

        # Realizar PATCH para actualizar solo el prompt
        response = client.conversational_ai.agents.update(
            agent_id=agent_id, conversation_config={"agent": {"prompt": {"prompt": prompt_text}}}
        )

        # Convertir respuesta a diccionario si es necesario
        result_dict: dict[str, Any] | None = None
        if hasattr(response, "dict"):
            result_dict = response.dict()
        elif hasattr(response, "__dict__"):
            result_dict = response.__dict__
        else:
            result_dict = {"agent_id": agent_id, "result": str(response)}

        evaluation_logger.log_task_complete(
            "Actualizar Agente ElevenLabs", f"Prompt actualizado correctamente para agent_id={agent_id}"
        )

        return result_dict

    except Exception as e:
        evaluation_logger.log_error("Actualizar Agente ElevenLabs", f"Error actualizando agente {agent_id}: {str(e)}")
        import traceback

        evaluation_logger.log_error("Actualizar Agente ElevenLabs", f"Traceback: {traceback.format_exc()}")
        return None
