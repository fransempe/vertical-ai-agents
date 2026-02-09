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
        ⏱️ START ANALYSIS [YYYY-MM-DD HH:MM:SS] | END ANALYSIS [YYYY-MM-DD HH:MM:SS]

        🔍 Analizar conversation_data de cada conversación. REGLAS: Solo datos de BD. NO inventar. Si falta dato → "N/A".

        **ENFOQUE:** Analizar FORMA de responder (estructura, claridad, confianza) + contenido técnico.

        **1. ANÁLISIS GENERAL:** Calidad, fluidez comunicativa, engagement, profesionalismo (1-2 líneas cada uno).

        **2. HABILIDADES BLANDAS (puntaje 0-10 + comentario breve):**
        - Comunicación, Liderazgo, Trabajo en Equipo, Adaptabilidad, Resolución de Problemas, Gestión del Tiempo, Inteligencia Emocional, Aprendizaje Continuo
        - Para cada una: puntaje + comentario de 1-2 líneas con ejemplo específico si aplica.

        **3. ASPECTOS TÉCNICOS:**
        - Conocimientos técnicos: nivel + ejemplo específico
        - Experiencia práctica: evidencia + calidad
        - Capacidad de explicación: claridad demostrada

        **4. PREGUNTAS TÉCNICAS (CRÍTICO):**
        Identificar TODAS las preguntas técnicas del AI sobre la tecnología/stack del puesto.
        Para cada pregunta técnica encontrada:
        - Texto exacto (copiar)
        - ¿Contestada? (SÍ/NO/PARCIALMENTE)
        - Respuesta exacta del candidato (copiar)
        - Evaluación breve (1-2 líneas)
        Resumen: Total [X], Completas [X], Parciales [X], No contestadas [X]. Si hay no contestadas → ALERTA con lista.

        **5. PERSONALIDAD:** Confianza, profesionalismo, actitud positiva, motivación (puntaje 0-10 + comentario breve cada uno).

        **6. CONVERSACIÓN:** Sentimiento predominante, temas clave (lista), engagement (Bajo/Medio/Alto), calidad de respuestas (breve).

        **7. EVALUACIÓN FINAL:**
        - Resumen ejecutivo (2-3 líneas)
        - Fortalezas principales (lista 3-5)
        - Áreas de mejora (lista 2-3)
        - Recomendación: Recomendado/Condicional/No Recomendado + justificación (2-3 líneas)

        **FORMATO JSON (OBLIGATORIO):**
        {
          "conversation_id": "string",
          "candidate_name": "string (de BD, no inventar)",
          "overall_assessment": {"general_score": 0-10, "recommendation": "Recomendado/Condicional/No Recomendado", "confidence_level": "Alta/Media/Baja"},
          "soft_skills": {"communication": 0-10, "leadership": 0-10, "teamwork": 0-10, "adaptability": 0-10, "problem_solving": 0-10, "time_management": 0-10, "emotional_intelligence": 0-10, "continuous_learning": 0-10},
          "technical_assessment": {"technical_score": 0-10, "knowledge_depth": "Básico/Intermedio/Avanzado/Experto", "practical_experience": "Limitada/Moderada/Amplia/Extensa", "technical_questions": [{"question": "texto exacto", "answered": "SÍ/NO/PARCIALMENTE", "answer": "respuesta exacta", "evaluation": "breve"}]},
          "personality_traits": {"confidence": 0-10, "professionalism": 0-10, "positive_attitude": 0-10, "motivation": 0-10},
          "conversation_analysis": {"predominant_sentiment": "string", "key_topics": ["topic1"], "engagement_level": "Bajo/Medio/Alto", "response_quality": "string"},
          "detailed_insights": {"strengths": ["s1", "s2"], "weaknesses": ["w1"], "standout_moments": ["m1"], "concerns": ["c1"]},
          "final_recommendation": {"summary": "string", "hiring_decision": "string", "justification": "string", "next_steps": "string"}
        }

        **OPTIMIZACIÓN:** Comentarios breves (1-2 líneas). Ejemplos solo si son relevantes. Evitar repeticiones.
        """,
        expected_output="JSON con análisis conciso de cada conversación: puntajes 0-10, comentarios breves (1-2 líneas), preguntas técnicas identificadas, y recomendación final",
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
        ⏱️ **OBLIGATORIO:** Antes de comenzar, imprime: START EMAIL_SENDING [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END EMAIL_SENDING [YYYY-MM-DD HH:MM:SS].

        🚀 **TAREA CRÍTICA:** Generar y enviar OBLIGATORIAMENTE un reporte final de evaluación de candidatos siguiendo EXACTAMENTE el formato especificado.
        
        ⚠️ **IMPORTANTE:** Esta tarea DEBE ejecutarse SIEMPRE, incluso si las tareas anteriores tuvieron problemas. Si no hay datos completos del processing_task, usar los datos disponibles de extraction_task o analysis_task.

        ⚠️ **IMPORTANTE:** Este reporte es OBLIGATORIO y debe generarse SIEMPRE. Enviar SOLAMENTE UN EMAIL.

        🎯 **INSTRUCCIONES CRÍTICAS:**
        1. 📅 **PRIMERO:** Usar la herramienta get_current_date() para obtener la fecha actual en formato DD/MM/YYYY
        2. 📊 **OBTENER DATOS:** Revisar el resultado de la tarea de procesamiento (processing_task) o extraction_task para obtener todos los datos de candidatos y evaluaciones
        3. 🔍 **EXTRAER JD_INTERVIEW_ID:** Identificar el jd_interview_id de los datos disponibles (extraction_task o processing_task)
        4. 📧 **OBTENER EMAIL DEL CLIENTE:** Usar get_jd_interviews_data(jd_interview_id) para obtener client_id, luego get_client_email(client_id) para obtener el email del cliente
        5. 📧 **ASUNTO DEL EMAIL:** 
           - Si es análisis completo: "📊 Reporte de Evaluación de Candidatos - [FECHA]"
           - Si es análisis filtrado: "📊 Reporte de Evaluación - [JD_INTERVIEW_NAME] (ID: [JD_INTERVIEW_ID]) - [FECHA]"
        6. 📊 Generar el reporte completo con todos los candidatos analizados
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

        📋 **NOTA:** Mostrar siempre 5 candidatos, si hay menos, mostrar los disponibles ordenados por compatibilidad.

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
        - Debes llamar a send_evaluation_email(subject, body, to_email=email_del_cliente) EXACTAMENTE UNA VEZ.
        - El email_del_cliente DEBE obtenerse usando get_jd_interviews_data() y get_client_email().
        - El body DEBE construirse SOLO con datos provenientes del processing_task (derivados de la BD).
        - NO inventes nombres ni datos. Si faltan, muestra "N/A".
        
        🔧 **USO DE HERRAMIENTAS:**
        - get_current_date(): Obtener fecha actual
        - get_jd_interviews_data(jd_interview_id): Obtener datos del jd_interview (incluye client_id)
        - get_client_email(client_id): Obtener email del cliente desde la tabla clients
        - send_evaluation_email(subject, body, to_email): Enviar email (el to_email debe venir de get_client_email())
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
        
        ⚠️ **IMPORTANTE:** Llamar a get_conversations_by_jd_interview EXACTAMENTE UNA VEZ. NO llamar múltiples veces.
        
        Proceso:
        1. Llamar UNA VEZ a get_conversations_by_jd_interview con jd_interview_id: {jd_interview_id}
        2. Usar los datos obtenidos directamente. NO volver a llamar la herramienta.
        
        Incluir información relacionada de candidatos y meets usando los campos:
        - candidate_id para enlazar con tabla candidates
        - meet_id para enlazar con tabla meets
        - jd_interview_id para contexto del filtro
        
        Asegurar que cada registro incluya:
        - meet_id, candidate_id, conversation_data (campos específicos de conversations)
        - Datos completos del candidato (id, name, email, phone, cv_url, tech_stack)
        - Información del jd_interview (nombre, agent_id, client_id)
        """,
        expected_output=f"Lista JSON de conversaciones filtradas por jd_interview_id: {jd_interview_id} con toda la información relacionada. Si no hay conversaciones, incluir mensaje informativo: 'No se han presentado candidatos para esta entrevista'. IMPORTANTE: Incluir siempre la información del jd_interview (id, name, agent_id, client_id) para usar en el título del reporte.",
        agent=agent
    )

def create_matching_task(agent, user_id: str = None, client_id: str = None):
    """Tarea de matching de candidatos con entrevistas"""
    from tools.supabase_tools import get_candidates_by_recruiter
    
    # Determinar qué herramienta usar y la descripción
    if user_id and client_id:
        candidates_instruction = f"- Usar get_candidates_by_recruiter(user_id='{user_id}', client_id='{client_id}', limit=1000) para obtener candidatos filtrados por user_id y client_id"
    else:
        candidates_instruction = "- Usar get_candidates_data() para obtener todos los candidatos"
    
    return Task(
        description=f"""
        ⏱️ Antes de comenzar, imprime: START MATCHING [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END MATCHING [YYYY-MM-DD HH:MM:SS].

        🚨 **PROHIBICIÓN ABSOLUTA - CRÍTICO:**
        - NUNCA inventes, modifiques o alteres NINGÚN dato que venga de la base de datos
        - Usa EXACTAMENTE los datos que obtienes de las herramientas (get_candidates_data, get_candidates_by_recruiter, get_all_jd_interviews)
        - Para jd_interviews: usa EXACTAMENTE el id, interview_name, agent_id, job_description, tech_stack, client_id, created_at que vienen de la herramienta
        - Para candidates: usa EXACTAMENTE el id, name, email, phone, tech_stack, cv_url, observations que vienen de la herramienta
        - NO generes agent_id, NO inventes IDs, NO modifiques nombres, NO alteres tech_stack
        - Si un campo es null o vacío en la BD, déjalo como null o no lo incluyas, pero NO lo inventes
        - Si no tienes un dato, NO lo inventes. Usa SOLO lo que está en la base de datos

        🎯 Realizar matching inteligente entre candidatos (tech_stack) y entrevistas (tech_stack). Si la entrevista no tiene tech_stack, usar job_description como fallback.
        
        📊 **PROCESO DE MATCHING:**
        
        1. 📋 **Obtener Datos de Candidatos:**
           {candidates_instruction}
           - Extraer el campo tech_stack de cada candidato que es un array de strings
           - Extraer el campo observations de cada candidato (JSONB con: work_experience, industries_and_sectors, languages, certifications_and_courses, other)
           - Obtener información básica (id, name, email, phone, tech_stack, cv_url, observations)
        
        2. 📋 **Obtener Datos de Entrevistas:**
           {f"- Usar get_all_jd_interviews(client_id='{client_id}') para obtener entrevistas filtradas por client_id" if client_id else "- Usar get_all_jd_interviews() para obtener TODAS las entrevistas"}
           - Extraer los campos interview_name, job_description y tech_stack (string separado por comas, puede ser null o vacío)
           - Obtener información del agente asignado (agent_id)
           - El tech_stack de la entrevista es el campo principal para la comparación técnica
        
        3. 🚫 **Verificar Meets Existentes (ANTES DEL MATCHING):**
           - Usar get_existing_meets_candidates() para obtener un diccionario donde cada clave es un jd_interview_id (string) y el valor es una lista de candidate_ids que ya tienen meets generados para esa entrevista
           - IMPORTANTE: Antes de incluir un candidato en los matches para una jd_interview específica, verificar que su candidate_id NO esté en la lista de candidate_ids con meets existentes para esa jd_interview_id
           - EXCLUIR completamente de los resultados cualquier combinación candidato-entrevista donde ya exista un meet
           - Ejemplo: Si el resultado es {{"jd_123": ["cand_1", "cand_2"]}}, entonces NO incluir cand_1 ni cand_2 en los matches para jd_123
        
        4. 🔍 **Análisis de Compatibilidad Técnica (tech_stack):**
           Para cada candidato vs cada entrevista (solo los que NO tienen meet existente):
           - Obtener el tech_stack del candidato (array de strings)
           - Obtener el tech_stack de la entrevista (string separado por comas, puede ser null o vacío)
           - Si la entrevista NO tiene tech_stack o está vacío, usar el job_description como fallback para la comparación
           - Si la entrevista tiene tech_stack:
             * Parsear el tech_stack de la entrevista (separar por comas y limpiar espacios)
             * Comparar cada tecnología del tech_stack del candidato (array) con cada tecnología del tech_stack de la entrevista (array)
             * **SER INCLUSIVO**: Buscar coincidencias case-insensitive y considerar variaciones amplias:
               - React = ReactJS = React.js = React Native
               - JavaScript = JS = ECMAScript = ES6
               - Node.js = NodeJS = Node
               - Python = Python3 = Python 3
               - TypeScript = TS
               - Vue = Vue.js = VueJS
               - Angular = AngularJS = Angular.js
               - SQL = MySQL = PostgreSQL = SQL Server = Oracle
               - AWS = Amazon Web Services
               - Docker = Docker Compose
               - Kubernetes = K8s
               - Git = GitHub = GitLab = Bitbucket
               - Y cualquier otra variación razonable
             * **NO SER ESTRICTO**: Si hay CUALQUIER coincidencia (exacta, parcial o relacionada), calcular score > 0
             * Calcular el score basado en el número de coincidencias exactas y relacionadas
           - **CRÍTICO - SER INCLUSIVO**: Si hay al menos UNA coincidencia (incluso parcial o relacionada), calcular score > 0 e INCLUIR en resultados
           - **NO OMITIR**: No omitir candidatos válidos. Si hay alguna relación técnica, incluir el match aunque sea débil
           - Solo excluir si NO hay NINGUNA coincidencia técnica (ni exacta, ni parcial, ni relacionada)
        
        4.5. 📋 **Análisis de Compatibilidad basado en Observations:**
           Para cada candidato que tenga observations y cada entrevista:
           - Analizar work_experience: Comparar empresas, posiciones y responsabilidades con requisitos del JD
           - Analizar industries_and_sectors: Evaluar si los rubros/industrias del candidato son relevantes para el tipo de empresa/cliente del JD
           - Analizar languages: Verificar si los idiomas del candidato cumplen con los requisitos de idioma del JD (si están especificados)
           - Analizar certifications_and_courses: Evaluar si las certificaciones y cursos son relevantes para el puesto
           - Analizar other: Buscar información adicional relevante (proyectos, publicaciones, etc.) que pueda ser relevante
           - Calcular un score de observations (0-100) basado en:
             * Relevancia de experiencia laboral: 30%
             * Coincidencia de rubros/industrias: 25%
             * Cumplimiento de requisitos de idiomas: 20%
             * Relevancia de certificaciones: 15%
             * Información adicional relevante: 10%
           - Generar un análisis textual breve (1-2 líneas) sobre la compatibilidad de observations con el JD
        
        5. 📊 **Criterios de Evaluación (combinando tech_stack y observations):**
           **Para tech_stack (SER INCLUSIVO Y GENEROSO):**
           - Coincidencias exactas: 40% (tecnologías que coinciden exactamente entre el tech_stack del candidato y el tech_stack de la entrevista)
           - Coincidencias relacionadas: 30% (frameworks/herramientas relacionadas o variaciones, ej: React=ReactJS, JavaScript=JS)
           - Tecnologías complementarias: 20% (tecnologías del JD que complementan las del candidato)
           - Gaps críticos: -10% (tecnologías esenciales del tech_stack del JD que faltan en el candidato)
           - **Score base INCLUSIVO**: Calcular como (coincidencias_exactas + coincidencias_relacionadas) / total_tech_jd * 100
           - **Score mínimo GENEROSO**: 15% si hay al menos una coincidencia (exacta o relacionada)
           - **BONIFICACIÓN**: Si hay múltiples coincidencias, sumar bonificaciones (no solo dividir)
           - **NO SER ESTRICTO**: Incluir candidatos incluso con coincidencias parciales o relacionadas
           - Si el JD no tiene tech_stack, usar job_description como fallback para la comparación
           - **IMPORTANTE**: Si un candidato tiene tecnologías relacionadas o complementarias, darle un score razonable (mínimo 15-20%)
           
           **Para observations (si está disponible):**
           - Relevancia de experiencia laboral: 30% (empresas, posiciones, responsabilidades relevantes)
           - Coincidencia de rubros/industrias: 25% (rubros del candidato vs tipo de empresa/cliente del JD)
           - Cumplimiento de requisitos de idiomas: 20% (idiomas del candidato vs requisitos del JD)
           - Relevancia de certificaciones: 15% (certificaciones relevantes para el puesto)
           - Información adicional relevante: 10% (proyectos, publicaciones, etc. relevantes)
           
           **Score final combinado:**
           - Si el candidato tiene observations: Score final = (tech_stack_score * 0.6) + (observations_score * 0.4)
           - Si el candidato NO tiene observations: Score final = tech_stack_score
        
        6. 🎯 **Generar Resultados SIMPLIFICADOS:**
           - SOLO mostrar candidatos que tengan matches (score > 0) ordenados por score de mayor a menor
           - Para cada candidato con matches, incluir:
             * Datos completos del candidato (id, name, email, phone, cv_url, tech_stack, observations si está disponible)
               **CRÍTICO**: Usa EXACTAMENTE los datos del candidato que obtuviste de la herramienta, NO los inventes
             * Lista de entrevistas que coinciden con sus datos ordenadas por score de compatibilidad de mayor a menor
             * Para cada entrevista: registro completo de jd_interviews (id, interview_name, agent_id, job_description, tech_stack, client_id, created_at) + score de compatibilidad + análisis del match técnico + análisis del match de observations (si observations está disponible)
               **CRÍTICO**: Usa EXACTAMENTE los datos de jd_interviews que obtuviste de get_all_jd_interviews. NO inventes agent_id, NO modifiques id, NO alteres ningún campo. Copia EXACTAMENTE lo que viene de la base de datos.
        
        7. 📝 **Formato de Salida SIMPLIFICADO:**
           ```json
           {{
             "matches": [
               {{
                 "candidate": {{
                   "id": "123",
                   "name": "Juan Pérez",
                   "email": "juan@email.com",
                   "phone": "+1234567890",
                   "cv_url": "https://s3.../cv.pdf",
                   "tech_stack": ["React", "JavaScript", "Node.js"],
                   "observations": {{
                     "work_experience": [...],
                     "industries_and_sectors": [...],
                     "languages": [...],
                     "certifications_and_courses": [...],
                     "other": "..."
                   }}
                 }},
                 "matching_interviews": [
                   {{
                     "jd_interviews": {{
                       "id": "456",
                       "interview_name": "Desarrollador React Senior",
                       "agent_id": "agent_123",
                       "job_description": "Buscamos desarrollador con React, JavaScript...",
                       "tech_stack": "React, JavaScript, Node.js",
                       "client_id": "client_456",
                       "created_at": "2025-01-18T10:30:00Z"
                     }},
                     "compatibility_score": 85,
                     "match_analysis": "Excelente match con React y JavaScript...",
                     "observations_match": {{
                       "work_experience_relevance": "Análisis de relevancia de experiencia laboral con el JD",
                       "industries_match": "Análisis de coincidencia de rubros/industrias",
                       "languages_match": "Análisis de cumplimiento de requisitos de idiomas",
                       "certifications_match": "Análisis de relevancia de certificaciones",
                       "overall_observations_score": 75,
                       "observations_analysis": "Análisis general de compatibilidad de observations con el JD"
                     }}
                   }}
                 ]
               }}
             ]
           }}
           ```
           
           **IMPORTANTE sobre observations_match:**
           - Si el candidato NO tiene observations o está vacío, el campo observations_match debe ser null o no incluirse
           - Si el candidato tiene observations, SIEMPRE incluir observations_match con todos sus campos
           - El overall_observations_score debe ser un número entre 0 y 100
           - Los análisis textuales deben ser breves (1-2 líneas cada uno)
        
        ⚠️ **IMPORTANTE:** 
        - **SER INCLUSIVO**: Incluir candidatos que tengan al menos un match (score > 0), incluso si el match es débil o parcial
        - **NO OMITIR CANDIDATOS VÁLIDOS**: Si un candidato tiene alguna coincidencia técnica (exacta, parcial o relacionada), incluirlo en los resultados
        - **GENEROSIDAD EN MATCHING**: Es mejor incluir más candidatos que omitir candidatos válidos. Si hay duda, incluir el match con un score apropiado
        - Todo el análisis debe estar en ESPAÑOL LATINO
        - Utiliza terminología de recursos humanos en español de América Latina
        - Si no hay matches, retornar: {{"matches": []}}
        - **CRÍTICO**: La respuesta debe ser SOLO JSON válido, sin texto adicional antes o después
        - **CRÍTICO**: No incluir explicaciones, comentarios, ni texto fuera del JSON
        - **CRÍTICO**: No usar bloques de código markdown (```json ... ```), solo el JSON puro
        - **CRÍTICO**: El JSON debe empezar con {{ y terminar con }}
        - **CRÍTICO**: No agregar ningún texto antes del {{ ni después del }}
        - **CRÍTICO**: La respuesta completa debe ser parseable directamente con json.loads()
        """,
        expected_output="SOLO JSON válido con estructura: {'matches': [{'candidate': {...}, 'matching_interviews': [{'jd_interviews': {...}, 'compatibility_score': X, 'match_analysis': '...', 'observations_match': {...} (si observations está disponible)}]}]}",
        agent=agent
    )

def create_single_meet_extraction_task(agent, meet_id: str):
    """Tarea de extracción de datos de un meet específico"""
    return Task(
        description=f"""
        ⏱️ Antes de comenzar, imprime: START SINGLE_MEET_EXTRACTION [YYYY-MM-DD HH:MM:SS]. Al finalizar, imprime: END SINGLE_MEET_EXTRACTION [YYYY-MM-DD HH:MM:SS].

        Extraer todos los datos necesarios para evaluar el meet con ID: {meet_id}
        
        Debes obtener:
        - Información completa del meet (id, jd_interviews_id)
        - Conversación asociada al meet (conversation_data)
        - Datos completos del candidato (id, name, email, phone, cv_url, tech_stack)
        - Información del JD interview asociado (id, interview_name, agent_id, job_description, client_id)
        - Información del cliente asociado (id, name, email, phone)
        
        **IMPORTANTE:** Debes usar la herramienta get_meet_evaluation_data pasando el meet_id: {meet_id}
        El meet_id que debes usar es: {meet_id}
        NO uses placeholders como "<MEET_ID>" o variables, usa el valor exacto: {meet_id}
        
        Ejemplo de uso correcto: get_meet_evaluation_data(meet_id="{meet_id}")
        """,
        expected_output="JSON completo con meet, conversation, candidate, jd_interview y client",
        max_iter=2,
        agent=agent
    )

def create_elevenlabs_prompt_generation_task(agent, interview_name: str, job_description: str, sender_email: str):
    """Tarea para generar el prompt específico de ElevenLabs basado en la JD y extraer datos del cliente"""
    return Task(
        description=f"""
        Genera un prompt específico y detallado para un agente de voz de ElevenLabs que realizará entrevistas técnicas,
        y extrae los datos del cliente desde la descripción del puesto.
        
        **CONTEXTO:**
        - Nombre de la búsqueda: {interview_name}
        - Descripción del puesto: {job_description}
        - Email del remitente: {sender_email}
        
        **OBJETIVO:**
        1. Crear un prompt que defina el rol del entrevistador técnico basado en la descripción del puesto.
        2. Extraer datos del cliente desde la descripción del puesto.
        
        **INSTRUCCIONES PARA EL PROMPT:**
        1. Analiza la descripción del puesto y extrae:
           - Tecnologías principales requeridas
           - Herramientas y frameworks mencionados
           - Responsabilidades técnicas clave
           - Nivel de experiencia esperado
           - Conocimientos específicos necesarios
        
        2. Crea un prompt que:
           - Defina el rol del entrevistador como un profesional técnico especializado en estas tecnologías
           - Especifique qué conocimientos técnicos debe evaluar
           - Proporcione contexto sobre el puesto y sus responsabilidades
           - Establezca el tono profesional pero amigable
           - Sea específico para esta búsqueda, no genérico
           - Incluya de forma EXPLÍCITA la estructura de preguntas que debe seguir el agente de voz:
             
             1. **1 PREGUNTA DE RESPONSABILIDADES EN EXPERIENCIA LABORAL:**
                - El primer paso SIEMPRE debe ser hacer 1 (UNA) pregunta sobre la experiencia laboral del candidato.
                - Antes de preguntar, el agente debe leer del JSON devuelto por la herramienta `get-candidate-info` las propiedades `"responsibilities"` y `"experiencia"` (o estructuras equivalentes dentro de `experience`).
                - Debe tomar algunas de las responsabilidades que tuvo el candidato en trabajos previos para formular una pregunta concreta sobre UNA de esas responsabilidades.
                - Si esta información NO está disponible en el JSON (no hay `responsibilities` ni `experiencia` ni datos equivalentes), el agente debe **seguir adelante igualmente**, haciendo una pregunta general sobre responsabilidades en su experiencia laboral SIN fallar ni detener la entrevista.
             
             2. **1 PREGUNTA DE HABILIDADES BLANDAS:**
                - Realizar 1 (UNA) pregunta sobre habilidades blandas del candidato (comunicación, trabajo en equipo, liderazgo, resolución de problemas, adaptabilidad, etc.).
             
             3. **3 PREGUNTAS TÉCNICAS DEL PUESTO:**
                - Realizar 3 (TRES) preguntas técnicas específicas basadas en la descripción del puesto y el stack tecnológico requerido.
                - Las preguntas deben estar directamente relacionadas con las tecnologías, herramientas y conocimientos técnicos mencionados en la JD.
             
             4. **REGLAS IMPORTANTES:**
                - NO hagas más de 1 pregunta sobre la experiencia del candidato.
                - NO hagas más de 1 pregunta de habilidades blandas.
                - NO hagas más de 3 preguntas técnicas.
                - En total deben ser exactamente 5 preguntas (1 experiencia, 1 soft skill, 3 técnicas).
                - Al finalizar las 5 preguntas, el agente debe agradecer al candidato y cerrar la entrevista de forma cordial.
                - Siempre que alguna información proviniente de `get-candidate-info` no esté disponible en el JSON (por ejemplo `responsibilities` o `experiencia`), el agente debe **continuar normalmente** sin bloquearse, haciendo preguntas más generales sin depender de esos campos.
        
        3. El prompt debe:
           - Estar en español
           - Ser conciso pero completo
           - Incluir las reglas anteriores sobre la cantidad y tipo de preguntas
           - Enfocarse en definir el rol, el contexto del entrevistador y la estructura de la entrevista (5 preguntas en total)
        
        **INSTRUCCIONES PARA EXTRACCIÓN DE DATOS DEL CLIENTE:**
        Extrae los siguientes datos del cliente desde la descripción del puesto (busca en el formato "Cliente: X - Responsable: Y - Teléfono: Z"):
        - **nombre_cliente**: Nombre de la empresa/cliente (buscar después de "Cliente:" y antes del siguiente guion)
        - **responsable**: Nombre del responsable (buscar después de "Responsable:" y antes del siguiente guion)
        - **email**: Usar el email del remitente ({sender_email}) como email del cliente
        - **telefono**: Teléfono del cliente (buscar después de "Teléfono:" y antes del siguiente guion, o buscar cualquier número de teléfono en el texto)
        
        **INSTRUCCIONES PARA GENERAR NOMBRE DEL AGENTE:**
        Genera el nombre del agente de ElevenLabs en el formato: "Nombre del Cliente - Búsqueda solicitada"
        - Extrae el nombre del cliente desde la descripción del puesto
        - Extrae la tecnología o búsqueda principal mencionada en la descripción del puesto
        - Formato: "{{nombre_cliente}} - Búsqueda {{tecnologia}}"
        - Ejemplo: "Technova SA - Búsqueda ReactJS"
        - Si no encuentras nombre del cliente, usa el dominio del email del remitente
        - Si no encuentras tecnología específica, usa "Desarrollador" como búsqueda
        
        **FORMATO DE SALIDA (JSON):**
        {{
            "prompt": "Actúa como un entrevistador técnico...",
            "cliente": {{
                "nombre": "Nombre del Cliente",
                "responsable": "Nombre del Responsable",
                "email": "{sender_email}",
                "telefono": "1234567890"
            }},
            "agent_name": "Nombre del Cliente - Búsqueda Tecnología"
        }}
        
        Si no encuentras algún dato, usa null o una cadena vacía.
        """,
        expected_output="JSON con tres campos: 'prompt' (texto del prompt), 'cliente' (objeto con nombre, responsable, email, telefono) y 'agent_name' (nombre del agente en formato 'Cliente - Búsqueda')",
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
        
        ### Análisis de Emociones de Voz (si está disponible):
        Si los datos incluyen `emotion_analysis` en la conversación, realizar un análisis profundo:
        - **Tono no lingüístico (Prosody)**: Analizar las emociones detectadas en la voz continua del candidato.
          * Identificar las emociones predominantes (top 3-5) y su intensidad (basado en averageScore)
          * Analizar qué emociones son más frecuentes y qué significan en el contexto de la entrevista
          * Relacionar las emociones detectadas con las respuestas del candidato y su comportamiento comunicativo
          * **CRÍTICO: Generar un resumen interpretativo de MÍNIMO 3-4 renglones (NO menos) que explique detalladamente qué revelan estas emociones sobre el candidato**
          * El resumen debe ser extenso y detallado, incluyendo: emociones principales con porcentajes específicos, intensidad emocional, significado contextual profundo, correlación con el comportamiento durante la entrevista, y posibles implicaciones sobre el perfil del candidato
          * Ejemplo completo de 3-4 renglones: "El candidato mostró predominantemente Concentración (47.6%), Determinación (37.9%) y Contemplación (31.4%) con intensidad muy alta en su tono de voz continua durante toda la entrevista. Esta combinación emocional sugiere un enfoque serio, comprometido y reflexivo, indicando que el candidato se toma el proceso de selección con gran seriedad y demuestra capacidad de análisis profundo en sus respuestas. La alta intensidad de estas emociones positivas refleja confianza en sus conocimientos y preparación adecuada para el puesto. Además, la presencia constante de Contemplación sugiere que el candidato procesa cuidadosamente las preguntas antes de responder, lo cual es una señal positiva de pensamiento crítico y profesionalismo."
        
        - **Expresiones (Burst)**: Analizar las emociones detectadas en los vocal bursts (expresiones breves).
          * Identificar las emociones más frecuentes (top 3-5) en momentos de expresión espontánea
          * Analizar la coherencia entre lo que dice el candidato y sus expresiones emocionales
          * Detectar posibles señales de nerviosismo, confianza, entusiasmo o preocupación
          * **CRÍTICO: Generar un resumen interpretativo de MÍNIMO 3-4 renglones (NO menos) que explique detalladamente el significado de estas expresiones**
          * El resumen debe ser extenso y detallado, incluyendo: emociones principales con porcentajes específicos, intensidad emocional, significado contextual profundo, análisis de coherencia con el contenido verbal, y posibles señales positivas o de alerta
          * Ejemplo completo de 3-4 renglones: "Las expresiones espontáneas (vocal bursts) mostraron principalmente Alegría (38.5%), Amusement (37.2%) y Excitement (20.0%) con intensidad moderada a alta a lo largo de la entrevista. Esto indica genuino interés y entusiasmo por el puesto, así como una actitud positiva y relajada durante el proceso de selección. La presencia consistente de estas emociones positivas sugiere que el candidato se siente cómodo con el proceso y muestra autenticidad en sus respuestas, lo cual es una señal muy positiva de transparencia y confianza. La combinación de Alegría y Excitement especialmente en momentos clave de la conversación refleja que el candidato está genuinamente interesado en la oportunidad y no está simplemente cumpliendo con un proceso formal."
        
        - **Integración con el análisis general**: 
          * Usar los datos de emociones para enriquecer el análisis de habilidades blandas
          * Correlacionar las emociones detectadas con la evaluación de inteligencia emocional
          * Considerar las emociones como contexto adicional para entender mejor las respuestas del candidato
          * Si hay inconsistencias entre lo que dice y sus emociones, mencionarlo como observación
        
        **IMPORTANTE sobre análisis de emociones:**
        - Si `emotion_analysis` está presente en los datos, DEBES incluirlo en tu análisis
        - Usa los datos de `prosody.summary` y `burst.summary` para identificar emociones predominantes (top 3-5)
        - **CRÍTICO: Genera resúmenes textuales interpretativos de MÍNIMO 3-4 renglones para cada uno (prosody y burst)**
        - Los resúmenes NO deben ser cortos (1-2 renglones), deben ser extensos y detallados (3-4 renglones mínimo)
        - Incluye porcentajes específicos de las emociones, intensidad emocional, significado contextual profundo, y análisis de implicaciones
        - Incluye este análisis en `conversation_analysis.emotion_sentiment_summary` con:
          * `prosody_summary_text`: Resumen interpretativo extenso (3-4 renglones mínimo) del tono no lingüístico
          * `burst_summary_text`: Resumen interpretativo extenso (3-4 renglones mínimo) de las expresiones
        - Si NO hay datos de `emotion_analysis`, simplemente omite esta sección
        
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
            }},
            "emotion_sentiment_summary": {{
              "prosody_summary_text": "Resumen interpretativo del tono no lingüístico (solo si hay datos de emotion_analysis)",
              "burst_summary_text": "Resumen interpretativo de las expresiones (solo si hay datos de emotion_analysis)",
              "raw_emotion_analysis": {{}}
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
        
        **⚠️ PROHIBICIÓN ABSOLUTA - REGLAS CRÍTICAS:**
        
        1. **NUNCA INVENTES DATOS:**
           - NO inventes nombres, emails, teléfonos, proyectos, empresas o experiencias
           - NO inventes respuestas del candidato que no estén en conversation_data
           - NO inventes preguntas técnicas que no estén en la conversación
           - NO inventes datos de clientes o empresas
           - NO asumas información que no esté explícitamente en los datos proporcionados
        
        2. **SOLO USA DATOS REALES:**
           - Usa ÚNICAMENTE la información que viene de get_meet_evaluation_data
           - Todo debe estar basado en conversation_data, candidate, jd_interview o client
           - Si no hay evidencia para evaluar algo, escribe: "No hay evidencia suficiente en los datos proporcionados"
        
        3. **PARA HABILIDADES BLANDAS:**
           - Analiza SOLO lo que el candidato dijo o demostró en la conversación
           - Si no hay evidencia de una habilidad, indica: "No se encontró evidencia suficiente en la conversación"
           - NO inventes ejemplos o situaciones que no estén en conversation_data
        
        4. **PARA PREGUNTAS TÉCNICAS:**
           - Copia EXACTAMENTE el texto de las preguntas que están en conversation_data
           - Copia EXACTAMENTE las respuestas del candidato que están en conversation_data
           - NO inventes preguntas o respuestas que no estén en los datos
           - Si no hay preguntas técnicas en la conversación, indica: "No se encontraron preguntas técnicas en la conversación"
        
        5. **PARA EVALUACIÓN DE MATCH:**
           - Compara SOLO lo que está en los datos reales
           - NO inventes tecnologías, proyectos o experiencias del candidato
           - NO inventes requisitos de la JD que no estén en job_description
        
        6. **PARA ANÁLISIS DE EMOCIONES:**
           - Si los datos incluyen `emotion_analysis` en `conversation`, DEBES analizarlo
           - Usa los datos de `prosody.summary` y `burst.summary` para identificar emociones predominantes (top 3-5)
           - **CRÍTICO: Genera resúmenes interpretativos de MÍNIMO 3-4 renglones (NO menos) que expliquen detalladamente qué significan las emociones en el contexto de la entrevista**
           - Los resúmenes deben ser EXTENSOS y DETALLADOS, incluyendo: emociones principales con porcentajes específicos, intensidad emocional, significado contextual profundo, correlación con el comportamiento, y análisis de implicaciones sobre el perfil del candidato
           - NO generes resúmenes cortos (1-2 renglones), deben ser extensos (3-4 renglones mínimo)
           - Sé exhaustivo en el análisis: proporciona información sustancial y detallada sobre cada aspecto emocional
           - NO inventes emociones que no estén en los datos
           - Si NO hay datos de `emotion_analysis`, simplemente omite la sección `emotion_sentiment_summary`
        
        IMPORTANTE: 
        - Ser exhaustivo pero conciso
        - Basar todas las evaluaciones en evidencia específica REAL de los datos
        - Si no hay evidencia, indicarlo claramente en lugar de inventar
        - Todo el análisis en ESPAÑOL LATINO
        - Proporcionar justificaciones claras para la determinación de match basadas SOLO en datos reales
        """,
        expected_output="JSON completo con análisis exhaustivo y determinación de match potencial",
        agent=agent,
        context=[extraction_task]
    )