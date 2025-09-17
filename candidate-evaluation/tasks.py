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
        Realizar un análisis exhaustivo y detallado del campo conversation_data de cada conversación extraída.
        
        Para cada conversación, analizar y evaluar los siguientes aspectos:

        ## 1. EVALUACIÓN GENERAL (Escala 1-10)
        - Puntaje general de la conversación
        - Calidad de las respuestas
        - Coherencia y fluidez del diálogo

        ## 2. HABILIDADES BLANDAS (Escala 1-10 cada una)
        - **Comunicación**: Claridad, articulación, capacidad de expresión
        - **Liderazgo**: Iniciativa, capacidad de tomar decisiones, influencia
        - **Trabajo en equipo**: Colaboración, empatía, resolución de conflictos
        - **Adaptabilidad**: Flexibilidad ante cambios, resiliencia
        - **Resolución de problemas**: Pensamiento crítico, creatividad, análisis
        - **Gestión del tiempo**: Organización, priorización, eficiencia
        - **Inteligencia emocional**: Autoconciencia, autorregulación, empatía
        - **Aprendizaje continuo**: Curiosidad, disposición a crecer profesionalmente

        ## 3. ASPECTOS TÉCNICOS (Escala 1-10)
        - Conocimientos técnicos demostrados
        - Precisión en respuestas especializadas
        - Capacidad de explicar conceptos complejos
        - Experiencia práctica evidenciada

        ## 4. CARACTERÍSTICAS DE PERSONALIDAD
        - Confianza y seguridad
        - Profesionalismo
        - Actitud positiva
        - Motivación y entusiasmo

        ## 5. ANÁLISIS CONVERSACIONAL
        - Sentimientos predominantes durante la conversación
        - Temas principales discutidos
        - Momentos destacados (positivos y negativos)
        - Patrones de respuesta
        - Nivel de engagement y participación

        ## 6. EVALUACIÓN ESPECÍFICA POR PREGUNTA
        - Analizar las respuestas más importantes
        - Identificar fortalezas y debilidades específicas
        - Evaluar la profundidad de las respuestas

        ## 7. RECOMENDACIÓN FINAL
        - Resumen ejecutivo del candidato
        - Principales fortalezas identificadas
        - Áreas de mejora o preocupaciones
        - Recomendación de contratación (Recomendado/Condicional/No Recomendado)
        - Justificación detallada de la recomendación

        ## FORMATO DE SALIDA JSON:
        ```json
        {
          "conversation_id": "string",
          "candidate_name": "string",
          "overall_assessment": {
            "general_score": 0-10,
            "recommendation": "Recomendado/Condicional/No Recomendado",
            "confidence_level": "Alta/Media/Baja"
          },
          "soft_skills": {
            "communication": 0-10,
            "leadership": 0-10,
            "teamwork": 0-10,
            "adaptability": 0-10,
            "problem_solving": 0-10,
            "time_management": 0-10,
            "emotional_intelligence": 0-10,
            "continuous_learning": 0-10
          },
          "technical_assessment": {
            "technical_score": 0-10,
            "knowledge_depth": "Básico/Intermedio/Avanzado/Experto",
            "practical_experience": "Limitada/Moderada/Amplia/Extensa"
          },
          "personality_traits": {
            "confidence": 0-10,
            "professionalism": 0-10,
            "positive_attitude": 0-10,
            "motivation": 0-10
          },
          "conversation_analysis": {
            "predominant_sentiment": "string",
            "key_topics": ["topic1", "topic2"],
            "engagement_level": "Bajo/Medio/Alto",
            "response_quality": "string"
          },
          "detailed_insights": {
            "strengths": ["strength1", "strength2"],
            "weaknesses": ["weakness1", "weakness2"],
            "standout_moments": ["moment1", "moment2"],
            "concerns": ["concern1", "concern2"]
          },
          "final_recommendation": {
            "summary": "string",
            "hiring_decision": "string",
            "justification": "string",
            "next_steps": "string"
          }
        }
        ```
        
        Ser exhaustivo pero conciso. Basar todas las evaluaciones en evidencia específica de la conversación.
        """,
        expected_output="Análisis detallado y estructurado de cada conversación con evaluaciones específicas y recomendaciones en formato JSON",
        agent=agent,
        context=[extraction_task]
    )

def create_job_analysis_task(agent, extraction_task):
    """Tarea de análisis de descripciones de trabajo"""
    return Task(
        description="""
        Analizar las descripciones de trabajo obtenidas de las URLs en el campo job_description de la tabla meets.
        
        Para cada conversación que tenga una URL de descripción de trabajo:
        1. Obtener el contenido de la descripción del trabajo desde la URL
        2. Extraer los requisitos clave del puesto:
           - Habilidades técnicas requeridas
           - Experiencia necesaria
           - Competencias blandas deseadas
           - Nivel de educación
           - Responsabilidades principales
        3. Crear un perfil detallado del puesto ideal
        4. Preparar la información para la comparación con los resultados de conversaciones
        
        Proporcionar el análisis en formato JSON estructurado con información clara y procesable.
        """,
        expected_output="Análisis detallado de cada descripción de trabajo en formato JSON",
        agent=agent,
        context=[extraction_task]
    )

def create_candidate_job_comparison_task(agent, extraction_task, analysis_task, job_analysis_task):
    """Tarea de comparación candidato vs descripción de trabajo"""
    return Task(
        description="""
        Comparar los resultados del análisis de conversaciones con los requisitos del puesto
        extraídos de las descripciones de trabajo.
        
        Para cada candidato:
        1. Tomar el análisis de su conversación (habilidades, puntajes, evaluaciones)
        2. Comparar con los requisitos del puesto correspondiente
        3. Calcular un puntaje de compatibilidad candidato-puesto (1-10)
        4. Identificar fortalezas del candidato que coinciden con el puesto
        5. Identificar áreas donde el candidato no cumple con los requisitos
        6. Proporcionar recomendaciones específicas
        7. Generar un resumen ejecutivo de la evaluación
        
        El análisis debe ser objetivo y basado en datos concretos.
        """,
        expected_output="Comparación detallada candidato-puesto con puntajes y recomendaciones en formato JSON",
        agent=agent,
        context=[extraction_task, analysis_task, job_analysis_task]
    )

def create_processing_task(agent, extraction_task, analysis_task, job_analysis_task, comparison_task):
    """Tarea de procesamiento final"""
    return Task(
        description="""
        Combinar todos los análisis realizados para crear un reporte final comprehensivo.
        
        El reporte debe incluir para cada conversación:
        - Información básica (IDs, nombres, títulos)
        - Datos originales de conversación
        - Análisis completo de conversación realizado
        - Análisis de descripción de trabajo (si disponible)
        - Comparación candidato vs puesto (si descripción disponible)
        - Resumen ejecutivo con recomendación final
        
        Generar también estadísticas generales:
        - Total de conversaciones procesadas
        - Distribución por candidatos
        - Distribución por meets
        - Promedio de calidad de conversaciones
        - Promedio de puntaje de evaluación técnica
        - Promedio de compatibilidad candidato-puesto
        - Rankings de candidatos por puesto
        - Recomendaciones de contratación
        
        """,
        expected_output="Reporte final completo con todos los análisis, comparaciones y estadísticas en formato JSON",
        agent=agent,
        context=[extraction_task, analysis_task, job_analysis_task, comparison_task]
    )

def create_email_sending_task(agent, processing_task):
    """Tarea de envío de email con resultados"""
    return Task(
        description="""
        Enviar UN ÚNICO email con todo el contenido de la evaluación de candidatos en formato de texto legible.
        
        IMPORTANTE: Enviar SOLAMENTE UN EMAIL. No enviar múltiples emails ni duplicados.
        
        Tomar todos los resultados del procesamiento final y crear UN ÚNICO email que contenga:
        
        1. Asunto del email: "Reporte de Evaluación de Candidatos - 04/09/2025"
        
        2. Cuerpo del email debe incluir la evaluación completa en texto legible:
           - Todos los datos de cada conversación procesada
           - Análisis detallados de cada candidato
           - Evaluaciones de habilidades blandas con puntajes
           - Análisis técnicos y de personalidad
           - Recomendaciones y justificaciones
           - Comparaciones con job descriptions
           - Estadísticas y métricas calculadas
           - Ranking completo de candidatos
           
        3. Formato del email:
           - Texto plano y legible, NO JSON
           - Estructurado con títulos y secciones claras
           - Incluir todos los detalles del procesamiento
           - Fácil de leer y comprender
           
        4. PROCESO: 
           - Preparar TODO el contenido en un solo email
           - Enviar UNA SOLA VEZ usando la función send_evaluation_email
           - Verificar que el email fue enviado exitosamente
           - Retornar confirmación del envío
        
        5. RESTRICCIÓN CRÍTICA: Solo usar la función send_evaluation_email UNA VEZ por ejecución.
        
        El email debe ser enviado a flocklab.id@gmail.com usando la API configurada.
        """,
        expected_output="Confirmación del envío y copia exacta del email completo enviado con toda la evaluación detallada",
        agent=agent,
        context=[processing_task]
    )