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
        🔍 Realizar un análisis exhaustivo, detallado y cualitativo del campo conversation_data de cada conversación extraída.
        
        📋 **ENFOQUE PRINCIPAL:** Analizar la FORMA de responder del candidato, no solo el contenido.
        Proporcionar comentarios detallados y justificaciones fundamentadas para cada evaluación.

        ## 1. 🎯 **ANÁLISIS GENERAL DE LA CONVERSACIÓN**
        - **Calidad General**: Comentario detallado sobre la impresión general de la conversación
        - **Fluidez Comunicativa**: Análisis de cómo se expresa el candidato, claridad, coherencia
        - **Engagement**: Nivel de participación y compromiso mostrado
        - **Profesionalismo**: Demostración de actitud profesional y madurez

        ## 2. 💬 **ANÁLISIS DETALLADO DE PREGUNTAS Y RESPUESTAS**
        Para cada pregunta importante de la conversación:
        - **Pregunta**: [Citar la pregunta exacta]
        - **Respuesta del Candidato**: [Citar la respuesta completa]
        - **Análisis de la Forma de Responder**:
          * Tiempo de respuesta (inmediata, reflexiva, evasiva)
          * Estructura de la respuesta (organizada, desordenada, confusa)
          * Nivel de detalle (superficial, adecuado, exhaustivo)
          * Confianza en la respuesta (seguro, inseguro, dubitativo)
        - **Fortalezas Identificadas**: Qué aspectos positivos se observan
        - **Áreas de Mejora**: Qué aspectos podrían mejorarse
        - **Justificación**: Por qué se evalúa de esa manera

        ## 3. 🤝 **HABILIDADES BLANDAS - ANÁLISIS CUALITATIVO**
        - **Comunicación**: 
          * Comentario: Cómo se comunica el candidato, claridad, articulación
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas
        - **Liderazgo**: 
          * Comentario: Demostración de iniciativa, toma de decisiones, influencia
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas
        - **Trabajo en Equipo**: 
          * Comentario: Colaboración, empatía, resolución de conflictos
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas
        - **Adaptabilidad**: 
          * Comentario: Flexibilidad, resiliencia, manejo de cambios
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas
        - **Resolución de Problemas**: 
          * Comentario: Pensamiento crítico, creatividad, análisis
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas
        - **Gestión del Tiempo**: 
          * Comentario: Organización, priorización, eficiencia
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas
        - **Inteligencia Emocional**: 
          * Comentario: Autoconciencia, autorregulación, empatía
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas
        - **Aprendizaje Continuo**: 
          * Comentario: Curiosidad, disposición a crecer, apertura al aprendizaje
          * Ejemplos específicos de la conversación
          * Fortalezas y debilidades observadas

        ## 4. 🔧 **ASPECTOS TÉCNICOS - ANÁLISIS DETALLADO**
        - **Conocimientos Técnicos**: 
          * Comentario: Nivel de conocimientos demostrados
          * Ejemplos específicos de respuestas técnicas
          * Precisión y profundidad de los conceptos
        - **Experiencia Práctica**: 
          * Comentario: Evidencia de experiencia real en el campo
          * Ejemplos específicos de proyectos o situaciones mencionadas
          * Calidad de las experiencias compartidas
        - **Capacidad de Explicación**: 
          * Comentario: Cómo explica conceptos complejos
          * Ejemplos específicos de explicaciones dadas
          * Claridad y pedagogía en las explicaciones

        ## 5. 👤 **CARACTERÍSTICAS DE PERSONALIDAD - ANÁLISIS PROFUNDO**
        - **Confianza y Seguridad**: 
          * Comentario: Nivel de confianza mostrado
          * Ejemplos específicos de la conversación
          * Impacto en la comunicación
        - **Profesionalismo**: 
          * Comentario: Demostración de actitud profesional
          * Ejemplos específicos de la conversación
          * Madurez y seriedad mostrada
        - **Actitud Positiva**: 
          * Comentario: Optimismo y positividad demostrados
          * Ejemplos específicos de la conversación
          * Impacto en la dinámica de la conversación
        - **Motivación y Entusiasmo**: 
          * Comentario: Nivel de motivación y entusiasmo
          * Ejemplos específicos de la conversación
          * Evidencia de pasión por el trabajo

        ## 6. 🔍 **ANÁLISIS OBLIGATORIO DE PREGUNTAS TÉCNICAS**
        
        **⚠️ PROCESO CRÍTICO:** Identificar y evaluar EXACTAMENTE las preguntas técnicas específicas en la conversación basadas en el job_description.
        
        - **IDENTIFICACIÓN DE PREGUNTAS**: 
          * Leer cuidadosamente toda la conversación
          * Identificar EXACTAMENTE las preguntas técnicas específicas realizadas por el AI
          * Extraer el texto completo de cada pregunta técnica
          * Verificar que sean preguntas sobre la tecnología/stack específico del puesto (basado en job_description)
        
        - **EVALUACIÓN DE RESPUESTAS POR PREGUNTA**:
          * **Pregunta Técnica 1**: 
            - Texto exacto: "[COPIAR PREGUNTA EXACTA]"
            - ¿Fue contestada? [SÍ/NO/PARCIALMENTE]
            - Respuesta del candidato: "[COPIAR RESPUESTA EXACTA]"
            - Evaluación: [ANÁLISIS DETALLADO DE LA RESPUESTA]
          * **Pregunta Técnica 2**: 
            - Texto exacto: "[COPIAR PREGUNTA EXACTA]"
            - ¿Fue contestada? [SÍ/NO/PARCIALMENTE]
            - Respuesta del candidato: "[COPIAR RESPUESTA EXACTA]"
            - Evaluación: [ANÁLISIS DETALLADO DE LA RESPUESTA]
          * **Pregunta Técnica 3**: 
            - Texto exacto: "[COPIAR PREGUNTA EXACTA]"
            - ¿Fue contestada? [SÍ/NO/PARCIALMENTE]
            - Respuesta del candidato: "[COPIAR RESPUESTA EXACTA]"
            - Evaluación: [ANÁLISIS DETALLADO DE LA RESPUESTA]
          * **Pregunta Técnica 4**: 
            - Texto exacto: "[COPIAR PREGUNTA EXACTA]"
            - ¿Fue contestada? [SÍ/NO/PARCIALMENTE]
            - Respuesta del candidato: "[COPIAR RESPUESTA EXACTA]"
            - Evaluación: [ANÁLISIS DETALLADO DE LA RESPUESTA]
          * **Pregunta Técnica 5**: 
            - Texto exacto: "[COPIAR PREGUNTA EXACTA]"
            - ¿Fue contestada? [SÍ/NO/PARCIALMENTE]
            - Respuesta del candidato: "[COPIAR RESPUESTA EXACTA]"
            - Evaluación: [ANÁLISIS DETALLADO DE LA RESPUESTA]
        
        - **RESUMEN DE COMPLETITUD**:
          * Total de preguntas técnicas identificadas: [X/Y]
          * Preguntas completamente contestadas: [X/Y]
          * Preguntas parcialmente contestadas: [X/Y]
          * Preguntas NO contestadas: [X/Y]
          * **ALERTA CRÍTICA**: Si hay preguntas sin contestar, indicar claramente cuáles son
        
        - **EVALUACIÓN TÉCNICA GLOBAL**:
          * Nivel de conocimiento técnico en la tecnología específica demostrado
          * Precisión en conceptos específicos de la tecnología/stack
          * Capacidad de explicar conceptos complejos
          * Ejemplos prácticos y código proporcionado
          * Coherencia entre respuestas técnicas

        ## 7. 🧠 **ANÁLISIS CONVERSACIONAL DETALLADO**
        - **Sentimientos Predominantes**: 
          * Comentario: Qué emociones predominan en la conversación
          * Ejemplos específicos de expresiones emocionales
          * Impacto en la comunicación
        - **Temas Principales**: 
          * Comentario: Qué temas se discuten más
          * Profundidad de cada tema tratado
          * Relevancia para el puesto
        - **Momentos Destacados**: 
          * Comentario: Momentos más positivos y negativos
          * Ejemplos específicos de cada momento
          * Impacto en la evaluación general
        - **Patrones de Respuesta**: 
          * Comentario: Patrones consistentes en las respuestas
          * Ejemplos específicos de patrones observados
          * Implicaciones para el rol

        ## 8. 📊 **EVALUACIÓN INTEGRAL**
        - **Resumen Ejecutivo**: 
          * Comentario general sobre el candidato
          * Impresión general de la conversación
          * Nivel de compatibilidad con el puesto
        - **Fortalezas Principales**: 
          * Lista detallada de fortalezas identificadas
          * Ejemplos específicos de cada fortaleza
          * Impacto en el desempeño potencial
        - **Áreas de Mejora**: 
          * Lista detallada de áreas de mejora
          * Ejemplos específicos de cada área
          * Recomendaciones para el desarrollo
        - **Recomendación Final**: 
          * Recomendación de contratación (Recomendado/Condicional/No Recomendado)
          * Justificación detallada de la recomendación
          * Factores clave que influyen en la decisión

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
        expected_output="Análisis exhaustivo y cualitativo de cada conversación con comentarios detallados, justificaciones fundamentadas y evaluaciones específicas en formato JSON",
        agent=agent,
        context=[extraction_task]
    )

def create_job_analysis_task(agent, extraction_task):
    """Tarea de análisis de descripciones de trabajo"""
    return Task(
        description="""
        📄 Analizar las descripciones de trabajo obtenidas de la tabla jd_interviews para evaluación dinámica.
        
        🔍 **PROCESO DE ANÁLISIS:**
        Para cada registro en jd_interviews:
        
        1. 📊 **Obtener datos de jd_interviews:**
           - Consultar la tabla jd_interviews usando get_jd_interview_data()
           - Extraer el campo job_description de cada registro
           - Obtener información del agente asignado (agent_id)
        
        2. 📋 **Extraer requisitos clave del puesto:**
           - 🛠️ Habilidades técnicas requeridas (identificar tecnologías específicas)
           - 💼 Experiencia necesaria (años, nivel)
           - 🤝 Competencias blandas deseadas
           - 🎓 Nivel de educación requerido
           - 📝 Responsabilidades principales
           - 🏢 Tipo de empresa/industria
           - 💰 Rango salarial (si está disponible)
           - 📍 Ubicación/Modalidad de trabajo
        
        3. 🎯 **Crear perfil detallado del puesto ideal:**
           - Candidato perfecto para este rol
           - Tecnologías específicas requeridas
           - Puntajes de competencias esperadas
           - Prioridades del puesto
           - Criterios de evaluación
        
        4. 📊 **Preparar para comparación:**
           - Estructurar datos para matcheo con candidatos
           - Identificar criterios críticos vs deseables
           - Definir pesos de importancia
           - Mapear tecnologías específicas para análisis técnico
        
        ⚠️ **IMPORTANTE:** Todo el análisis debe estar en ESPAÑOL LATINO.
        Utiliza terminología de recursos humanos en español de América Latina.

        📤 **SALIDA:** Análisis detallado en formato JSON estructurado con información clara y procesable.
        """,
        expected_output="Análisis detallado de cada descripción de trabajo desde jd_interviews en formato JSON",
        agent=agent,
        context=[extraction_task]
    )

def create_candidate_job_comparison_task(agent, extraction_task, analysis_task, job_analysis_task):
    """Tarea de comparación candidato vs descripción de trabajo"""
    return Task(
        description="""
        🎯 Realizar análisis de matcheo entre candidatos y descripciones de trabajo desde Google Docs.
        
        📊 **PROCESO DE COMPARACIÓN:**
        Para cada candidato y su job description correspondiente:
        
        1. 🔍 **Análisis de Compatibilidad Técnica:**
           - Comparar habilidades técnicas del candidato vs requisitos del puesto
           - Evaluar nivel de experiencia vs experiencia requerida
           - Identificar fortalezas técnicas que coinciden
           - Detectar gaps técnicos importantes
        
        2. 🤝 **Análisis de Competencias Blandas:**
           - Comparar competencias blandas del candidato vs competencias deseadas
           - Evaluar soft skills críticas para el rol
           - Identificar fortalezas en comunicación, liderazgo, etc.
           - Detectar áreas de mejora en competencias blandas
        
        3. 📝 **Generar Análisis Textual Breve:**
           - Crear un análisis conciso de una línea sobre el matcheo
           - Incluir nivel de compatibilidad general (Excelente/Bueno/Moderado/Débil)
           - Mencionar las fortalezas principales que coinciden
           - Destacar gaps críticos si los hay
           - Proporcionar una evaluación general del fit candidato-puesto
        
        4. 🎯 **Formato del Análisis:**
           - Máximo 2-3 líneas de texto
           - Lenguaje claro y directo
           - Enfoque en compatibilidad general
           - Sin puntajes numéricos detallados
           - Justificación de la recomendación
           - Enfoque en la compatibilidad general del candidato con el puesto
        
        ⚠️ **IMPORTANTE:** Todo el análisis debe estar en ESPAÑOL LATINO.
        Utiliza terminología de recursos humanos en español de América Latina.
        """,
        expected_output="Análisis textual breve de matcheo candidato-puesto en formato JSON",
        agent=agent,
        context=[extraction_task, analysis_task, job_analysis_task]
    )

def create_processing_task(agent, extraction_task, analysis_task, job_analysis_task, comparison_task):
    """Tarea de procesamiento final"""
    return Task(
        description="""
        Combinar todos los análisis realizados para crear DOS SALIDAS:
        1. Un reporte JSON completo con todos los datos
        2. Un reporte formateado en texto siguiendo el formato específico requerido
        
        ## PRIMERA SALIDA - Reporte JSON completo:
        El reporte debe incluir para cada conversación:
        - Información básica (IDs, nombres, títulos)
        - Datos originales de conversación
        - Análisis completo de conversación realizado
        - Análisis de descripción de trabajo desde Google Docs (si disponible)
        - Análisis de matcheo candidato vs job description (si disponible)
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
        
        ## SEGUNDA SALIDA - Reporte Formateado:
        Crear ADICIONALMENTE un reporte en texto formateado para cada candidato usando EXACTAMENTE este formato:

        PARA CADA CANDIDATO:
        ```
        Asunto: Reporte de Evaluación de Candidatos - [FECHA_ACTUAL] (Colocar la fecha de hoy en formato DD/MM/YYYY)

        Estimado equipo de reclutamiento,

        A continuación se presenta el informe detallado de evaluación del candidato [NOMBRE_CANDIDATO]:

        Evaluación General:
        - Puntuación General: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Recomendación: [Recomendado/Condicional/No Recomendado] 
        - Nivel de Confianza: [Alta/Media/Baja]

        Habilidades Blandas:
        - Comunicación: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Liderazgo: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Trabajo en Equipo: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Adaptabilidad: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Resolución de Problemas: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Gestión del Tiempo: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Inteligencia Emocional: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Aprendizaje Continuo: [PUNTAJE] (colocar el puntaje de 0 a 10)

        Evaluación Técnica:
        - Puntuación Técnica: [PUNTAJE] (colocar el puntaje de 0 a 10)
        - Profundidad de Conocimiento: [Básico/Intermedio/Avanzado/Experto]
        - Experiencia Práctica: [Limitada/Moderada/Amplia/Extensa]

        Análisis de la Conversación:
        - Sentimiento Predominante: [SENTIMIENTO] (colocar el sentimiento predominante de la conversación)
        - Temas Clave: [LISTA_TEMAS] (colocar la lista de temas clave de la conversación)
        - Nivel de Compromiso: [Bajo/Medio/Alto] (colocar el nivel de compromiso de la conversación)
        - Calidad de Respuesta: [DESCRIPCIÓN] (colocar la descripción de la calidad de la respuesta)

        Observaciones Detalladas:
        - Fortalezas: [LISTA_FORTALEZAS] (colocar la lista de fortalezas de la conversación)
        - Áreas de Mejora: [LISTA_AREAS_MEJORA] (colocar la lista de áreas de mejora de la conversación)
        - Momentos Destacados: [LISTA_MOMENTOS] (colocar la lista de momentos destacados de la conversación)
        - Preocupaciones: [LISTA_PREOCUPACIONES] (colocar la lista de preocupaciones de la conversación)

        Recomendación Final:
        - Resumen: [RESUMEN_EJECUTIVO] (colocar el resumen ejecutivo de la recomendación final)
        - Decisión de Contratación: [DECISIÓN] (colocar la decisión de contratación de la recomendación final)
        - Justificación: [JUSTIFICACIÓN_DETALLADA]
        - Próximos Pasos: [RECOMENDACIONES_PRÓXIMOS_PASOS] (colocar las recomendaciones próximos pasos de la recomendación final)

        Atentamente,
        Clara - AI Recruiter
        ```

        La respuesta debe incluir AMBOS reportes: el JSON completo y el reporte formateado.
        """,
        expected_output="JSON que contenga tanto el reporte completo como el reporte formateado. Estructura: {'full_report': {...} }",
        agent=agent,
        context=[extraction_task, analysis_task, job_analysis_task, comparison_task]
    )

def create_email_sending_task(agent, processing_task):
    """Tarea de envío de email con resultados"""
    return Task(
        description="""
        🚀 Generar y enviar OBLIGATORIAMENTE un reporte final de evaluación de candidatos siguiendo EXACTAMENTE el formato especificado.

        ⚠️ **IMPORTANTE:** Este reporte es OBLIGATORIO y debe generarse SIEMPRE. Enviar SOLAMENTE UN EMAIL.

        🎯 **INSTRUCCIONES CRÍTICAS:**
        1. 📅 **PRIMERO:** Usar la herramienta get_current_date() para obtener la fecha actual en formato DD/MM/YYYY
        2. 📧 Usar esa fecha en el asunto del email
        3. 📊 Generar el reporte completo con todos los candidatos analizados
        4. 📝 **ANÁLISIS CUALITATIVO:** En las secciones de habilidades y evaluación técnica, proporcionar análisis textuales detallados con comentarios sobre la forma de responder, ejemplos específicos y justificaciones fundamentadas
        5. 📝 **ANÁLISIS DE MATCHEO:** Debe ser un análisis textual breve de 1-2 líneas, sin puntajes numéricos, enfocado en la compatibilidad general del candidato con el puesto
        6. 🎯 **ENFOQUE PRINCIPAL:** Analizar la FORMA de responder del candidato, no solo el contenido, con comentarios detallados y justificaciones
        6.1. 🔍 **ANÁLISIS TÉCNICO CRÍTICO:** 
            - Leer cuidadosamente toda la conversación para identificar EXACTAMENTE las preguntas técnicas específicas
            - Extraer el texto completo de cada pregunta técnica realizada por el AI
            - Verificar que cada pregunta sea específicamente sobre la tecnología/stack del puesto (basado en job_description)
            - Para cada pregunta: copiar el texto exacto, verificar si fue contestada (SÍ/NO/PARCIALMENTE), copiar la respuesta exacta del candidato
            - Crear un resumen de completitud: [X/Y completamente contestadas, X/Y parcialmente, X/Y no contestadas]
            - Si hay preguntas sin contestar, generar ALERTA CRÍTICA especificando cuáles son
        7. 🏆 **TOP 5 CANDIDATOS:** Al final del email, crear un ranking de los 5 mejores candidatos (o menos si no hay suficientes) basado en su compatibilidad con el Job Description, ordenados del mejor al peor matcheo. Esta sección debe ir AL FINAL del informe, después de todas las evaluaciones individuales
        8. 📏 **LÍNEAS DIVISORIAS:** Entre cada informe de candidato, agregar una línea divisoria clara para separar visualmente cada evaluación
        9. 🏆 **ENMARCAR TOP 5:** Agregar líneas divisorias encima y debajo de la sección "Top 5 Candidatos" para enmarcarla completamente y separarla del resto del contenido

        FORMATO EXACTO REQUERIDO para cada candidato:

        📧 Asunto: 📊 Reporte de Evaluación de Candidatos - [FECHA_OBTENIDA_DE_LA_HERRAMIENTA]

        👋 Estimado equipo de reclutamiento,

        📋 A continuación se presenta el informe detallado de evaluación del candidato [NOMBRE_CANDIDATO]:

        🎯 **EVALUACIÓN GENERAL**
        ⭐ Puntuación General: [PUNTAJE]
        🎖️ Recomendación: [Recomendado/Condicional/No Recomendado]
        🔒 Nivel de Confianza: [Alta/Media/Baja]

        💪 **HABILIDADES BLANDAS**
        💬 Comunicación: [ANÁLISIS_CUALITATIVO_COMUNICACIÓN]        
        👑 Liderazgo: [ANÁLISIS_CUALITATIVO_LIDERAZGO]
        🤝 Trabajo en Equipo: [ANÁLISIS_CUALITATIVO_TRABAJO_EQUIPO]
        🔄 Adaptabilidad: [ANÁLISIS_CUALITATIVO_ADAPTABILIDAD]
        🧩 Resolución de Problemas: [ANÁLISIS_CUALITATIVO_RESOLUCIÓN]
        ⏰ Gestión del Tiempo: [ANÁLISIS_CUALITATIVO_GESTIÓN_TIEMPO]
        🧠 Inteligencia Emocional: [ANÁLISIS_CUALITATIVO_INTELIGENCIA_EMOCIONAL]
        📚 Aprendizaje Continuo: [ANÁLISIS_CUALITATIVO_APRENDIZAJE]

        🔧 **EVALUACIÓN TÉCNICA**
        ⚙️ Conocimientos Técnicos: [ANÁLISIS_CUALITATIVO_CONOCIMIENTOS]
        📖 Experiencia Práctica: [ANÁLISIS_CUALITATIVO_EXPERIENCIA]
        💼 Capacidad de Explicación: [ANÁLISIS_CUALITATIVO_EXPLICACIÓN]

        💭 **ANÁLISIS DE LA CONVERSACIÓN**
        😊 Sentimiento Predominante: [SENTIMIENTO]
        🏷️ Temas Clave: [LISTA_TEMAS]
        🔥 Nivel de Compromiso: [Bajo/Medio/Alto]
        ✨ Calidad de Respuesta: [DESCRIPCIÓN]

        🔍 **ANÁLISIS DE PREGUNTAS TÉCNICAS**
        ⚠️ **SEGUIMIENTO CRÍTICO DE PREGUNTAS:**
        📊 Total Preguntas Identificadas: [X/Y preguntas técnicas específicas]
        ✅ Preguntas Completamente Contestadas: [X/Y]
        ⚠️ Preguntas Parcialmente Contestadas: [X/Y]
        ❌ Preguntas NO Contestadas: [X/Y]
        🎯 Calidad Técnica Global: [ANÁLISIS_CALIDAD_TÉCNICA_ESPECÍFICA]
        💡 Nivel de Conocimiento Técnico: [NIVEL_CONOCIMIENTO_TECNOLOGÍA_ESPECÍFICA]
        🚨 **ALERTA**: [Si hay preguntas sin contestar, especificar cuáles]

        📝 **OBSERVACIONES DETALLADAS**
        💎 Fortalezas: [LISTA_FORTALEZAS]
        🎯 Áreas de Mejora: [LISTA_AREAS_MEJORA]
        🌟 Momentos Destacados: [LISTA_MOMENTOS]
        ⚠️ Preocupaciones: [LISTA_PREOCUPACIONES]

        🎯 **ANÁLISIS DE MATCHEO CON JOB DESCRIPTION**
        📝 Análisis: [ANÁLISIS_BREVE_MATCHEO]
        
        🎯 **RECOMENDACIÓN FINAL**
        📄 Resumen: [RESUMEN_EJECUTIVO]
        ✅ Decisión de Contratación: [DECISIÓN]
        📋 Justificación: [JUSTIFICACIÓN_DETALLADA]
        🚀 Próximos Pasos: [RECOMENDACIONES_PRÓXIMOS_PASOS]

        🙏 Atentamente,
        👨‍💼 Clara - AI Recruiter

        🔄 [Si hay múltiples candidatos, repetir este formato para cada uno]
        
        ════════════════════════════════════════════════════════════════════════════════
        📋 **SIGUIENTE CANDIDATO**
        ════════════════════════════════════════════════════════════════════════════════

        ════════════════════════════════════════════════════════════════════════════════
        🏆 **TOP 5 CANDIDATOS RECOMENDADOS**
        ════════════════════════════════════════════════════════════════════════════════
        📊 Ranking basado en compatibilidad con el Job Description:

        🥇 **1er LUGAR - [NOMBRE_CANDIDATO_1]**
        ⭐ Nivel de Matcheo: [EXCELENTE/BUENO/MODERADO]
        🎯 Fortalezas Clave: [FORTALEZAS_PRINCIPALES]
        📝 Análisis: [ANÁLISIS_BREVE_MATCHEO_1]

        🥈 **2do LUGAR - [NOMBRE_CANDIDATO_2]**
        ⭐ Nivel de Matcheo: [EXCELENTE/BUENO/MODERADO]
        🎯 Fortalezas Clave: [FORTALEZAS_PRINCIPALES]
        📝 Análisis: [ANÁLISIS_BREVE_MATCHEO_2]

        🥉 **3er LUGAR - [NOMBRE_CANDIDATO_3]**
        ⭐ Nivel de Matcheo: [EXCELENTE/BUENO/MODERADO]
        🎯 Fortalezas Clave: [FORTALEZAS_PRINCIPALES]
        📝 Análisis: [ANÁLISIS_BREVE_MATCHEO_3]

        🏅 **4to LUGAR - [NOMBRE_CANDIDATO_4]**
        ⭐ Nivel de Matcheo: [EXCELENTE/BUENO/MODERADO]
        🎯 Fortalezas Clave: [FORTALEZAS_PRINCIPALES]
        📝 Análisis: [ANÁLISIS_BREVE_MATCHEO_4]

        🏅 **5to LUGAR - [NOMBRE_CANDIDATO_5]**
        ⭐ Nivel de Matcheo: [EXCELENTE/BUENO/MODERADO]
        🎯 Fortalezas Clave: [FORTALEZAS_PRINCIPALES]
        📝 Análisis: [ANÁLISIS_BREVE_MATCHEO_5]

        📋 **NOTA:** Si hay menos de 5 candidatos, mostrar solo los disponibles ordenados por compatibilidad.

        ════════════════════════════════════════════════════════════════════════════════

        🚀 **PROCESO OBLIGATORIO:**
        1. 📥 Tomar TODOS los resultados del procesamiento final
        2. ✨ Formatear cada candidato usando EXACTAMENTE el formato anterior
        3. 🔍 **VERIFICAR ANÁLISIS TÉCNICO:** Asegurar que cada candidato tenga análisis detallado de las preguntas técnicas específicas con seguimiento de completitud
        4. 📏 **LÍNEAS DIVISORIAS:** Agregar líneas divisorias entre cada informe de candidato para separación visual
        5. 🏆 **CREAR RANKING:** Evaluar la compatibilidad de cada candidato con el Job Description y ordenarlos del mejor al peor matcheo
        6. 📊 **TOP 5:** Seleccionar los 5 mejores candidatos (o menos si no hay suficientes) y crear la sección de ranking
        7. 📏 **ENMARCAR TOP 5:** Agregar líneas divisorias encima y debajo de la sección Top 5 para enmarcarla completamente
        8. 📧 Crear un email con todos los candidatos evaluados + ranking
        9. 🚀 Enviar UNA SOLA VEZ usando send_evaluation_email
        10. 📅 La fecha debe ser la actual en formato DD/MM/YYYY
        11. 🔄 Todos los campos entre corchetes deben ser reemplazados con datos reales

        ⚠️ **RESTRICCIÓN CRÍTICA:** Solo usar send_evaluation_email UNA VEZ por ejecución.
        """,
        expected_output="Confirmación del envío y copia del reporte completo formateado según el formato exacto especificado",
        agent=agent,
        context=[processing_task]
    )