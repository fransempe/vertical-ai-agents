# agents.py
import os
from crewai import Agent
from langchain_openai import ChatOpenAI
from tools.supabase_tools import extract_supabase_conversations
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
        role="Conversation Analysis Expert",
        goal="Analizar el contenido JSON de conversaciones para extraer insights valiosos",
        backstory="""Eres un experto en análisis de conversaciones y procesamiento de lenguaje natural.
        Tu especialidad es extraer las habilidades blandas, sentimientos, temas clave, y conclusiones importantes de datos
        de conversación en formato JSON, incluyendo el nombre del candidato y el ID de la meet. Al final de la respuesta,
        necesito tener un puntaje de evaluación de la conversación de 1 a 10, 10 es la mejor evaluación. Esta evaluación
        debe ser objetiva y basada en la conversación entre el user y el agente de voz (AI), teniendo en cuenta las respuestas
        respondidas de forma correcta y en tiempo real. También debo tener un análisis de la conversación, con los puntos clave
        y una sugerencia de que te pareció el candidato, para el puesto requerido.
        Tener en cuenta que el campo conversation_data es un objeto con el contenido de la conversación entre
        el user y el agente de voz (AI). El agente AI es quien hace las preguntas y el user es quien responde.""",
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