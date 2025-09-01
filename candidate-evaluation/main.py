import json
import asyncio
from crew import create_data_processing_crew
from datetime import datetime

async def main():
    """Función principal que ejecuta el crew"""
    print("🚀 Iniciando CrewAI Multi-Agent System...")
    print("=" * 50)
    
    try:
        # Crear el crew
        crew = create_data_processing_crew()
        
        # Ejecutar el crew
        result = crew.kickoff()
        
        # Guardar resultados
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_results_{timestamp}.json"
        
        # Intentar parsear como JSON, si no, guardar como texto
        try:
            result_json = json.loads(str(result))
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result_json, f, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            with open(filename.replace('.json', '.txt'), 'w', encoding='utf-8') as f:
                f.write(str(result))
            filename = filename.replace('.json', '.txt')
        
        print(f"\n✅ Procesamiento completado!")
        print(f"📄 Resultados guardados en: {filename}")
        print("=" * 50)
        
        return result
        
    except Exception as e:
        print(f"❌ Error durante el procesamiento: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(main())