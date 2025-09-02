from crewai import Task

def create_extraction_task(agent):
    """Tarea de extracción de datos"""
    return Task(
        description="""
        Extraer todas las conversaciones de la base de datos Supabase.
        Incluir información relacionada de candidatos y meets usando los campos:
        - candidate_id para enlazar con tabla candidates
        - meet_id para enlazar con tabla meets
        
        Asegurar que cada registro incluya:
        - ID de conversación
        - Datos JSON de conversation_data
        - Nombre del candidato
        - ID de meet
        """,
        expected_output="Lista JSON de conversaciones con toda la información relacionada",
        agent=agent
    )

def create_analysis_task(agent, extraction_task):
    """Tarea de análisis de conversaciones"""
    return Task(
        description="""
        Analizar el campo conversation_data de cada conversación extraída.
        Para cada conversación, extraer:
        
        1. Sentimientos predominantes
        2. Temas principales discutidos
        3. Conclusiones importantes
        4. Calidad de la conversación (escala 1-10)
        5. Habilidades blandas
        6. Puntaje de evaluación de las respuestas a las preguntas técnicas (escala 1-10)
        7. Sugerencia de que te pareció el candidato para el puesto requerido
        
        Proporcionar el análisis en formato JSON estructurado.
        """,
        expected_output="Análisis detallado de cada conversación en formato JSON",
        agent=agent,
        context=[extraction_task]
    )

def create_processing_task(agent, extraction_task, analysis_task):
    """Tarea de procesamiento final"""
    return Task(
        description="""
        Combinar los datos extraídos con los análisis realizados para crear un reporte final.
        
        El reporte debe incluir para cada conversación:
        - Información básica (IDs, nombres, títulos)
        - Datos originales de conversación
        - Análisis completo realizado
        - Resumen ejecutivo
        
        Generar también estadísticas generales:
        - Total de conversaciones procesadas
        - Distribución por candidatos
        - Distribución por meets
        - Promedio de calidad de conversaciones
        - Promedio de puntaje de evaluación de las respuestas a las preguntas técnicas
        - Promedio de puntaje de evaluación de la conversación
        - Promedio de sugerencia de que te pareció el candidato para el puesto requerido
        
        """,
        expected_output="Reporte final completo con datos procesados y estadísticas",
        agent=agent,
        context=[extraction_task, analysis_task]
    )