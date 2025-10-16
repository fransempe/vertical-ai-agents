import os
import io
import re
import json
import boto3
import pdfplumber
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text as pdfminer_extract_text
from docx import Document
from typing import Dict, Any, Optional
from crewai.tools import tool
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.logger import evaluation_logger

load_dotenv()

# Configuración de AWS S3
S3_BUCKET = "hhrr-ai-multiagents"
S3_REGION = "us-east-1"
S3_PREFIX = "cvs/"


def _get_s3_client():
    """
    Crea y retorna un cliente de S3 configurado con las credenciales correctas
    """
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", S3_REGION)
    
    if not aws_access_key_id:
        raise ValueError("AWS_ACCESS_KEY_ID not found in environment variables. Please set it in .env file")
    
    if not aws_secret_access_key:
        raise ValueError("AWS_SECRET_ACCESS_KEY not found in environment variables. Please set it in .env file")
    
    # Verificar que las credenciales funcionen haciendo una llamada simple (sin logging)
    try:
        # Crear cliente con configuración explícita
        s3_client = boto3.client(
            's3',
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        return s3_client
    except Exception as e:
        evaluation_logger.log_error("AWS S3", f"Error creando cliente S3: {str(e)}")
        raise ValueError(f"Failed to create S3 client: {str(e)}")


def _extract_text_from_pdf_with_textract(file_content: bytes) -> str:
    """
    Extrae texto de PDF usando AWS Textract OCR (para PDFs escaneados/imágenes)
    
    Args:
        file_content: Contenido del archivo PDF en bytes
        
    Returns:
        Texto extraído del PDF usando OCR
    """
    try:
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", S3_REGION)
        
        textract = boto3.client(
            'textract',
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        
        # Verificar tamaño del archivo (máximo 5MB para sincrónico)
        file_size_mb = len(file_content) / (1024 * 1024)
        
        if file_size_mb > 5:
            raise Exception(
                f"El archivo es muy grande ({file_size_mb:.2f} MB). "
                "Textract síncrono solo soporta hasta 5MB. "
                "Considera comprimir el PDF o usar procesamiento asíncrono."
            )
        
        # Usar DetectDocumentText para extracción simple de texto
        response = textract.detect_document_text(
            Document={'Bytes': file_content}
        )
        
        # Extraer el texto de la respuesta
        text = ""
        line_count = 0
        
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                text += block['Text'] + "\n"
                line_count += 1
        
        if text.strip():
            return text.strip()
        else:
            raise Exception("Textract no encontró texto en el documento")
            
    except Exception as e:
        error_msg = str(e)
        
        # Mensajes de error más descriptivos
        if "AccessDeniedException" in error_msg:
            raise Exception(
                "Acceso denegado a AWS Textract. "
                "El usuario IAM necesita el permiso 'textract:DetectDocumentText'. "
                "Agrega la política AmazonTextractFullAccess o crea una política personalizada."
            )
        elif "InvalidParameterException" in error_msg:
            raise Exception(f"Parámetro inválido en Textract: {error_msg}")
        elif "ProvisionedThroughputExceededException" in error_msg:
            raise Exception("Límite de Textract excedido. Espera unos segundos y reintenta.")
        else:
            raise Exception(f"Error en Textract OCR: {error_msg}")


def _extract_text_from_pdf(file_content: bytes) -> str:
    """
    Extrae texto de un archivo PDF usando múltiples métodos de extracción
    
    Args:
        file_content: Contenido del archivo PDF en bytes
        
    Returns:
        Texto extraído del PDF
    """
    text = ""
    pdf_bytes = io.BytesIO(file_content)
    
    # MÉTODO 1: pdfplumber (mejor para PDFs con tablas y layouts complejos)
    try:
        pdf_bytes.seek(0)  # Resetear posición
        
        with pdfplumber.open(pdf_bytes) as pdf:
            num_pages = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                
                if page_text and page_text.strip():
                    text += page_text + "\n\n"
                else:
                    pass
        
        if text.strip():
            return text.strip()
        else:
            pass
    except Exception:
        pass
    
    # MÉTODO 2: PyPDF2 (más rápido, mejor para PDFs simples)
    try:
        pdf_bytes.seek(0)  # Resetear posición
        
        pdf_reader = PdfReader(pdf_bytes)
        num_pages = len(pdf_reader.pages)
        
        text = ""
        for i, page in enumerate(pdf_reader.pages, 1):
            page_text = page.extract_text()
            
            if page_text and page_text.strip():
                text += page_text + "\n\n"
            else:
                pass
        
        if text.strip():
            return text.strip()
        else:
            pass
    except Exception:
        pass
    
    # MÉTODO 3: pdfminer.six (más robusto para PDFs difíciles)
    try:
        pdf_bytes.seek(0)  # Resetear posición
        
        text = pdfminer_extract_text(pdf_bytes)
        
        if text and text.strip():
            return text.strip()
        else:
            pass
    except Exception:
        pass
    
    # MÉTODO 4: AWS Textract OCR (para PDFs escaneados/imágenes)
    try:
        text = _extract_text_from_pdf_with_textract(file_content)
        
        if text and text.strip():
            return text.strip()
        else:
            pass
    except Exception as e:
        evaluation_logger.log_error("Extracción PDF", f"⚠ Textract OCR falló: {str(e)}")
        
        # Si Textract falla, proporcionar información de diagnóstico (sin logging)
        try:
            pdf_bytes.seek(0)
            pdf_reader = PdfReader(pdf_bytes)
            _ = {
                "num_pages": len(pdf_reader.pages),
                "is_encrypted": pdf_reader.is_encrypted,
                "textract_error": str(e)
            }
        except:
            pass
    
    # Si todos los métodos fallaron
    evaluation_logger.log_error("Extracción PDF", "Todos los métodos de extracción fallaron (incluyendo OCR)")
    
    raise Exception(
        "No se pudo extraer texto del PDF con ningún método disponible (incluyendo OCR). "
        "Posibles causas:\n"
        "1. El PDF está protegido o encriptado\n"
        "2. El PDF está corrupto o tiene un formato no estándar\n"
        "3. El PDF está vacío o no contiene texto ni imágenes legibles\n"
        "4. Textract no tiene permisos (necesita textract:DetectDocumentText)\n"
        "5. El archivo excede los 5MB para procesamiento sincrónico de Textract"
    )


def _extract_text_from_docx(file_content: bytes) -> str:
    """
    Extrae texto de un archivo DOCX
    
    Args:
        file_content: Contenido del archivo DOCX en bytes
        
    Returns:
        Texto extraído del DOCX
    """
    try:
        doc = Document(io.BytesIO(file_content))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except Exception as e:
        raise Exception(f"Error extracting text from DOCX: {str(e)}")


def _extract_text_from_doc(file_content: bytes) -> str:
    """
    Extrae texto de un archivo DOC (formato antiguo)
    Nota: Para archivos .doc antiguos, se recomienda convertirlos a .docx primero
    
    Args:
        file_content: Contenido del archivo DOC en bytes
        
    Returns:
        Texto extraído del DOC
    """
    # Para archivos .doc antiguos, intentamos con python-docx de todas formas
    # Si no funciona, se puede usar antiword o convertir a .docx primero
    try:
        return _extract_text_from_docx(file_content)
    except Exception as e:
        raise Exception(f"Error extracting text from DOC: {str(e)}. Consider converting to DOCX format.")


@tool
def download_cv_from_s3(filename: str) -> str:
    """
    Descarga un CV desde S3 y extrae su contenido como texto.
    
    Args:
        filename: Nombre del archivo en S3 (ej: "cv_juan_perez.pdf")
        
    Returns:
        JSON string con el contenido del CV y metadata
    """
    try:
        
        # Agregar el prefijo 'cvs/' al filename si no lo tiene
        s3_key = filename if filename.startswith(S3_PREFIX) else f"{S3_PREFIX}{filename}"
        
        # Crear cliente S3
        s3_client = _get_s3_client()
        
        # Primero verificar que el archivo existe
        try:
            s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        except s3_client.exceptions.NoSuchKey:
            raise FileNotFoundError(
                f"El archivo '{s3_key}' no existe en el bucket '{S3_BUCKET}'. "
                f"Verifica que el archivo esté en la ubicación correcta."
            )
        except Exception as e:
            raise Exception(f"Error verificando objeto en S3: {str(e)}")
        
        # Descargar archivo
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        file_content = response['Body'].read()
        
        if len(file_content) == 0:
            raise ValueError(f"El archivo '{filename}' está vacío (0 bytes)")
        
        # Detectar tipo de archivo por extensión
        file_extension = filename.lower().split('.')[-1]
        
        # Extraer texto según el tipo de archivo
        if file_extension == 'pdf':
            text_content = _extract_text_from_pdf(file_content)
        elif file_extension == 'docx':
            text_content = _extract_text_from_docx(file_content)
        elif file_extension == 'doc':
            text_content = _extract_text_from_doc(file_content)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}. Supported formats: pdf, doc, docx")
        
        return json.dumps({
            "success": True,
            "filename": filename,
            "s3_key": s3_key,
            "bucket": S3_BUCKET,
            "file_type": file_extension,
            "text_content": text_content,
            "content_length": len(text_content)
        }, indent=2, ensure_ascii=False)
        
    except FileNotFoundError as e:
        evaluation_logger.log_error("Descarga de CV", f"Archivo no encontrado: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"File not found: {str(e)}",
            "error_type": "FileNotFoundError",
            "filename": filename,
            "s3_bucket": S3_BUCKET,
            "s3_key": s3_key if 's3_key' in locals() else f"{S3_PREFIX}{filename}"
        }, indent=2)
    except ValueError as e:
        evaluation_logger.log_error("Descarga de CV", f"Error de configuración: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "ValueError",
            "filename": filename
        }, indent=2)
    except s3_client.exceptions.NoSuchBucket if 's3_client' in locals() else Exception as e:
        evaluation_logger.log_error("Descarga de CV", f"Bucket no encontrado: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"Bucket '{S3_BUCKET}' not found. Verify the bucket name and your AWS permissions.",
            "error_type": "NoSuchBucket",
            "filename": filename,
            "s3_bucket": S3_BUCKET
        }, indent=2)
    except Exception as e:
        # Capturar errores específicos de AWS
        error_message = str(e)
        error_type = type(e).__name__
        
        evaluation_logger.log_error("Descarga de CV", f"Error ({error_type}): {error_message}")
        
        # Mensajes de error más descriptivos según el tipo
        if "AccessDenied" in error_message or "403" in error_message:
            error_detail = (
                "Access Denied. Verifica que:\n"
                "1. Las credenciales AWS sean correctas\n"
                "2. El usuario IAM tenga permisos de lectura (s3:GetObject) en el bucket\n"
                "3. El bucket y objeto existan en la región correcta"
            )
        elif "InvalidAccessKeyId" in error_message:
            error_detail = "Invalid Access Key ID. Verifica que AWS_ACCESS_KEY_ID sea correcto en el archivo .env"
        elif "SignatureDoesNotMatch" in error_message:
            error_detail = "Invalid Secret Key. Verifica que AWS_SECRET_ACCESS_KEY sea correcto en el archivo .env"
        elif "NoSuchKey" in error_message:
            error_detail = f"El archivo no existe en S3. Ruta completa: s3://{S3_BUCKET}/{s3_key if 's3_key' in locals() else filename}"
        else:
            error_detail = error_message
        
        return json.dumps({
            "success": False,
            "error": error_detail,
            "error_type": error_type,
            "filename": filename,
            "s3_bucket": S3_BUCKET,
            "s3_region": S3_REGION
        }, indent=2, ensure_ascii=False)


@tool
def extract_candidate_data(cv_text: str) -> str:
    """
    Extrae datos estructurados del candidato a partir del texto del CV.
    Esta es una herramienta base que el agente puede usar, pero el agente LLM
    hará el análisis real usando sus capacidades de NLP.
    
    Args:
        cv_text: Texto completo del CV
        
    Returns:
        JSON string con los datos extraídos del candidato
    """
    try:
        
        # Patrones regex básicos para ayudar al agente
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
        
        # Buscar emails
        emails = re.findall(email_pattern, cv_text)
        
        # Buscar teléfonos
        phones = re.findall(phone_pattern, cv_text)
        
        # Tecnologías comunes (lista base para ayudar al agente)
        common_techs = [
            'Python', 'JavaScript', 'TypeScript', 'Java', 'C#', 'C++', 'Ruby', 'PHP', 'Go', 'Rust',
            'React', 'Angular', 'Vue', 'Node.js', 'Express', 'Django', 'Flask', 'FastAPI', 'Spring',
            'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Git', 'CI/CD', 'Jenkins',
            'HTML', 'CSS', 'SASS', 'LESS', 'Bootstrap', 'Tailwind',
            'REST', 'GraphQL', 'gRPC', 'WebSocket',
            'TensorFlow', 'PyTorch', 'Scikit-learn', 'Pandas', 'NumPy'
        ]
        
        # Buscar tecnologías mencionadas (case-insensitive)
        found_techs = []
        cv_text_lower = cv_text.lower()
        for tech in common_techs:
            if tech.lower() in cv_text_lower:
                found_techs.append(tech)
        
        return json.dumps({
            "success": True,
            "cv_text": cv_text,
            "extracted_hints": {
                "emails_found": emails,
                "phones_found": phones,
                "technologies_found": found_techs
            },
            "note": "Use estos hints para ayudarte a extraer y estructurar los datos del candidato"
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        evaluation_logger.log_error("Extracción de Datos", f"Error: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

