import os
import json
from typing import List, Dict, Any
from crewai.tools import tool
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseExtractorTool:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase = create_client(url, key)

@tool
def extract_supabase_conversations(limit: int = 100) -> str:
    """
    Extrae datos de conversaciones de Supabase con joins a candidatos y meets.
    
    Args:
        limit: Número máximo de conversaciones a extraer
        
    Returns:
        JSON string con los datos de conversaciones
    """
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase = create_client(url, key)
        
        response = supabase.table('conversations').select(
            '''
            id,
            candidate_id,
            meet_id,
            conversation_data,
            candidates(name)
            '''
        ).limit(limit).execute()
        
        conversations = []
        for row in response.data:
            conversation = {
                "conversation_id": row['id'],
                "candidate_id": row['candidate_id'],
                "meet_id": row['meet_id'],
                "conversation_data": row['conversation_data'],
                "candidate_name": row['candidates']['name'] if row['candidates'] else None
            }
            conversations.append(conversation)
        
        return json.dumps(conversations, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error extracting data: {str(e)}"}, indent=2)