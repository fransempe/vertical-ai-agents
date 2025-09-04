# agents.py
import os
from crewai import Agent
from langchain_openai import ChatOpenAI
from tools.supabase_tools import extract_supabase_conversations, fetch_job_description, send_evaluation_email
from dotenv import load_dotenv

load_dotenv()

# Configurar el modelo de OpenAI
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.1
)

def create_data_extractor_agent():
    """Crea el agente extractor de datos"""
    return Agent(
        role="Data Extraction Specialist",
        goal="Extraer datos de conversaciones desde Supabase incluyendo información de candidates y meets",
        backstory="""Eres un especialista en extracción de datos con experiencia en bases de datos.
        Tu trabajo es obtener información completa de la tabla conversations, asegurándote de incluir
        todos los datos relacionados al candidato y a la tabla meets mediante joins correctos.""",
        tools=[extract_supabase_conversations],
        verbose=True,
        llm=llm
    )

def create_conversation_analyzer_agent():
    """Crea el agente analizador de conversaciones"""
    return Agent(
        role="Senior Conversation Analysis & HR Assessment Expert",
        goal="Realizar análisis exhaustivos y profesionales de conversaciones de candidatos, evaluando habilidades blandas, técnicas y potencial de contratación",
        backstory="""Eres un experto senior en análisis de conversaciones con más de 15 años de experiencia en recursos humanos 
        y evaluación de talento. Tu especialidad es realizar análisis profundos y objetivos de conversaciones entre candidatos 
        y sistemas de entrevistas de IA.

        Tienes experiencia en:
        - Psicología organizacional y evaluación de competencias
        - Análisis de habilidades blandas (comunicación, liderazgo, trabajo en equipo, etc.)
        - Evaluación técnica y profesional
        - Identificación de fortalezas y áreas de mejora
        - Predicción de desempeño laboral basada en patrones conversacionales
        - Detección de red flags y señales positivas en candidatos

        Tu enfoque es meticuloso, basado en evidencia, y siempre proporcionas evaluaciones balanceadas con justificaciones claras.
        Entiendes que el campo conversation_data contiene la interacción entre el candidato (user) y el sistema de entrevista (AI),
        donde el AI hace preguntas y el user responde.

        Tu objetivo es proporcionar evaluaciones que ayuden a tomar decisiones de contratación informadas y justas.""",
        verbose=True,
        llm=llm
    )

def create_job_description_analyzer_agent():
    """Crea el agente analizador de descripciones de trabajo"""
    return Agent(
        role="Job Description Analysis Expert",
        goal="Analizar descripciones de trabajo y compararlas con los resultados de las conversaciones",
        backstory="""Eres un experto en análisis de descripciones de trabajo y recursos humanos.
        Tu especialidad es obtener información detallada de descripciones de trabajo desde URLs,
        analizarlas para extraer requisitos clave, habilidades necesarias, experiencia requerida,
        y luego compararlas con los resultados de análisis de conversaciones para determinar
        qué tan bien se ajusta cada candidato al puesto. Proporcionas un análisis detallado
        de la compatibilidad candidato-puesto con puntajes y recomendaciones específicas.""",
        tools=[fetch_job_description],
        verbose=True,
        llm=llm
    )

def create_data_processor_agent():
    """Crea el agente procesador de datos"""
    return Agent(
        role="Data Processing Coordinator",
        goal="Coordinar el procesamiento completo y generar reportes finales estructurados",
        backstory="""Eres un coordinador experto en procesamiento de datos que combina información
        de múltiples fuentes. Tu trabajo es asegurar que todos los datos se procesen correctamente
        y generar reportes finales bien estructurados.""",
        verbose=True,
        llm=llm
    )

def create_email_sender_agent():
    """Crea el agente de envío de emails"""
    return Agent(
        role="Email Communication Specialist",
        goal="Enviar por email TODA la evaluación completa de candidatos en formato de texto legible y estructurado",
        backstory="""Eres un especialista en comunicaciones que se encarga de convertir y enviar
        TODOS los resultados completos del análisis de candidatos por email. Tu trabajo es tomar
        TODA la información procesada (análisis de conversaciones, evaluaciones de habilidades,
        comparaciones, estadísticas, recomendaciones) y crear un email con TODO el contenido
        en formato de texto legible y bien estructurado.
        
        NO debes hacer resúmenes. Debes incluir TODA la evaluación completa de cada candidato
        con todos los detalles, puntajes, análisis y recomendaciones. El email debe contener
        la evaluación COMPLETA en texto plano, fácil de leer, con títulos y secciones claras.
        
        IMPORTANTE: Siempre retornar una copia exacta del email completo enviado para que
        quede registrado en los resultados finales.""",
        tools=[send_evaluation_email],
        verbose=True,
        llm=llm
    )