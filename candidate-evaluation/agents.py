# agents.py
import os
from crewai import Agent
from langchain_openai import ChatOpenAI
from tools.supabase_tools import SupabaseExtractorTool
from dotenv import load_dotenv

load_dotenv()

# Configurar el modelo de OpenAI
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.1
)

def create_data_extractor_agent():
    """Crea el agente extractor de datos"""
    return Agent(
        role="Data Extraction Specialist",
        goal="Extraer datos de conversaciones desde Supabase incluyendo información de candidatos y meets",
        backstory="""Eres un especialista en extracción de datos con experiencia en bases de datos.
        Tu trabajo es obtener información completa de conversaciones, asegurándote de incluir
        todos los datos relacionados mediante joins correctos.""",
        tools=[SupabaseExtractorTool()],
        verbose=True,
        llm=llm
    )

def create_conversation_analyzer_agent():
    """Crea el agente analizador de conversaciones"""
    return Agent(
        role="Conversation Analysis Expert",
        goal="Analizar el contenido JSON de conversaciones para extraer insights valiosos",
        backstory="""Eres un experto en análisis de conversaciones y procesamiento de lenguaje natural.
        Tu especialidad es extraer sentimientos, temas clave, y conclusiones importantes de datos
        de conversación en formato JSON.""",
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