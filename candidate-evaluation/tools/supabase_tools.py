import os
import json
from typing import List, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseExtractorTool:
    """Tool simple para extraer datos de Supabase sin dependencias de crewai_tools"""
    
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)
        self.name = "Supabase Data Extractor"
        self.description = "Extrae datos de conversaciones de Supabase con joins a candidatos y meets"
    
    def extract_data(self, limit: int = 100) -> List[Dict]:
        """Extrae conversaciones con información relacionada"""
        try:
            response = self.supabase.table('conversations').select(
                '''
                id,
                candidate_id,
                meet_id,
                conversation_data,
                candidates(name),
                meet(title)
                '''
            ).limit(limit).execute()
            
            conversations = []
            for row in response.data:
                conversation = {
                    "conversation_id": row['id'],
                    "candidate_id": row['candidate_id'],
                    "meet_id": row['meet_id'],
                    "conversation_data": row['conversation_data'],
                    "candidate_name": row['candidates']['name'] if row['candidates'] else None,
                    "meet_title": row['meet']['title'] if row['meet'] else None
                }
                conversations.append(conversation)
            
            return conversations
            
        except Exception as e:
            print(f"Error extracting data: {str(e)}")
            return []
    
    def _run(self, limit: int = 100) -> str:
        """Método requerido por CrewAI - devuelve JSON string"""
        data = self.extract_data(limit)
        return json.dumps(data, indent=2)