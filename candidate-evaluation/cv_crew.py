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
        6. Crea o actualiza el candidato en la tabla 'candidates' usando la herramienta create_candidate, con los campos:
           - name, email, phone, linkedin (si está disponible), tech_stack (array)
           - cv_url: Construir como "https://hhrr-ai-multiagents.s3.us-east-1.amazonaws.com/cvs/{filename}"
           {f" - user_id: {user_id}, client_id: {client_id} (IMPORTANTE: incluir estos parámetros si están disponibles)" if user_id and client_id else ""}
        7. Confirma el resultado del upsert devolviendo el ID o el registro creado
        
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
        
        ========================================
        
        INSTRUCCIONES IMPORTANTES:
        - Si algún dato no está presente, indica "No especificado"
        - Para tech_stack, incluye TODAS las tecnologías mencionadas (lenguajes, frameworks, bases de datos, cloud, etc.)
        - No inventes información que no esté en el CV
        - Extrae los datos exactamente como aparecen en el documento
        
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
        - Resultado de creación/actualización en Supabase (candidates)
        Todo presentado de forma clara y legible
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

