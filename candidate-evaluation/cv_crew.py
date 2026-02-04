# cv_crew.py
"""
Crew independiente para procesamiento de CVs
"""
from crewai import Crew, Task
from cv_agent import create_cv_analyzer_agent
from utils.logger import evaluation_logger


def create_cv_analysis_crew(filename: str, user_id: str = None, client_id: str = None):
    """
    Crea un crew especializado para analizar un CV desde S3
    
    Args:
        filename: Nombre del archivo CV en S3
        user_id: ID del usuario que crea el candidato (opcional)
        client_id: ID del cliente asociado (opcional)
        
    Returns:
        Crew configurado para análisis de CV
    """
    # Crear agente
    cv_analyzer = create_cv_analyzer_agent()
    
    # Definir tarea
    analyze_task = Task(
        description=f"""
        Analiza el CV del archivo '{filename}' que está almacenado en el bucket S3 'hhrr-ai-multiagents/cvs'.
        
        Pasos a seguir:
        1. Descarga el CV desde S3 usando la herramienta download_cv_from_s3 con el nombre de archivo: {filename}
        2. Una vez descargado, verifica que la descarga fue exitosa (success: true)
        3. Si la descarga falló o el contenido está vacío, reporta el error claramente
        4. Si la descarga fue exitosa, extrae el texto completo del CV
        5. Analiza el texto del CV para extraer la siguiente información:
           - Nombre y apellido del candidato
           - Email de contacto
           - Teléfono de contacto
           - LinkedIn: URL del perfil de LinkedIn (si está presente en el CV)
           - Tech_stack: Array con todas las tecnologías, lenguajes, frameworks y herramientas mencionadas
           - INFORMACIÓN ADICIONAL (para el campo observations en formato JSON):
             * work_experience: Array de objetos con experiencia laboral desde la más reciente hasta la más antigua. Cada objeto debe tener: company (empresa), position (cargo), period (período en formato "MM/YYYY - MM/YYYY" o "MM/YYYY - Present"), duration_months (duración aproximada en meses), responsibilities (array de responsabilidades principales)
             * industries_and_sectors: Array de objetos con rubros/industrias ordenados por tiempo de experiencia (de mayor a menor). Cada objeto debe tener: industry (nombre del rubro), experience_months (tiempo aproximado en meses)
             * languages: Array de objetos con idiomas y sus niveles. Cada objeto debe tener: language (nombre del idioma), level (nivel: "basic", "intermediate", "advanced", "native", etc.)
             * certifications_and_courses: Array de objetos con certificaciones y cursos. Cada objeto debe tener: name (nombre), issuer (institución/emisor), date (fecha si está disponible), type ("certification" o "course")
             * other: String con cualquier otra información relevante (proyectos destacados, publicaciones, premios, reconocimientos, etc.)
        6. Formatea toda la información adicional en un JSON válido para el campo observations, usando el siguiente formato estricto:
           
           {{
             "work_experience": [
               {{
                 "company": "Nombre de la empresa",
                 "position": "Cargo/Posición",
                 "period": "MM/YYYY - MM/YYYY o MM/YYYY - Present",
                 "duration_months": número_aproximado,
                 "responsibilities": ["responsabilidad 1", "responsabilidad 2", ...]
               }},
               ...
             ],
             "industries_and_sectors": [
               {{
                 "industry": "Nombre del rubro/industria",
                 "experience_months": número_aproximado
               }},
               ...
             ],
             "languages": [
               {{
                 "language": "Nombre del idioma",
                 "level": "basic|intermediate|advanced|native"
               }},
               ...
             ],
             "certifications_and_courses": [
               {{
                 "name": "Nombre del curso/certificación",
                 "issuer": "Institución/Emisor",
                 "date": "MM/YYYY o null",
                 "type": "certification|course"
               }},
               ...
             ],
             "other": "Cualquier otra información relevante o null"
           }}
           
           IMPORTANTE: El JSON debe ser válido y estar correctamente formateado. Si algún campo no tiene información, usa un array vacío [] o null según corresponda.
           
        7. Crea o actualiza el candidato en la tabla 'candidates' usando la herramienta create_candidate, con los campos:
           - name, email, phone, linkedin (si está disponible), tech_stack (array)
           - observations: El JSON string con toda la información adicional extraída (debe ser un JSON válido)
           - cv_url: Construir como "https://hhrr-ai-multiagents.s3.us-east-1.amazonaws.com/cvs/{filename}"
           {f" - user_id: {user_id}, client_id: {client_id} (IMPORTANTE: incluir estos parámetros si están disponibles)" if user_id and client_id else ""}
        8. Confirma el resultado del upsert devolviendo el ID o el registro creado
        
        FORMATO DE SALIDA REQUERIDO:
        Debes retornar la información en el siguiente formato estructurado:
        
        ========================================
        ANÁLISIS DE CV - {filename}
        ========================================
        
        📋 DATOS DEL CANDIDATO:
        ----------------------
        Nombre y Apellido: [nombre completo extraído]
        Email: [email extraído o "No especificado"]
        Teléfono: [teléfono extraído o "No especificado"]
        LinkedIn: [URL de LinkedIn extraída o "No especificado"]
        
        💻 TECH STACK:
        --------------
        [Lista de tecnologías separadas por comas o como array]
        
        📝 OBSERVACIONES (Información Adicional en JSON):
        -------------------------------------------------
        [JSON string con la estructura: work_experience, industries_and_sectors, languages, certifications_and_courses, other]
        
        ========================================
        
        INSTRUCCIONES IMPORTANTES:
        - Si algún dato no está presente, usa arrays vacíos [] o null según corresponda
        - Para tech_stack, incluye TODAS las tecnologías mencionadas (lenguajes, frameworks, bases de datos, cloud, etc.)
        - Para observations, DEBES generar un JSON válido con la estructura especificada
        - El JSON debe ser parseable y estar correctamente formateado
        - No inventes información que no esté en el CV
        - Extrae los datos exactamente como aparecen en el documento
        - Para experiencia laboral, ordénala desde la más reciente hasta la más antigua
        - Para rubros, ordénalos por tiempo de experiencia aproximado (de mayor a menor)
        - Si no hay información para alguna sección, usa un array vacío [] o null
        
        MANEJO DE ERRORES:
        - Si el CV no se pudo descargar o extraer, reporta:
          * El nombre del archivo
          * El tipo de error específico
          * Posibles soluciones o causas
        - Si el CV es una imagen escaneada, indica que se requiere OCR
        - Si hay problemas de permisos AWS, indica los pasos para solucionarlo
        """,
        expected_output="""
        Un reporte estructurado con:
        - Nombre y apellido del candidato
        - Email de contacto
        - Teléfono de contacto
        - LinkedIn (si está disponible)
        - Tech_stack en formato de array o lista
        - Observations: JSON string válido con la estructura:
          {
            "work_experience": [...],
            "industries_and_sectors": [...],
            "languages": [...],
            "certifications_and_courses": [...],
            "other": "..."
          }
        - Resultado de creación/actualización en Supabase (candidates)
        Todo presentado de forma clara y legible, con el JSON de observations correctamente formateado
        """,
        agent=cv_analyzer
    )
    
    # Crear crew
    crew = Crew(
        agents=[cv_analyzer],
        tasks=[analyze_task],
        verbose=True
    )
    
    evaluation_logger.log_task_start("CV Analysis Crew", f"Crew creado para analizar: {filename}")
    
    return crew

