from crewai import Task

def create_extraction_task(agent):
    """Tarea de extracción de datos"""
    return Task(
        description="""
        ⏱️ Antes de comenzar, imprime: START EXTRACTION [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END EXTRACTION [YYYY-MM-DD HH:MM:SS].

        Extraer todas las conversaciones de la base de datos Supabase.
        Incluir información relacionada de candidatos y meets usando los campos:
        - candidate_id para enlazar con tabla candidates
        - meet_id para enlazar con tabla meets
        
        Asegurar que cada registro incluya:
        - meet_id, candidate_id, conversation_data (campos específicos de conversations)
        - Datos completos del candidato (id, name, email, phone, cv_url, tech_stack)
        """,
        expected_output="Lista JSON de conversaciones con toda la información relacionada",
        agent=agent
    )

def create_analysis_task(agent, extraction_task):
    """Tarea de análisis de conversaciones"""
    return Task(
        description="""
        ⏱️ Antes de comenzar, imprime: START ANALYSIS [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END ANALYSIS [YYYY-MM-DD HH:MM:SS].

        🔍 Realizar un análisis exhaustivo, detallado y cualitativo del campo conversation_data de cada conversación extraída.

        REGLAS DE RIGOR DE DATOS (CRÍTICO):
        - SOLO puedes usar información presente en los datos de entrada (contexto y conversation_data de la BD).
        - NO inventes nombres, emails, tech_stacks ni datos de candidatos. Si un dato no está, deja "N/A".
        - Cuando cites fragmentos, cópialos exactamente del conversation_data.
        - Si faltan campos requeridos, repórtalos explícitamente sin crear contenido.
        
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
        ⏱️ Antes de comenzar, imprime: START JOB_ANALYSIS [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END JOB_ANALYSIS [YYYY-MM-DD HH:MM:SS].

        📄 Analizar las descripciones de trabajo obtenidas de la tabla jd_interviews para evaluación dinámica.

        REGLAS DE RIGOR DE DATOS (CRÍTICO):
        - Usa EXCLUSIVAMENTE los campos obtenidos de la BD (get_all_jd_interviews / get_jd_interviews_data).
        - NO inventes tecnologías ni requisitos si no están en el job_description.
        - Si un campo no aparece, repórtalo como "N/A" sin inferir.
        
        🔍 **PROCESO DE ANÁLISIS:**
        Para cada registro en jd_interviews:
        
        1. 📊 **Obtener datos de jd_interviews:**
           - Consultar la tabla jd_interviews usando get_all_jd_interviews()
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
        ⏱️ Antes de comenzar, imprime: START COMPARISON [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END COMPARISON [YYYY-MM-DD HH:MM:SS].

        🎯 Realizar análisis de matcheo entre candidatos y descripciones de trabajo desde Google Docs.

        REGLAS DE RIGOR DE DATOS (CRÍTICO):
        - El nombre del candidato, email, tech_stack DEBEN salir de los datos obtenidos de la BD.
        - El análisis de matcheo DEBE basarse en job_description y tech_stack extraídos, sin suponer datos.
        - Si faltan datos, reportar claramente y continuar sin inventar.
        
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
        ⏱️ Antes de comenzar, imprime: START PROCESSING [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END PROCESSING [YYYY-MM-DD HH:MM:SS].

        Combinar todos los análisis realizados para crear DOS SALIDAS:
        1. Un reporte JSON completo con todos los datos
        2. Un reporte formateado en texto siguiendo el formato específico requerido

        REGLAS DE RIGOR DE DATOS (CRÍTICO):
        - El reporte DEBE estar 100% fundamentado en los datos de entrada (extraction_task, job_analysis, comparison).
        - NO agregues candidatos ni campos que no existan en los datos provenientes de la BD.
        - Si algún campo falta, usa "N/A"; no lo inventes.
        
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
        
        **SI ES ANÁLISIS FILTRADO:**
        Asunto: Reporte de Evaluación - [JD_INTERVIEW_NAME] (ID: [JD_INTERVIEW_ID]) - [FECHA_ACTUAL]

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
        ⏱️ Antes de comenzar, imprime: START EMAIL_SENDING [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END EMAIL_SENDING [YYYY-MM-DD HH:MM:SS].

        🚀 Generar y enviar OBLIGATORIAMENTE un reporte final de evaluación de candidatos siguiendo EXACTAMENTE el formato especificado.

        ⚠️ **IMPORTANTE:** Este reporte es OBLIGATORIO y debe generarse SIEMPRE. Enviar SOLAMENTE UN EMAIL.

        🎯 **INSTRUCCIONES CRÍTICAS:**
        1. 📅 **PRIMERO:** Usar la herramienta get_current_date() para obtener la fecha actual en formato DD/MM/YYYY
        2. 📊 **OBTENER DATOS:** Revisar el resultado de la tarea de procesamiento (processing_task) para obtener todos los datos de candidatos y evaluaciones
        3. 📧 **ASUNTO DEL EMAIL:** 
           - Si es análisis completo: "📊 Reporte de Evaluación de Candidatos - [FECHA]"
           - Si es análisis filtrado: "📊 Reporte de Evaluación - [JD_INTERVIEW_NAME] (ID: [JD_INTERVIEW_ID]) - [FECHA]"
        4. 🔍 **DETECTAR TIPO DE ANÁLISIS:** Revisar los datos de entrada para identificar si incluyen información de jd_interview (jd_interview_id, jd_interview_name, jd_interview_agent_id)
        5. 📊 Generar el reporte completo con todos los candidatos analizados
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
        
        **SI ES ANÁLISIS FILTRADO POR JD_INTERVIEW_ID:**
        📧 Asunto: 📊 Reporte de Evaluación - [JD_INTERVIEW_NAME] (ID: [JD_INTERVIEW_ID]) - [FECHA_OBTENIDA_DE_LA_HERRAMIENTA]

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

        ⚠️ **RESTRICCIÓN CRÍTICA:**
        - Debes llamar a send_evaluation_email(subject, body) EXACTAMENTE UNA VEZ.
        - El body DEBE construirse SOLO con datos provenientes del processing_task (derivados de la BD).
        - NO inventes nombres ni datos. Si faltan, muestra "N/A".
        
        🔧 **USO DE HERRAMIENTAS:**
        1. Usar get_current_date() para obtener la fecha actual
        2. Usar send_evaluation_email(subject, body) para enviar el email
        3. El subject debe seguir el formato especificado arriba
        4. El body debe contener todo el reporte formateado según el formato exacto
        """,
        expected_output="Confirmación del envío y copia del reporte completo formateado según el formato exacto especificado",
        agent=agent,
        context=[processing_task]
    )

def create_evaluation_saving_task(agent, processing_task, jd_interview_id: str = None):
    """Tarea de guardado de evaluación en la base de datos"""
    if jd_interview_id:
        jd_instruction = f"""
🚨 **ACCIÓN OBLIGATORIA - DEBES EJECUTAR ESTO:**
El jd_interview_id es: {jd_interview_id}
DEBES llamar a save_interview_evaluation con este ID. NO es opcional.
"""
    else:
        jd_instruction = """
⚠️ **IMPORTANTE:** No hay jd_interview_id disponible. Busca jd_interview_id en el full_report o en las tareas anteriores.
Si no encuentras jd_interview_id, NO puedes guardar.
"""
    
    return Task(
        description=f"""💾 **TAREA CRÍTICA:** Procesar el resultado del análisis y guardar en interview_evaluations.

{jd_instruction}

🎯 **OBJETIVO:** Extraer datos del full_report y guardarlos en la base de datos ANTES de enviar el email.

        📋 **PROCESO OBLIGATORIO:**
        
        1. 📊 **REVISAR RESULTADO DEL PROCESAMIENTO:**
           - Obtener el resultado completo de la tarea de procesamiento (processing_task)
           - Buscar el campo 'full_report' en el resultado
           - Si no existe 'full_report', buscar 'report' o el objeto completo del resultado
           - Si el resultado es un string, intentar parsearlo como JSON
        
        2. 🔍 **EXTRAER DATOS DEL FULL_REPORT:**
           
           **A) SUMMARY (Estructura específica requerida):**
           - El summary DEBE tener esta estructura EXACTA:
             {{
               "kpis": {{
                 "completed_interviews": número_de_candidatos,
                 "avg_score": promedio_de_scores (float)
               }},
               "notes": "texto descriptivo de la evaluación"
             }}
           - Para calcular kpis:
             * completed_interviews: cantidad total de candidatos evaluados
             * avg_score: promedio de todos los scores de candidatos (suma de scores / cantidad)
           - Para notes: crear un texto descriptivo como "Evaluación final de búsqueda [nombre] - [fecha]"
           - ⚠️ IMPORTANTE: Esta es la estructura ÚNICA que debe tener el summary
           - Si el full_report tiene información adicional, incluirla en el summary pero mantener esta estructura base
           
           **B) CANDIDATES (Objeto estructurado - FORMATO ÚNICO):**
           - Buscar en el full_report el campo 'candidates' o buscar en 'conversations'/'meets'/'evaluations'
           - Estructurar candidates como un objeto donde:
             * Cada CLAVE es el candidate_id (UUID del candidato o meet_id) como STRING
             * Cada VALOR es un objeto con EXACTAMENTE estos campos: {{"name": str, "score": int, "recommendation": str}}
           - ⚠️ FORMATO EXACTO REQUERIDO (igual al ejemplo SQL):
             {{
               "cand-uuid-1": {{
                 "name": "Francisco Sempé",
                 "score": 82,
                 "recommendation": "Favorable"
               }},
               "cand-uuid-2": {{
                 "name": "Denis Perafán",
                 "score": 74,
                 "recommendation": "Condicional"
               }}
             }}
           - Si candidates viene como lista, convertirla a objeto usando candidate_id como clave
           - Buscar campos para candidate_id: candidate_id, id, meet_id, conversation_id
           - Buscar score en: score, general_score, final_score, overall_score (convertir a int)
           - Buscar recommendation en: recommendation, final_recommendation, final_decision, decision
           - Mapear recommendation: "Recomendado" -> "Favorable", mantener otros valores
           
           **C) RANKING (Array ordenado - FORMATO ÚNICO):**
           - Buscar en el full_report el campo 'ranking'
           - Si no existe, construir el ranking ordenando candidates por score (de mayor a menor)
           - ⚠️ FORMATO EXACTO REQUERIDO:
             [
               {{
                 "candidate_id": "cand-uuid-1",
                 "name": "Francisco Sempé",
                 "score": 82,
                 "analisis": "Análisis breve de matcheo del candidato",
                 "nivel_matcheo": "EXCELENTE",
                 "fortalezas_clave": ["Fortaleza 1", "Fortaleza 2", "Fortaleza 3"]
               }},
               {{
                 "candidate_id": "cand-uuid-2",
                 "name": "Denis Perafán",
                 "score": 74,
                 "analisis": "Análisis breve de matcheo del candidato",
                 "nivel_matcheo": "BUENO",
                 "fortalezas_clave": ["Fortaleza 1", "Fortaleza 2"]
               }}
             ]
           - Cada objeto debe tener EXACTAMENTE estos campos:
             * candidate_id (string): ID del candidato
             * name (string): Nombre del candidato
             * score (int): Score numérico
             * analisis (string): Análisis breve de 1-2 líneas sobre el matcheo del candidato
             * nivel_matcheo (string): "EXCELENTE", "BUENO", "MODERADO", o "DÉBIL"
             * fortalezas_clave (array de strings): Lista de 2-4 fortalezas principales del candidato
           - Buscar estos datos en:
             * analisis: Campo 'analysis', 'match_analysis', 'analisis' en el full_report o en el análisis de matcheo del candidato
             * nivel_matcheo: Campo 'nivel_matcheo', 'match_level', 'compatibility_level' o derivarlo del score
             * fortalezas_clave: Campo 'strengths', 'fortalezas', 'fortalezas_clave' en el análisis del candidato
           - Ordenar por score de mayor a menor
           
           **D) CANDIDATES_COUNT:**
           - Contar la cantidad de candidatos en el objeto candidates
           - Si candidates es dict: len(candidates.keys())
           - Si candidates es list: len(candidates)
        
        3. 🔍 **OBTENER JD_INTERVIEW_ID:**
           - PRIMERO: Usar el jd_interview_id proporcionado en esta descripción si está disponible
           - SEGUNDO: Buscar jd_interview_id en el full_report (campo 'jd_interview_id' o 'jd_interview' con subcampo 'id')
           - TERCERO: Buscar en las tareas anteriores (extraction_task) que pueden tener el jd_interview_id
           - Si NO hay jd_interview_id disponible, NO guardar y retornar: "No se puede guardar: jd_interview_id no disponible"
           - Si hay jd_interview_id, proceder con el guardado
        
        4. 💾 **GUARDAR EN BASE DE DATOS - ESTO ES OBLIGATORIO:**
           ⚠️ **DEBES LLAMAR A save_interview_evaluation EXACTAMENTE UNA VEZ - NO LLAMES DOS VECES**
           
           Pasos EXACTOS:
           a) Importar json si no está disponible
           b) Convertir cada objeto a JSON string:
              * summary_json = json.dumps(full_report_dict)
              * candidates_json = json.dumps(candidates_dict)  
              * ranking_json = json.dumps(ranking_list)
           c) LLAMAR A LA HERRAMIENTA save_interview_evaluation UNA SOLA VEZ con estos parámetros EXACTOS:
              - Si jd_interview_id está en esta descripción, usa ese valor EXACTAMENTE
              - Si no está aquí, búscalo en el full_report
              - Llamar: save_interview_evaluation(
                  jd_interview_id=jd_interview_id_encontrado,
                  summary=summary_json,
                  candidates=candidates_json,
                  ranking=ranking_json,
                  candidates_count=candidates_count
              )
           d) ⚠️ CRÍTICO: 
              - jd_interview_id debe ser un STRING
              - summary, candidates, ranking deben ser STRINGS JSON (no objetos)
              - candidates_count debe ser un INT
              - DEBES usar la herramienta save_interview_evaluation, NO escribir código que intente guardar directamente
              - ⚠️ LLAMAR SOLO UNA VEZ - después de llamar, retornar el resultado y TERMINAR
        
        5. ✅ **VERIFICAR RESULTADO:**
           - Parsear la respuesta de save_interview_evaluation como JSON
           - Verificar que el campo 'success' sea True
           - Si success es True, retornar: "✅ Evaluación guardada exitosamente. Evaluation ID: [evaluation_id]"
           - Si success es False, retornar: "❌ Error guardando: [error]"
        
        ⚠️ **REGLAS CRÍTICAS - FORMATO ÚNICO:**
        1. El summary DEBE tener estructura: {{"kpis": {{"completed_interviews": int, "avg_score": float}}, "notes": string}}
        2. Candidates DEBE ser objeto: {{"candidate-id": {{"name": str, "score": int, "recommendation": str}}, ...}}
        3. Ranking DEBE ser array: [{{"candidate_id": str, "name": str, "score": int, "analisis": str, "nivel_matcheo": str, "fortalezas_clave": [str, ...]}}, ...]
        4. DEBES usar la herramienta save_interview_evaluation - NO intentes guardar de otra forma
        5. SIEMPRE convertir objetos a JSON strings con json.dumps() antes de llamar al tool
        6. Si no hay jd_interview_id disponible, retornar: "❌ No se puede guardar: jd_interview_id no disponible"
        7. Si hay jd_interview_id, DEBES llamar a save_interview_evaluation - no es opcional
        
        🔧 **PASOS OBLIGATORIOS:**
        1. ✅ Revisar resultado de processing_task
        2. ✅ Extraer full_report
        3. ✅ Procesar candidates y ranking
        4. ✅ Convertir a JSON strings
        5. ✅ LLAMAR A save_interview_evaluation (OBLIGATORIO)
        6. ✅ Retornar el resultado del guardado
        
        📝 **SALIDA REQUERIDA:**
        Debes retornar el resultado de save_interview_evaluation. Si fue exitoso, mostrar el evaluation_id.
        Si falló, mostrar el error específico.
        """,
        expected_output="Confirmación del guardado en interview_evaluations con evaluation_id o mensaje específico indicando por qué no se pudo guardar",
        agent=agent,
        context=[processing_task]
    )

def create_filtered_extraction_task(agent, jd_interview_id: str):
    """Tarea de extracción de datos filtrada por jd_interview_id"""
    return Task(
        description=f"""
        ⏱️ Antes de comenzar, imprime: START FILTERED_EXTRACTION [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END FILTERED_EXTRACTION [YYYY-MM-DD HH:MM:SS].

        Extraer conversaciones filtradas por jd_interview_id: {jd_interview_id}
        
        Proceso:
        1. Obtener jd_interview por ID: {jd_interview_id}
        2. Buscar meets que tengan jd_interviews_id = {jd_interview_id}
        3. Obtener conversaciones de esos meets específicos
        
        Incluir información relacionada de candidatos y meets usando los campos:
        - candidate_id para enlazar con tabla candidates
        - meet_id para enlazar con tabla meets
        - jd_interview_id para contexto del filtro
        
        Asegurar que cada registro incluya:
        - meet_id, candidate_id, conversation_data (campos específicos de conversations)
        - Datos completos del candidato (id, name, email, phone, cv_url, tech_stack)
        - Información del jd_interview (nombre, agent_id, email_source)
        """,
        expected_output=f"Lista JSON de conversaciones filtradas por jd_interview_id: {jd_interview_id} con toda la información relacionada. Si no hay conversaciones, incluir mensaje informativo: 'No se han presentado candidatos para esta entrevista'. IMPORTANTE: Incluir siempre la información del jd_interview (id, name, agent_id, email_source) para usar en el título del reporte.",
        agent=agent
    )

def create_matching_task(agent):
    """Tarea de matching de candidatos con entrevistas"""
    return Task(
        description="""
        ⏱️ Antes de comenzar, imprime: START MATCHING [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END MATCHING [YYYY-MM-DD HH:MM:SS].

        🎯 Realizar matching inteligente entre candidatos (tech_stack) y entrevistas (job_description).
        
        📊 **PROCESO DE MATCHING:**
        
        1. 📋 **Obtener Datos de Candidatos:**
           - Usar get_candidates_data() para obtener todos los candidatos
           - Extraer el campo tech_stack de cada candidato
           - Obtener información básica (id, name, email, phone, cv_url)
        
        2. 📋 **Obtener Datos de Entrevistas:**
           - Usar get_all_jd_interviews() para obtener TODAS las entrevistas
           - Extraer los campos interview_name y job_description
           - Obtener información del agente asignado (agent_id)
        
        3. 🔍 **Análisis de Compatibilidad:**
           Para cada candidato, analizar contra cada entrevista:
           - Comparar tech_stack del candidato con job_description de la entrevista
           - Identificar tecnologías exactas mencionadas en ambos
           - Identificar tecnologías relacionadas o complementarias
           - Detectar gaps importantes en el tech_stack del candidato
           - Calcular score de compatibilidad (0-100%)
        
        4. 📊 **Criterios de Evaluación:**
           - **Coincidencias Exactas (peso 40%):** Tecnologías que aparecen exactamente en ambos
           - **Coincidencias Relacionadas (peso 30%):** Frameworks, librerías o herramientas relacionadas
           - **Tecnologías Complementarias (peso 20%):** Skills que complementan el stack requerido
           - **Gaps Críticos (peso -10%):** Tecnologías esenciales que faltan en el candidato
        
        5. 🎯 **Generar Resultados SIMPLIFICADOS:**
           - SOLO mostrar candidatos que tengan matches (score > 0)
           - Para cada candidato con matches, incluir:
             * Datos completos del candidato (id, name, email, phone, cv_url, tech_stack)
             * Lista de entrevistas que coinciden con sus datos
             * Para cada entrevista: registro completo de jd_interviews (id, interview_name, agent_id, job_description, email_source, created_at) + score de compatibilidad + análisis del match
        
        6. 📝 **Formato de Salida SIMPLIFICADO:**
           ```json
           {
             "matches": [
               {
                 "candidate": {
                   "id": "123",
                   "name": "Juan Pérez",
                   "email": "juan@email.com",
                   "phone": "+1234567890",
                   "cv_url": "https://s3.../cv.pdf",
                   "tech_stack": ["React", "JavaScript", "Node.js"]
                 },
                 "matching_interviews": [
                   {
                     "jd_interviews": {
                       "id": "456",
                       "interview_name": "Desarrollador React Senior",
                       "agent_id": "agent_123",
                       "job_description": "Buscamos desarrollador con React, JavaScript...",
                       "email_source": "recruiting@company.com",
                       "created_at": "2025-01-18T10:30:00Z"
                     },
                     "compatibility_score": 85,
                     "match_analysis": "Excelente match con React y JavaScript..."
                   }
                 ]
               }
             ]
           }
           ```
        
        ⚠️ **IMPORTANTE:** 
        - Solo incluir candidatos que tengan al menos un match (score > 0)
        - Todo el análisis debe estar en ESPAÑOL LATINO
        - Utiliza terminología de recursos humanos en español de América Latina
        - Si no hay matches, retornar: {"matches": []}
        - **CRÍTICO**: La respuesta debe ser SOLO JSON válido, sin texto adicional
        - **CRÍTICO**: No incluir explicaciones fuera del JSON
        - **CRÍTICO**: El JSON debe empezar con { y terminar con }
        """,
        expected_output="SOLO JSON válido con estructura: {'matches': [{'candidate': {...}, 'matching_interviews': [{'jd_interviews': {...}, 'compatibility_score': X, 'match_analysis': '...'}]}]}",
        agent=agent
    )

def create_single_meet_extraction_task(agent, meet_id: str):
    """Tarea de extracción de datos de un meet específico"""
    return Task(
        description=f"""
        ⏱️ Antes de comenzar, imprime: START SINGLE_MEET_EXTRACTION [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END SINGLE_MEET_EXTRACTION [YYYY-MM-DD HH:MM:SS].

        Extraer todos los datos necesarios para evaluar el meet con ID: {meet_id}
        
        Debes obtener:
        - Información completa del meet (id, jd_interviews_id, fechas)
        - Conversación asociada al meet (conversation_data)
        - Datos completos del candidato (id, name, email, phone, cv_url, tech_stack)
        - Información del JD interview asociado (id, interview_name, agent_id, job_description, email_source)
        
        Usar get_meet_evaluation_data(meet_id="{meet_id}") para obtener todos los datos.
        """,
        expected_output="JSON completo con meet, conversation, candidate y jd_interview",
        agent=agent
    )

def create_single_meet_evaluation_task(agent, extraction_task):
    """Tarea de evaluación completa de un solo meet"""
    return Task(
        description="""
        ⏱️ Antes de comenzar, imprime: START SINGLE_MEET_EVALUATION [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END SINGLE_MEET_EVALUATION [YYYY-MM-DD HH:MM:SS].

        🔍 Realizar una evaluación exhaustiva y detallada de UNA SOLA entrevista (meet) para determinar 
        si el candidato es un posible match basado en la JD del meet.
        
        📋 **PROCESO DE EVALUACIÓN:**
        
        ## 1. 📊 **ANÁLISIS DE LA CONVERSACIÓN**
        Realizar un análisis exhaustivo similar al análisis estándar pero enfocado en un solo candidato:
        
        ### Habilidades Blandas - Análisis Cualitativo:
        - **Comunicación**: Comentario detallado con ejemplos específicos
        - **Liderazgo**: Análisis de iniciativa y toma de decisiones
        - **Trabajo en Equipo**: Evaluación de colaboración
        - **Adaptabilidad**: Flexibilidad y manejo de cambios
        - **Resolución de Problemas**: Pensamiento crítico y creatividad
        - **Gestión del Tiempo**: Organización y priorización
        - **Inteligencia Emocional**: Autoconciencia y empatía
        - **Aprendizaje Continuo**: Curiosidad y disposición a crecer
        
        ### Aspectos Técnicos - Análisis Detallado:
        - **Conocimientos Técnicos**: Nivel demostrado con ejemplos específicos
        - **Experiencia Práctica**: Evidencia de experiencia real
        - **Análisis Obligatorio de Preguntas Técnicas**:
          * Identificar EXACTAMENTE todas las preguntas técnicas
          * Para cada pregunta: copiar texto exacto, verificar si fue contestada (SÍ/NO/PARCIALMENTE)
          * Copiar respuesta exacta del candidato
          * Evaluar calidad técnica de cada respuesta
          * Crear resumen: [X/Y completamente contestadas, X/Y parcialmente, X/Y no contestadas]
          * Si hay preguntas sin contestar, generar ALERTA CRÍTICA
        
        ## 2. 📋 **ANÁLISIS DE LA JD**
        Analizar la job_description del JD interview asociado:
        - Extraer requisitos técnicos específicos
        - Identificar tecnologías y stack requerido
        - Extraer requisitos de experiencia
        - Identificar habilidades blandas esperadas
        - Determinar nivel de seniority requerido
        
        ## 3. 🎯 **COMPARACIÓN Y DETERMINACIÓN DE MATCH**
        Comparar el análisis del candidato con los requisitos de la JD:
        
        ### Comparación Técnica:
        - Coincidencias exactas con tecnologías requeridas
        - Coincidencias parciales o relacionadas
        - Gaps críticos en tecnologías requeridas
        - Tecnologías complementarias del candidato
        - Nivel de conocimiento vs nivel requerido
        
        ### Comparación de Habilidades Blandas:
        - Evaluar cada habilidad blanda vs lo requerido
        - Identificar fortalezas sobresalientes
        - Identificar áreas de mejora relevantes
        
        ### Evaluación de Experiencia:
        - Experiencia práctica vs experiencia requerida
        - Proyectos mencionados vs tipo de proyectos requeridos
        - Nivel de seniority demostrado vs requerido
        
        ## 4. ✅ **DETERMINACIÓN FINAL DE MATCH**
        Basado en todo el análisis, determinar:
        - **¿Es un posible match?** (SÍ/NO/CONDICIONAL)
        - **Score de compatibilidad** (0-100%)
        - **Justificación detallada** de la decisión
        - **Fortalezas principales** que apoyan el match
        - **Áreas de preocupación** o gaps importantes
        - **Recomendación final** (Recomendado/Condicional/No Recomendado)
        
        ## FORMATO DE SALIDA JSON:
        ```json
        {{
          "meet_id": "string",
          "candidate": {{
            "id": "string",
            "name": "string",
            "email": "string",
            "tech_stack": "string"
          }},
          "jd_interview": {{
            "id": "string",
            "interview_name": "string",
            "job_description": "string"
          }},
          "conversation_analysis": {{
            "soft_skills": {{
              "communication": "comentario detallado",
              "leadership": "comentario detallado",
              "teamwork": "comentario detallado",
              "adaptability": "comentario detallado",
              "problem_solving": "comentario detallado",
              "time_management": "comentario detallado",
              "emotional_intelligence": "comentario detallado",
              "continuous_learning": "comentario detallado"
            }},
            "technical_assessment": {{
              "knowledge_level": "Básico/Intermedio/Avanzado/Experto",
              "practical_experience": "Limitada/Moderada/Amplia/Extensa",
              "technical_questions": [
                {{
                  "question": "texto exacto de la pregunta",
                  "answered": "SÍ/NO/PARCIALMENTE",
                  "answer": "respuesta exacta del candidato",
                  "evaluation": "análisis detallado"
                }}
              ],
              "completeness_summary": {{
                "total_questions": X,
                "fully_answered": X,
                "partially_answered": X,
                "not_answered": X
              }},
              "alerts": ["alertas críticas si las hay"]
            }}
          }},
          "jd_analysis": {{
            "required_technologies": ["tech1", "tech2"],
            "experience_level_required": "Junior/Mid/Senior",
            "soft_skills_required": ["skill1", "skill2"]
          }},
          "match_evaluation": {{
            "is_potential_match": true/false,
            "compatibility_score": 0-100,
            "technical_match": {{
              "exact_matches": ["tech1", "tech2"],
              "partial_matches": ["tech3"],
              "critical_gaps": ["tech4"],
              "complementary_skills": ["tech5"]
            }},
            "soft_skills_match": "análisis comparativo",
            "experience_match": "análisis comparativo",
            "strengths": ["fortaleza1", "fortaleza2"],
            "concerns": ["preocupación1", "preocupación2"],
            "final_recommendation": "Recomendado/Condicional/No Recomendado",
            "justification": "justificación detallada de la decisión"
          }}
        }}
        ```
        
        IMPORTANTE: 
        - Ser exhaustivo pero conciso
        - Basar todas las evaluaciones en evidencia específica
        - Todo el análisis en ESPAÑOL LATINO
        - Proporcionar justificaciones claras para la determinación de match
        """,
        expected_output="JSON completo con análisis exhaustivo y determinación de match potencial",
        agent=agent,
        context=[extraction_task]
    )