#!/usr/bin/env python3
"""
Script de prueba para verificar la lectura de CVs desde S3
"""
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_env_vars():
    """Verifica que las variables de entorno necesarias estén configuradas"""
    print("=" * 60)
    print("VERIFICACIÓN DE VARIABLES DE ENTORNO")
    print("=" * 60)
    
    required_vars = {
        'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
        'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY')
    }
    
    all_ok = True
    for var_name, var_value in required_vars.items():
        if var_value:
            masked_value = var_value[:8] + "..." if len(var_value) > 8 else "***"
            print(f"✓ {var_name}: {masked_value}")
        else:
            print(f"✗ {var_name}: NO CONFIGURADA")
            all_ok = False
    
    print()
    return all_ok

def test_s3_connection():
    """Prueba la conexión a S3"""
    print("=" * 60)
    print("PRUEBA DE CONEXIÓN A S3")
    print("=" * 60)
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
        
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        
        print(f"Región AWS: {aws_region}")
        print(f"Access Key: {aws_access_key_id[:8]}..." if aws_access_key_id else "Access Key: NOT SET")
        print()
        
        s3_client = boto3.client(
            's3',
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        
        # Intentar listar archivos en el bucket
        bucket_name = "hhrr-ai-multiagents"
        prefix = "cvs/"
        
        print(f"Conectando a bucket: s3://{bucket_name}/{prefix}")
        print(f"Listando objetos...")
        print()
        
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix,
            MaxKeys=20
        )
        
        if 'Contents' in response:
            print(f"✓ Conexión exitosa! Archivos encontrados en {bucket_name}/{prefix}:")
            print()
            for i, obj in enumerate(response['Contents'], 1):
                size_kb = obj['Size'] / 1024
                # Extraer solo el nombre del archivo sin el prefijo
                filename = obj['Key'].replace(prefix, '')
                if filename:  # Evitar mostrar la carpeta vacía
                    print(f"  {i}. {filename} ({size_kb:.2f} KB)")
            print()
            return True
        else:
            print(f"⚠ No se encontraron archivos en {bucket_name}/{prefix}")
            print("  El bucket existe pero la carpeta está vacía.")
            return False
    
    except NoCredentialsError:
        print("✗ ERROR: Credenciales de AWS no encontradas")
        print("  Verifica que AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY estén en .env")
        print()
        return False
    
    except PartialCredentialsError:
        print("✗ ERROR: Credenciales de AWS incompletas")
        print("  Falta AWS_ACCESS_KEY_ID o AWS_SECRET_ACCESS_KEY")
        print()
        return False
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        print(f"✗ ERROR de AWS: {error_code}")
        print(f"  Mensaje: {error_message}")
        print()
        
        if error_code == 'AccessDenied' or error_code == '403':
            print("  Posibles causas:")
            print("  1. Las credenciales no tienen permisos de lectura (s3:ListBucket)")
            print("  2. El bucket no existe o está en otra región")
            print("  3. Las políticas de IAM no permiten el acceso")
        elif error_code == 'InvalidAccessKeyId':
            print("  El Access Key ID es inválido. Verifica el valor en .env")
        elif error_code == 'SignatureDoesNotMatch':
            print("  El Secret Access Key es incorrecto. Verifica el valor en .env")
        elif error_code == 'NoSuchBucket':
            print(f"  El bucket '{bucket_name}' no existe o está en otra región")
        
        print()
        return False
            
    except Exception as e:
        print(f"✗ Error inesperado conectando a S3: {type(e).__name__}")
        print(f"  {str(e)}")
        print()
        return False

def test_pdf_extraction(filename):
    """Prueba la extracción de texto de un PDF"""
    print("=" * 60)
    print(f"PRUEBA DE EXTRACCIÓN DE PDF: {filename}")
    print("=" * 60)
    
    try:
        from tools.cv_tools import download_cv_from_s3
        import json
        
        print(f"Descargando y extrayendo: {filename}")
        print()
        
        result_json = download_cv_from_s3(filename)
        result = json.loads(result_json)
        
        if result.get('success'):
            print("✓ Extracción exitosa!")
            print(f"  - Archivo: {result.get('filename')}")
            print(f"  - S3 Key: {result.get('s3_key')}")
            print(f"  - Tipo: {result.get('file_type')}")
            print(f"  - Caracteres extraídos: {result.get('content_length')}")
            print()
            print("Preview del contenido:")
            print("-" * 60)
            content = result.get('text_content', '')
            preview = content[:500] if content else "Sin contenido"
            print(preview)
            if len(content) > 500:
                print("\n... (contenido truncado)")
            print("-" * 60)
            print()
            return True
        else:
            print(f"✗ Error en la extracción")
            print(f"  Tipo de error: {result.get('error_type', 'Unknown')}")
            print(f"  Mensaje: {result.get('error')}")
            print()
            if result.get('s3_bucket'):
                print(f"  Bucket: {result.get('s3_bucket')}")
            if result.get('s3_key'):
                print(f"  Key: {result.get('s3_key')}")
            if result.get('s3_region'):
                print(f"  Región: {result.get('s3_region')}")
            print()
            return False
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print()
        return False

def main():
    """Función principal del script de prueba"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "TEST DE LECTURA DE CVs" + " " * 21 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    # Paso 1: Verificar variables de entorno
    if not test_env_vars():
        print("⚠ Por favor configura las variables de entorno faltantes en el archivo .env")
        print()
        print("Ejemplo de .env:")
        print("-" * 60)
        print("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
        print("AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        print("AWS_REGION=us-east-1")
        print("OPENAI_API_KEY=sk-...")
        print("-" * 60)
        sys.exit(1)
    
    # Paso 2: Probar conexión a S3
    s3_ok = test_s3_connection()
    
    if not s3_ok:
        print("⚠ No se pudo conectar a S3. Verifica las credenciales de AWS.")
        print()
        print("Pasos para solucionar:")
        print("1. Ve a AWS IAM Console")
        print("2. Verifica que el usuario tenga los permisos:")
        print("   - s3:ListBucket")
        print("   - s3:GetObject")
        print("3. Verifica que el bucket 'hhrr-ai-multiagents' exista")
        print("4. Verifica que esté en la región correcta (us-east-1)")
        sys.exit(1)
    
    # Paso 3: Probar extracción de PDF
    print("Ingresa el nombre del archivo a probar (o presiona Enter para salir):")
    print("Ejemplo: cv_candidato.pdf")
    filename = input("> ").strip()
    
    if filename:
        test_pdf_extraction(filename)
    
    print()
    print("=" * 60)
    print("FIN DE LAS PRUEBAS")
    print("=" * 60)

if __name__ == "__main__":
    main()

