#!/usr/bin/env python3
"""
Script de prueba rápida para un CV específico
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

def test_specific_cv(filename):
    """Prueba la extracción de un CV específico"""
    print("=" * 80)
    print(f"PRUEBA DE EXTRACCIÓN: {filename}")
    print("=" * 80)
    print()
    
    try:
        from tools.cv_tools import download_cv_from_s3
        
        print(f"📥 Descargando: {filename}")
        print()
        
        result_json = download_cv_from_s3(filename)
        result = json.loads(result_json)
        
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        print()
        
        if result.get('success'):
            print("✅ ÉXITO - Extracción completada")
            print()
            print(f"📄 Archivo: {result.get('filename')}")
            print(f"📁 S3 Key: {result.get('s3_key')}")
            print(f"📦 Bucket: {result.get('bucket')}")
            print(f"📝 Tipo: {result.get('file_type')}")
            print(f"📊 Caracteres extraídos: {result.get('content_length')}")
            print()
            print("ℹ️  NOTA: El sistema intentó 4 métodos de extracción:")
            print("   1. pdfplumber  2. PyPDF2  3. pdfminer.six  4. AWS Textract OCR")
            print("   Si el PDF era una imagen, se usó OCR automáticamente (método 4)")
            print("   Revisa los logs arriba para ver qué método funcionó.")
            print()
            
            content = result.get('text_content', '')
            if content:
                print("=" * 80)
                print("PREVIEW DEL CONTENIDO (primeros 800 caracteres):")
                print("=" * 80)
                print(content[:800])
                if len(content) > 800:
                    print("\n... (contenido truncado)")
                print()
            else:
                print("⚠️ El contenido extraído está vacío")
                print()
        else:
            print("❌ ERROR - No se pudo extraer el CV")
            print()
            print(f"🔴 Tipo de error: {result.get('error_type', 'Unknown')}")
            print(f"🔴 Mensaje: {result.get('error')}")
            print()
            
            if result.get('s3_bucket'):
                print(f"📦 Bucket: {result.get('s3_bucket')}")
            if result.get('s3_key'):
                print(f"📁 Key: {result.get('s3_key')}")
            if result.get('s3_region'):
                print(f"🌍 Región: {result.get('s3_region')}")
            print()
            
            # Sugerencias según el tipo de error
            error_msg = result.get('error', '').lower()
            if 'ocr' in error_msg or 'escaneado' in error_msg or 'imagen' in error_msg:
                print("💡 SOLUCIÓN SUGERIDA:")
                print("-" * 80)
                print("El PDF parece ser una imagen escaneada. Opciones:")
                print()
                print("1. Usar AWS Textract para extraer texto de la imagen:")
                print("   https://aws.amazon.com/textract/")
                print()
                print("2. Usar Tesseract OCR localmente:")
                print("   pip install pytesseract pdf2image")
                print()
                print("3. Convertir el PDF a texto usando un servicio online")
                print()
                print("4. Solicitar el CV en formato Word o texto plano")
                print("-" * 80)
            elif 'access' in error_msg or 'denied' in error_msg:
                print("💡 SOLUCIÓN SUGERIDA:")
                print("-" * 80)
                print("Problema de permisos de AWS. Verifica:")
                print("1. Las credenciales en .env son correctas")
                print("2. El usuario IAM tiene permisos s3:GetObject")
                print("3. El bucket y archivo existen en la región correcta")
                print("-" * 80)
        
        print()
        print("=" * 80)
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Error inesperado: {type(e).__name__}")
        print(f"   {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Archivo específico que está dando problemas
    default_filename = "2025-10-13T13-34-07-cv1760362447161.pdf"
    
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        print(f"Usando archivo por defecto: {default_filename}")
        print("(Puedes pasar otro archivo como argumento: python test_specific_cv.py archivo.pdf)")
        print()
        filename = default_filename
    
    test_specific_cv(filename)

