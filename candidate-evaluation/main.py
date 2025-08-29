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
        filename = f"crew_results_{timestamp}.json"
        
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

# test_crew.py - Script para probar el crew con datos de prueba
import os
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

def test_connections():
    """Prueba las conexiones antes de ejecutar el crew"""
    load_dotenv()
    
    print("🔍 Probando conexiones...")
    
    # Test Supabase
    print("\n📊 Supabase:")
    try:
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        response = supabase.table('conversations').select('id').limit(1).execute()
        print(f"✅ Conectado - {len(response.data)} registros encontrados")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test OpenAI
    print("\n🤖 OpenAI:")
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=10
        )
        print("✅ Conectado correctamente")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    print("\n🎉 Todas las conexiones están funcionando!")
    return True

if __name__ == "__main__":
    if test_connections():
        print("\n🚀 Puedes ejecutar 'python main.py' para iniciar el crew")
    else:
        print("\n⚠️  Revisa tu configuración en el archivo .env")