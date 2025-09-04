#!/usr/bin/env python3
"""
Script principal para ejecutar el proceso de evaluación de candidatos con logging completo
"""

import os
import sys
import json
from datetime import datetime
from crew import create_data_processing_crew
from utils.logger import evaluation_logger

def main():
    """Función principal que ejecuta todo el proceso de evaluación"""
    try:
        print("="*80)
        print("🚀 SISTEMA DE EVALUACIÓN DE CANDIDATOS")
        print("="*80)
        
        # Inicializar logging
        start_time = datetime.now()
        evaluation_logger.logger.info("="*80)
        evaluation_logger.logger.info("🚀 INICIANDO PROCESO DE EVALUACIÓN DE CANDIDATOS")
        evaluation_logger.logger.info(f"⏰ Fecha y hora de inicio: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        evaluation_logger.logger.info("="*80)
        
        # Verificar variables de entorno
        required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            evaluation_logger.log_error("Configuración", f"Variables de entorno faltantes: {missing_vars}")
            print(f"❌ Error: Variables de entorno faltantes: {missing_vars}")
            return
        
        evaluation_logger.log_task_progress("Configuración", "Variables de entorno verificadas correctamente")
        
        # Crear y ejecutar crew
        evaluation_logger.log_task_start("Proceso Principal", "Crew Manager")
        crew = create_data_processing_crew()
        
        print("\n📊 Ejecutando análisis de candidatos...")
        print("   - Extrayendo datos de Supabase")
        print("   - Analizando conversaciones")
        print("   - Evaluando job descriptions")
        print("   - Generando comparaciones")
        print("   - Procesando reportes finales")
        print("   - Enviando resultados por email")
        print("\n⏳ Este proceso puede tomar varios minutos...\n")
        
        # Ejecutar el crew
        result = crew.kickoff()
        
        # Guardar resultados localmente también
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_results_{timestamp}.json"
        
        try:
            result_json = json.loads(str(result))
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result_json, f, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            with open(filename.replace('.json', '.txt'), 'w', encoding='utf-8') as f:
                f.write(str(result))
            filename = filename.replace('.json', '.txt')
        
        # Calcular tiempo de ejecución
        end_time = datetime.now()
        execution_time = end_time - start_time
        
        # Log de finalización
        evaluation_logger.log_task_complete("Proceso Principal", f"Proceso completado en {execution_time}")
        evaluation_logger.logger.info("="*80)
        evaluation_logger.logger.info("✅ PROCESO DE EVALUACIÓN COMPLETADO EXITOSAMENTE")
        evaluation_logger.logger.info(f"⏰ Tiempo total de ejecución: {execution_time}")
        evaluation_logger.logger.info(f"📁 Logs guardados en: {evaluation_logger.logs_dir}")
        evaluation_logger.logger.info(f"📄 Resultados guardados en: {filename}")
        evaluation_logger.logger.info("="*80)
        
        print("\n" + "="*80)
        print("✅ PROCESO COMPLETADO EXITOSAMENTE")
        print(f"⏰ Tiempo de ejecución: {execution_time}")
        print(f"📁 Logs guardados en: {evaluation_logger.logs_dir}")
        print(f"📄 Resultados guardados en: {filename}")
        print("📧 Resultados enviados por email")
        print("="*80)
        
        return result
        
    except KeyboardInterrupt:
        evaluation_logger.log_error("Proceso Principal", "Proceso interrumpido por el usuario")
        print("\n❌ Proceso interrumpido por el usuario")
        
    except Exception as e:
        end_time = datetime.now()
        execution_time = end_time - start_time
        
        evaluation_logger.log_error("Proceso Principal", f"Error crítico: {str(e)}")
        evaluation_logger.logger.error("="*80)
        evaluation_logger.logger.error("❌ PROCESO FALLIDO")
        evaluation_logger.logger.error(f"⏰ Tiempo antes del fallo: {execution_time}")
        evaluation_logger.logger.error(f"🔍 Error: {str(e)}")
        evaluation_logger.logger.error("="*80)
        
        print(f"\n❌ Error crítico: {str(e)}")
        print(f"📁 Logs con detalles del error en: {evaluation_logger.logs_dir}")
        raise

if __name__ == "__main__":
    main()