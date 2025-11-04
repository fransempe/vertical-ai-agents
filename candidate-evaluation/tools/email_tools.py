import time
import json
import requests
import httpx
from typing import List, Dict, Any, Optional
from crewai.tools import tool
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
import re
import html
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.logger import evaluation_logger

load_dotenv()

class GraphEmailMonitor:
    def __init__(self):
        # Configuración de Microsoft Graph
        self.graph_tenant_id = os.getenv("GRAPH_TENANT_ID", "")
        self.graph_client_id = os.getenv("GRAPH_CLIENT_ID", "")
        self.graph_client_secret = os.getenv("GRAPH_CLIENT_SECRET", "")
        self.graph_scope = os.getenv("GRAPH_SCOPE", "https://graph.microsoft.com/.default")
        self.graph_base = os.getenv("GRAPH_BASE", "https://graph.microsoft.com/v1.0")
        self.outlook_user_id = os.getenv("OUTLOOK_USER_ID", "")
        
        # Patrón flexible para detectar cualquier prefijo que termine en -JD
        self.jd_pattern = r'.*-JD$'
        self.is_monitoring = False
        
        # Inicializar Supabase
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase = create_client(url, key)

        # Patrón para consultas de estado: Status-<uuid>
        self.status_pattern = r'^Status-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$'
    
    # Variable de clase compartida para trackear message_ids procesados (evitar duplicados)
    _processed_message_ids = set()

    def get_graph_access_token(self) -> str:
        """
        Obtiene un token de acceso de Microsoft Graph usando client credentials
        
        Returns:
            Token de acceso de Graph
        """
        try:
            token_url = f"https://login.microsoftonline.com/{self.graph_tenant_id}/oauth2/v2.0/token"
            data = {
                "client_id": self.graph_client_id,
                "client_secret": self.graph_client_secret,
                "grant_type": "client_credentials",
                "scope": self.graph_scope,
            }
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            token = response.json()["access_token"]
            evaluation_logger.log_task_progress("Graph Token", "Token obtenido exitosamente")
            return token
        except Exception as e:
            evaluation_logger.log_error("Graph Token", f"Error obteniendo token: {str(e)}")
            raise

    async def fetch_message_async(self, user_id: str, message_id: str, token: str) -> dict:
        """
        Lee el mensaje completo desde Microsoft Graph (async)
        
        Args:
            user_id: ID del usuario de Outlook
            message_id: ID del mensaje
            token: Token de acceso de Graph
            
        Returns:
            Diccionario con los datos del mensaje
        """
        try:
            # Obtener el mensaje completo con body y todos los campos necesarios
            url = f"{self.graph_base}/users/{user_id}/messages/{message_id}?$select=subject,from,sender,receivedDateTime,body,bodyPreview,isRead,webLink,toRecipients"
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            evaluation_logger.log_error("Fetch Message", f"Error obteniendo mensaje: {str(e)}")
            raise

    def fetch_message(self, user_id: str, message_id: str, token: str = None) -> dict:
        """
        Lee el mensaje completo desde Microsoft Graph (sync)
        
        Args:
            user_id: ID del usuario de Outlook
            message_id: ID del mensaje
            token: Token de acceso de Graph (opcional, se obtiene si no se proporciona)
            
        Returns:
            Diccionario con los datos del mensaje
        """
        try:
            if not token:
                token = self.get_graph_access_token()
            
            # Obtener el mensaje completo con body y todos los campos necesarios
            url = f"{self.graph_base}/users/{user_id}/messages/{message_id}?$select=subject,from,sender,receivedDateTime,body,bodyPreview,isRead,webLink,toRecipients"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            evaluation_logger.log_error("Fetch Message", f"Error obteniendo mensaje: {str(e)}")
            raise

    def extract_text_from_body(self, body_data: dict) -> str:
        """
        Extrae texto plano del body del email (puede ser HTML o texto plano)
        
        Args:
            body_data: Diccionario con 'content' y 'contentType' del body
            
        Returns:
            Texto plano extraído
        """
        try:
            if not body_data:
                return ""
            
            content = body_data.get("content", "")
            content_type = body_data.get("contentType", "text")
            
            if content_type == "html":
                # Convertir HTML a texto plano básico
                # Remover tags HTML
                text = re.sub(r'<[^>]+>', '', content)
                # Decodificar entidades HTML
                text = html.unescape(text)
                # Limpiar espacios múltiples
                text = re.sub(r'\s+', ' ', text)
                return text.strip()
            else:
                # Ya es texto plano
                return content.strip()
        except Exception as e:
            evaluation_logger.log_error("Extract Text", f"Error extrayendo texto: {str(e)}")
            return content if isinstance(content, str) else ""

    def process_graph_message(self, message_data: dict, message_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Procesa un mensaje de Graph y lo convierte al formato esperado
        
        Args:
            message_data: Datos del mensaje obtenidos de Graph
            message_id: ID del mensaje (opcional)
            
        Returns:
            Diccionario con los datos del email en formato estándar, o None si no es válido
        """
        try:
            # Extraer datos del mensaje
            subject = message_data.get("subject", "")
            from_data = message_data.get("from", {})
            sender_email = from_data.get("emailAddress", {}).get("address", "") if from_data else ""
            sender_name = from_data.get("emailAddress", {}).get("name", "") if from_data else ""
            received_date = message_data.get("receivedDateTime", "")
            
            # Extraer contenido del body
            body_data = message_data.get("body", {})
            content = self.extract_text_from_body(body_data)
            
            # Si no hay contenido en body, usar bodyPreview
            if not content or len(content.strip()) < 10:
                content = message_data.get("bodyPreview", "")
            
            # Construir sender string
            if sender_name and sender_email:
                sender = f"{sender_name} <{sender_email}>"
            elif sender_email:
                sender = sender_email
            else:
                sender = "Unknown"
            
            # Clasificar tipo de email
            classification = self.classify_email_type(subject, content)
            ctype = classification.get("type")

            if ctype == "status":
                status_id = classification.get("status_id")
                evaluation_logger.log_task_progress("Status Query Email", f"Consulta de estado detectada: {status_id}")
                return {
                    'subject': subject,
                    'content': content,
                    'sender': sender,
                    'date': received_date,
                    'email_id': message_id or message_data.get("id", ""),
                    'message_id': message_id or message_data.get("id", ""),
                    'sender_email': sender_email,
                    'sender_name': sender_name,
                    'status_query': True,
                    'status_id': status_id
                }

            if ctype != "jd":
                return None
            
            email_data = {
                'subject': subject,
                'content': content,
                'sender': sender,
                'date': received_date,
                'email_id': message_id or message_data.get("id", ""),
                'message_id': message_id or message_data.get("id", ""),
                'sender_email': sender_email,
                'sender_name': sender_name,
                'jd_request': True
            }
            
            return email_data
            
        except Exception as e:
            evaluation_logger.log_error("Process Graph Message", f"Error procesando mensaje: {str(e)}")
            return None

    def get_agents_from_db(self) -> List[Dict[str, Any]]:
        """
        Consulta la tabla agents en Supabase
        
        Returns:
            Lista de agentes con sus datos
        """
        try:
            response = self.supabase.table('agents').select('*').execute()
            return response.data
        except Exception as e:
            evaluation_logger.log_error("Consulta agents", f"Error consultando tabla agents: {str(e)}")
            return []

    def match_email_to_agent(self, subject: str, content: str) -> Optional[Dict[str, Any]]:
        """
        Matchea el subject y contenido del email con un agente de la BD
        
        Args:
            subject: Asunto del email
            content: Contenido del email
            
        Returns:
            Diccionario con el agente que mejor matchea, o None si no hay match
        """
        try:
            agents = self.get_agents_from_db()
            
            if not agents:
                return None
            
            # Extraer tecnología del subject (remover -JD)
            if not subject.endswith('-JD'):
                return None
            
            # Obtener la tecnología del subject
            technology = subject.replace('-JD', '').strip()
            
            if not technology:
                return None
            
            # Buscar agente que tenga el tech_stack correspondiente
            technology_lower = technology.lower()
            
            for agent in agents:
                agent_tech_stack = agent.get('tech_stack', '').lower()
                agent_name = agent.get('name', '').lower()
                
                # Verificar si la tecnología está en el tech_stack del agente
                if technology_lower in agent_tech_stack:
                    evaluation_logger.log_task_complete("Matching Email-Agent", f"Agente encontrado por tech_stack: {agent.get('name')}")
                    return agent
                
                # Verificar si la tecnología está en el nombre del agente
                if technology_lower in agent_name:
                    evaluation_logger.log_task_complete("Matching Email-Agent", f"Agente encontrado por nombre: {agent.get('name')}")
                    return agent
                
                # Verificar si hay coincidencia parcial en tech_stack
                tech_stack_list = agent_tech_stack.split(',') if agent_tech_stack else []
                for tech_item in tech_stack_list:
                    tech_item = tech_item.strip()
                    if technology_lower in tech_item or tech_item in technology_lower:
                        evaluation_logger.log_task_complete("Matching Email-Agent", f"Agente encontrado por coincidencia parcial: {agent.get('name')}")
                        return agent
            
            evaluation_logger.log_task_progress("Matching Email-Agent", f"No se encontró agente para tecnología: {technology}")
            return None
            
        except Exception as e:
            evaluation_logger.log_error("Matching Email-Agent", f"Error haciendo match: {str(e)}")
            return None

    def get_or_create_client(self, email: str, content: str = "", subject: str = "") -> Optional[str]:
        """
        Busca un cliente por email. Si no existe, lo crea.
        
        Args:
            email: Email del cliente (from del email)
            content: Contenido del email para extraer datos adicionales
            subject: Asunto del email para extraer datos adicionales
            
        Returns:
            ID del cliente (existente o creado), o None si falla
        """
        try:
            evaluation_logger.log_task_start("Buscar/Crear Cliente", f"Buscando cliente con email: {email}")
            
            # Buscar cliente por email
            response = self.supabase.table('clients').select('id').eq('email', email).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                client_id = response.data[0].get('id')
                evaluation_logger.log_task_complete("Buscar/Crear Cliente", f"Cliente existente encontrado - ID: {client_id}")
                return client_id
            
            # Cliente no existe, crear uno nuevo
            evaluation_logger.log_task_progress("Buscar/Crear Cliente", "Cliente no encontrado, creando nuevo...")
            
            # Extraer datos del cliente del contenido
            client_name = self.extract_client_name(content, subject) or email.split('@')[0]  # Fallback al dominio si no se encuentra
            client_responsible = self.extract_responsible(content, subject)
            client_phone = self.extract_phone(content, subject)
            
            client_data = {
                "email": email,
                "name": client_name,
                "responsible": client_responsible if client_responsible else None,
                "phone": client_phone if client_phone else None
            }
            
            # Insertar nuevo cliente
            client_response = self.supabase.table('clients').insert(client_data).execute()
            
            if client_response.data and len(client_response.data) > 0:
                new_client_id = client_response.data[0].get('id')
                evaluation_logger.log_task_complete("Buscar/Crear Cliente", f"Cliente creado exitosamente - ID: {new_client_id}")
                return new_client_id
            else:
                evaluation_logger.log_error("Buscar/Crear Cliente", "No se pudo crear el cliente")
                return None
                
        except Exception as e:
            evaluation_logger.log_error("Buscar/Crear Cliente", f"Error: {str(e)}")
            return None
    
    def extract_responsible(self, content: str, subject: str) -> Optional[str]:
        """
        Extrae el responsable del contenido del email.
        
        Args:
            content: Contenido del email
            subject: Asunto del email
            
        Returns:
            Nombre del responsable o None si no se encuentra
        """
        import re
        
        patterns = [
            r'RESPONSABLE:\s*([^\n\r]+)',
            r'Responsable:\s*([^\n\r]+)',
            r'RESPONSABLE\s*:\s*([^\n\r]+)',
            r'Responsable\s*:\s*([^\n\r]+)',
            r'CONTACTO:\s*([^\n\r]+)',
            r'Contacto:\s*([^\n\r]+)',
            r'CONTACTO\s*:\s*([^\n\r]+)',
            r'Contacto\s*:\s*([^\n\r]+)',
        ]
        
        text_to_search = f"{content} {subject}"
        for pattern in patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                responsible = match.group(1).strip()
                # Limpiar
                responsible = re.sub(r'[^\w\s\-\.]', '', responsible)
                if responsible and len(responsible) > 2:
                    return responsible
        
        return None
    
    def extract_phone(self, content: str, subject: str) -> Optional[str]:
        """
        Extrae el teléfono del contenido del email.
        
        Args:
            content: Contenido del email
            subject: Asunto del email
            
        Returns:
            Teléfono o None si no se encuentra
        """
        import re
        
        patterns = [
            r'TEL[EÉ]FONO:\s*([^\n\r]+)',
            r'Tel[ée]fono:\s*([^\n\r]+)',
            r'PHONE:\s*([^\n\r]+)',
            r'Phone:\s*([^\n\r]+)',
            r'TEL:\s*([^\n\r]+)',
            r'Tel:\s*([^\n\r]+)',
        ]
        
        # Patrón general para números de teléfono
        phone_pattern = r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
        
        text_to_search = f"{content} {subject}"
        
        # Buscar con patrones específicos primero
        for pattern in patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                phone = match.group(1).strip()
                # Limpiar y extraer solo números/teléfono válido
                phone_match = re.search(phone_pattern, phone)
                if phone_match:
                    return phone_match.group(0).strip()
        
        # Buscar cualquier teléfono en el texto
        phone_match = re.search(phone_pattern, text_to_search)
        if phone_match:
            return phone_match.group(0).strip()
        
        return None

    def insert_jd_interview(self, interview_name: str, agent_id: str, job_description: str, 
                           email_source: str, content: str = "", subject: str = "") -> Optional[Dict[str, Any]]:
        """
        Inserta un nuevo registro en la tabla jd_interviews
        
        Args:
            interview_name: Nombre de la entrevista
            agent_id: ID del agente asignado
            job_description: Descripción del trabajo o contenido del email
            email_source: Email de origen (from del email)
            content: Contenido completo del email (opcional, para extraer datos del cliente)
            subject: Asunto del email (opcional, para extraer datos del cliente)
            
        Returns:
            Diccionario con el resultado del insert, o None si falla
        """
        try:
            evaluation_logger.log_task_start("Insert JD Interview", "Insertando registro en jd_interviews")
            
            # Extraer email limpio del email_source
            clean_email = self.extract_clean_email(email_source)
            
            # Obtener o crear cliente basado en el email
            client_id = self.get_or_create_client(clean_email, content, subject)
            
            if not client_id:
                evaluation_logger.log_error("Insert JD Interview", "No se pudo obtener o crear el cliente")
                return None
            
            # Crear jd_interview con client_id
            data = {
                "interview_name": interview_name,
                "agent_id": agent_id,
                "job_description": job_description,
                "client_id": client_id
            }
            
            response = self.supabase.table('jd_interviews').insert(data).execute()
            
            if response.data and len(response.data) > 0:
                inserted_record = response.data[0]
                evaluation_logger.log_task_complete(
                    "Insert JD Interview", 
                    f"Registro insertado exitosamente - ID: {inserted_record.get('id', 'N/A')}"
                )
                return inserted_record
            else:
                evaluation_logger.log_error("Insert JD Interview", "No se pudo insertar el registro")
                return None
                
        except Exception as e:
            evaluation_logger.log_error("Insert JD Interview", f"Error insertando registro: {str(e)}")
            return None

    def process_email_from_graph(self, message_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Procesa un email desde Microsoft Graph usando el message_id
        
        Args:
            message_id: ID del mensaje de Graph
            user_id: ID del usuario (opcional, usa OUTLOOK_USER_ID si no se proporciona)
            
        Returns:
            Diccionario con el resultado del procesamiento, o None si falla
        """
        try:
            # Verificar si ya procesamos este message_id (evitar duplicados)
            if message_id in GraphEmailMonitor._processed_message_ids:
                evaluation_logger.log_task_progress("Procesar Email Graph", f"Email ya procesado (duplicado ignorado): {message_id}")
                print(f"⚠️ Email duplicado ignorado: {message_id}")
                return None
            
            if not user_id:
                user_id = self.outlook_user_id
            
            if not user_id:
                evaluation_logger.log_error("Process Email", "No se proporcionó user_id y no hay OUTLOOK_USER_ID configurado")
                return None
            
            # Marcar como procesado ANTES de procesar (evitar race conditions)
            GraphEmailMonitor._processed_message_ids.add(message_id)
            
            # Limpiar cache antiguo si tiene más de 1000 elementos (evitar memory leak)
            if len(GraphEmailMonitor._processed_message_ids) > 1000:
                # Mantener solo los últimos 500
                GraphEmailMonitor._processed_message_ids = set(list(GraphEmailMonitor._processed_message_ids)[-500:])
            
            # Obtener el mensaje desde Graph
            evaluation_logger.log_task_start("Procesar Email Graph", f"Obteniendo mensaje {message_id}")
            message_data = self.fetch_message(user_id, message_id)
            
            # Procesar el mensaje
            email_data = self.process_graph_message(message_data, message_id)
            
            if not email_data:
                evaluation_logger.log_task_progress("Procesar Email Graph", "Email ignorado (ni -JD ni Status-uuid)")
                return None
            
            # Si es consulta de estado, consultar overview y devolver
            if email_data.get('status_query') is True:
                sid = email_data.get('status_id', 'N/A')
                evaluation_logger.log_task_start("Status Query Email", f"Consultando estado para JD Interview: {sid}")
                status_overview = self.get_status_overview(sid)
                email_data['status_overview'] = status_overview
                evaluation_logger.log_task_complete("Status Query Email", f"Estado {'encontrado' if status_overview else 'no encontrado'} - ID: {sid}")
                print(f"🔎 Status Query: {sid} | Found: {bool(status_overview)}")
                if status_overview:
                    # Enviar email al cliente con el overview
                    client_email = None
                    client_data = status_overview.get('client') if isinstance(status_overview, dict) else None
                    if isinstance(client_data, dict):
                        client_email = client_data.get('email')

                    if client_email:
                        self.send_status_overview_email(client_email, sid, status_overview)
                    else:
                        evaluation_logger.log_error("Status Overview Email", "No se encontró email del cliente para enviar status")
            else:
                # Procesar el contenido del email y flujo -JD
                self.process_email_content(email_data)
            
            return email_data
            
        except Exception as e:
            evaluation_logger.log_error("Procesar Email Graph", f"Error procesando email: {str(e)}")
            return None

    def get_status_overview(self, jd_interview_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta interview_evaluations por jd_interview_id y devuelve resumen,
        además de client y jd_interview relacionados.
        """
        try:
            # Buscar evaluación por jd_interview_id
            eval_resp = self.supabase.table('interview_evaluations').select(
                'id,jd_interview_id,client_id,summary,candidates,ranking,candidates_count'
            ).eq('jd_interview_id', jd_interview_id).limit(1).execute()

            if not eval_resp.data:
                return None

            evaluation = eval_resp.data[0]
            client = None
            jd = None

            client_id = evaluation.get('client_id')
            if client_id:
                cli_resp = self.supabase.table('clients').select(
                    'id,email,name,responsible,phone'
                ).eq('id', client_id).limit(1).execute()
                if cli_resp.data:
                    client = cli_resp.data[0]

            jd_id = evaluation.get('jd_interview_id')
            if jd_id:
                jd_resp = self.supabase.table('jd_interviews').select(
                    'id,interview_name,agent_id,client_id,created_at'
                ).eq('id', jd_id).limit(1).execute()
                if jd_resp.data:
                    jd = jd_resp.data[0]

            # Construir respuesta con los campos requeridos
            overview = {
                'summary': evaluation.get('summary'),
                'candidates': evaluation.get('candidates'),
                'ranking': evaluation.get('ranking'),
                'candidates_count': evaluation.get('candidates_count'),
                'client': client,
                'jd_interview': jd
            }
            return overview
        except Exception as e:
            evaluation_logger.log_error("Status Overview", f"Error consultando estado: {str(e)}")
            return None

    def send_status_overview_email(self, to_email: str, jd_interview_id: str, overview: Dict[str, Any]) -> bool:
        """
        Envía por email el objeto de status overview al cliente.
        """
        try:
            evaluation_logger.log_task_start("Status Overview Email", f"Enviando status a {to_email}")

            subject, body = self.format_status_overview_email(jd_interview_id, overview)

            email_api_url = os.getenv("EMAIL_API_URL", "http://127.0.0.1:8004/send-simple-email")
            payload = {
                "to_email": to_email,
                "subject": subject,
                "body": body
            }

            try:
                response = requests.post(
                    email_api_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                response.raise_for_status()
                evaluation_logger.log_task_complete("Status Overview Email", f"Email enviado a {to_email}")
                return True
            except requests.exceptions.RequestException as e:
                evaluation_logger.log_error("Status Overview Email", f"Error enviando email: {str(e)}")
                return False

        except Exception as e:
            evaluation_logger.log_error("Status Overview Email", f"Error preparando envío: {str(e)}")
            return False

    def format_status_overview_email(self, jd_interview_id: str, overview: Dict[str, Any]) -> (str, str):
        """
        Construye un email humano-legible con el resumen de estado, candidatos y ranking.
        """
        try:
            client = overview.get('client') or {}
            jd = overview.get('jd_interview') or {}
            summary = overview.get('summary') or {}
            kpis = (summary or {}).get('kpis') or {}
            candidates = overview.get('candidates') or {}
            ranking = overview.get('ranking') or []
            candidates_count = overview.get('candidates_count')

            client_name = client.get('name', 'N/A')
            client_email = client.get('email', 'N/A')
            client_resp = client.get('responsible', 'N/A')
            client_phone = client.get('phone', 'N/A')
            interview_name = jd.get('interview_name', 'N/A')

            avg_score = kpis.get('avg_score', 'N/A')
            completed_interviews = kpis.get('completed_interviews', 'N/A')
            # Notas removidas del formato final

            # Armar listado de candidatos (a partir de candidates dict)
            candidate_lines = []
            if isinstance(candidates, dict):
                # Ordenar por score desc si posible
                try:
                    sorted_items = sorted(candidates.items(), key=lambda kv: (kv[1] or {}).get('score', 0), reverse=True)
                except Exception:
                    sorted_items = candidates.items()
                for cid, cdata in sorted_items:
                    if not isinstance(cdata, dict):
                        continue
                    cname = cdata.get('name', 'N/A')
                    cscore = cdata.get('score', 'N/A')
                    creco = cdata.get('recommendation', 'N/A')
                    candidate_lines.append(f"• {cname}  🏅 {cscore}  | 🧭 {creco}")

            # Armar ranking
            ranking_lines = []
            if isinstance(ranking, list):
                for i, r in enumerate(ranking, 1):
                    if not isinstance(r, dict):
                        continue
                    rname = r.get('name', 'N/A')
                    rscore = r.get('score', 'N/A')
                    rmatch = r.get('nivel_matcheo', 'N/A')
                    rid = r.get('candidate_id', 'N/A')
                    strengths = r.get('fortalezas_clave') or []
                    strengths_str = ', '.join(strengths) if strengths else 'N/A'
                    analisis = r.get('analisis', 'N/A')
                    medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"#{i}"))
                    ranking_lines.append(
                        f"{medal} {rname}  🏅 {rscore}  | 🔗 {rmatch}\n   💪 {strengths_str}\n   📝 {analisis}"
                    )

            subject = f"📊 Status {jd_interview_id} • {interview_name}"
            header = (
                f"Hola,\n\n"
                f"A continuación te compartimos el estado de la búsqueda:\n\n"
                f"🏢 Cliente: {client_name} ({client_email})\n"
                f"👤 Responsable: {client_resp}   ☎️ {client_phone}\n"
                f"🗂️ Entrevista: {interview_name}   🆔 {jd_interview_id}\n"
                f"👥 Candidatos: {candidates_count if candidates_count is not None else 'N/A'}\n"
            )

            kpis_block = (
                f"\n📈 KPIs:\n"
                f"• ⭐ Score promedio: {avg_score}\n"
                f"• ✅ Entrevistas completadas: {completed_interviews}\n"
            )

            candidates_block = "\n👥 Candidatos:\n" + ("\n".join(candidate_lines) if candidate_lines else "Sin datos de candidatos")

            ranking_block = "\n\n🏆 Ranking:\n" + ("\n\n".join(ranking_lines) if ranking_lines else "Sin ranking disponible")

            footer = "\n\nSaludos,\nSistema de Evaluación de Candidatos\n"

            body = header + kpis_block + "\n" + candidates_block + ranking_block + footer
            return subject, body
        except Exception:
            # Fallback al JSON si hay un error formateando
            return f"📊 Status {jd_interview_id}", json.dumps(overview, indent=2, ensure_ascii=False)

    def process_email_content(self, email_data: Dict[str, Any]) -> None:
        """
        Procesa el contenido del email y lo muestra en consola

        Args:
            email_data: Diccionario con los datos del email
        """
        try:
            subject = email_data.get('subject', '')
            content = email_data.get('content', '')
            sender = email_data.get('sender', '')
            received_date = email_data.get('date', '')

            print("=" * 80)
            print("📧 NUEVO EMAIL DETECTADO")
            print("=" * 80)
            print(f"📤 De: {sender}")
            print(f"📅 Fecha: {received_date}")
            print(f"📋 Asunto: {subject}")
            print("-" * 80)
            print("📄 CONTENIDO:")
            print(content)
            print("=" * 80)
            
            # Matchear con agente
            matched_agent = self.match_email_to_agent(subject, content)
            
            print("\n🤖 RESULTADO DEL MATCHING CON AGENTE:")
            print("=" * 80)
            if matched_agent:
                print(f"✅ AGENTE ENCONTRADO:")
                print(f"   - Agent ID: {matched_agent.get('agent_id', 'N/A')}")
                print(f"   - Name: {matched_agent.get('name', 'N/A')}")
                print(f"   - Tech Stack: {matched_agent.get('tech_stack', 'N/A')}")
                print(f"   - Description: {matched_agent.get('description', 'N/A')}")
                print(f"   - Status: {matched_agent.get('status', 'N/A')}")
                
                # Insertar en la tabla jd_interviews
                interview_name = self.generate_interview_name(subject, content, sender)
                agent_id = matched_agent.get('agent_id')
                
                inserted_record = self.insert_jd_interview(
                    interview_name=interview_name,
                    agent_id=agent_id,
                    job_description=content,
                    email_source=sender,
                    content=content,
                    subject=subject
                )
                
                print("\n💾 RESULTADO DEL INSERT EN jd_interviews:")
                print("=" * 80)
                if inserted_record:
                    print(f"✅ REGISTRO INSERTADO EXITOSAMENTE:")
                    print(f"   - ID: {inserted_record.get('id', 'N/A')}")
                    print(f"   - Interview Name: {inserted_record.get('interview_name', 'N/A')}")
                    print(f"   - Agent ID: {inserted_record.get('agent_id', 'N/A')}")
                    print(f"   - Job Description: {inserted_record.get('job_description', 'N/A')[:100]}...")
                    print(f"   - Client ID: {inserted_record.get('client_id', 'N/A')}")
                    print(f"   - Created At: {inserted_record.get('created_at', 'N/A')}")
                    
                    # Enviar email de confirmación al emisor
                    print("\n📧 ENVIANDO EMAIL DE CONFIRMACIÓN:")
                    print("=" * 80)
                    clean_email = self.extract_clean_email(sender)
                    email_sent = self.send_confirmation_email(
                        to_email=clean_email,
                        interview_name=interview_name,
                        agent_name=matched_agent.get('name', 'N/A'),
                        agent_id=agent_id,
                        interview_id=inserted_record.get('id', 'N/A'),
                        success=True
                    )
                    
                    if email_sent:
                        print(f"✅ EMAIL DE CONFIRMACIÓN ENVIADO EXITOSAMENTE a {clean_email}")
                    else:
                        print(f"❌ ERROR ENVIANDO EMAIL DE CONFIRMACIÓN a {clean_email}")
                    print("=" * 80)
                    
                else:
                    print("❌ ERROR AL INSERTAR REGISTRO")
                    
                    # Enviar email de error al emisor
                    print("\n📧 ENVIANDO EMAIL DE ERROR:")
                    print("=" * 80)
                    clean_email = self.extract_clean_email(sender)
                    email_sent = self.send_confirmation_email(
                        to_email=clean_email,
                        interview_name=interview_name,
                        agent_name=matched_agent.get('name', 'N/A'),
                        agent_id=agent_id,
                        interview_id='N/A',
                        success=False
                    )
                    
                    if email_sent:
                        print(f"✅ EMAIL DE ERROR ENVIADO a {clean_email}")
                    else:
                        print(f"❌ ERROR ENVIANDO EMAIL DE ERROR a {clean_email}")
                    print("=" * 80)
                    
                print("=" * 80 + "\n")
                
            else:
                print("❌ NO SE ENCONTRÓ AGENTE MATCHING")
                
                # Enviar email de error cuando no se encuentra agente
                print("\n📧 ENVIANDO EMAIL DE ERROR (NO SE ENCONTRÓ AGENTE):")
                print("=" * 80)
                clean_email = self.extract_clean_email(sender)
                interview_name = self.generate_interview_name(subject, content, sender)
                
                email_sent = self.send_confirmation_email(
                    to_email=clean_email,
                    interview_name=interview_name,
                    agent_name='N/A',
                    agent_id='N/A',
                    interview_id='N/A',
                    success=False
                )
                
                if email_sent:
                    print(f"✅ EMAIL DE ERROR ENVIADO a {clean_email}")
                else:
                    print(f"❌ ERROR ENVIANDO EMAIL DE ERROR a {clean_email}")
                print("=" * 80)
                
            print("=" * 80 + "\n")

            evaluation_logger.log_task_complete("Procesamiento Email", f"Email procesado: {subject}")

        except Exception as e:
            evaluation_logger.log_error("Procesamiento Email", f"Error procesando email: {str(e)}")

    def start_monitoring(self) -> None:
        """
        NOTA: El monitoreo ahora se hace a través de webhooks de Microsoft Graph.
        Esta función se mantiene por compatibilidad pero no hace nada activo.
        El procesamiento de emails se debe hacer a través de process_email_from_graph()
        llamado desde el webhook endpoint.
        """
        evaluation_logger.log_task_progress("Monitoreo Email", "El monitoreo ahora se realiza a través de webhooks de Microsoft Graph")
        print("🔍 NOTA: El monitoreo de emails ahora se realiza a través de webhooks de Microsoft Graph")
        print("📧 Los emails se procesan automáticamente cuando llegan al webhook endpoint")
        print(f"🎯 Patrón de detección: {self.jd_pattern}")
        print("⚠️  Este método ya no realiza polling activo")

    def is_job_search_email(self, subject: str, content: str) -> bool:
        """
        Detecta si un email es una búsqueda de trabajo basado en el prefijo -JD.
        
        Args:
            subject: Asunto del email
            content: Contenido del email
            
        Returns:
            True si el subject termina en -JD, False en caso contrario
        """
        import re
        
        # Verificar si el subject termina en -JD
        return bool(re.search(self.jd_pattern, subject, re.IGNORECASE))

    def is_status_query_email(self, subject: str) -> Optional[str]:
        """
        Detecta si el email es una consulta de estado con subject "Status-<uuid>".

        Returns:
            El UUID como string si matchea, de lo contrario None.
        """
        import re
        m = re.match(self.status_pattern, subject.strip()) if subject else None
        return m.group(1) if m else None

    def classify_email_type(self, subject: str, content: str) -> Dict[str, Any]:
        """
        Clasifica el email en tipos: 'status' (Status-uuid), 'jd' (-JD) o 'other'.
        """
        status_id = self.is_status_query_email(subject)
        if status_id:
            return {"type": "status", "status_id": status_id}
        if self.is_job_search_email(subject, content):
            return {"type": "jd"}
        return {"type": "other"}

    def generate_interview_name(self, subject: str, content: str, sender: str) -> str:
        """
        Genera un nombre descriptivo para la entrevista basado en el cliente, tecnología y búsqueda.
        
        Args:
            subject: Asunto del email
            content: Contenido del email
            sender: Remitente del email
            
        Returns:
            Nombre descriptivo de la entrevista
        """
        try:
            # Extraer nombre del cliente del contenido del email
            client_name = self.extract_client_name(content, subject)
            
            # Extraer tecnología principal del contenido
            technology = self.extract_technology(content, subject)
            
            # Extraer tipo de búsqueda/posición
            position_type = self.extract_position_type(content, subject)
            
            # Generar nombre descriptivo con formato: CLIENTE - Búsqueda TIPO TECNOLOGÍA
            if client_name and technology:
                interview_name = f"{client_name} - Búsqueda {position_type} {technology}"
            elif client_name:
                interview_name = f"{client_name} - Búsqueda {position_type}"
            elif technology:
                interview_name = f"Búsqueda {position_type} {technology}"
            else:
                # Fallback al subject original
                interview_name = f"Interview - {subject}"
            
            evaluation_logger.log_task_complete("Generar Nombre de Entrevista", f"Nombre generado: {interview_name}")
            return interview_name
            
        except Exception as e:
            evaluation_logger.log_error("Generar Nombre de Entrevista", f"Error generando nombre: {str(e)}")
            return f"Interview - {subject}"
    
    def extract_client_name(self, content: str, subject: str) -> str:
        """
        Extrae el nombre del cliente del contenido del email.
        
        Args:
            content: Contenido del email
            subject: Asunto del email
            
        Returns:
            Nombre del cliente o None si no se encuentra
        """
        import re
        
        # Patrones para buscar el nombre del cliente
        patterns = [
            r'CLIENTE:\s*([^\n\r]+)',
            r'Cliente:\s*([^\n\r]+)',
            r'CLIENTE\s*:\s*([^\n\r]+)',
            r'Cliente\s*:\s*([^\n\r]+)',
            r'CLIENTE\s*-\s*([^\n\r]+)',
            r'Cliente\s*-\s*([^\n\r]+)',
            r'CLIENTE\s*=\s*([^\n\r]+)',
            r'Cliente\s*=\s*([^\n\r]+)',
            r'CLIENTE\s*([^\n\r]+)',
            r'Cliente\s*([^\n\r]+)',
        ]
        
        # Buscar en el contenido
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                client_name = match.group(1).strip()
                # Limpiar el nombre del cliente
                client_name = re.sub(r'[^\w\s\-&]', '', client_name)
                if client_name and len(client_name) > 2:
                    return client_name
        
        # Buscar en el subject si no se encuentra en el contenido
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                client_name = match.group(1).strip()
                client_name = re.sub(r'[^\w\s\-&]', '', client_name)
                if client_name and len(client_name) > 2:
                    return client_name
        
        return None
    
    def extract_technology(self, content: str, subject: str) -> str:
        """
        Extrae la tecnología principal del contenido del email.
        
        Args:
            content: Contenido del email
            subject: Asunto del email
            
        Returns:
            Tecnología principal o None si no se encuentra
        """
        import re
        
        # Tecnologías comunes a buscar
        technologies = [
            'React', 'ReactJS', 'React.js', 'Angular', 'Vue', 'Vue.js',
            'Node.js', 'NodeJS', 'Python', 'Java', 'C#', 'C++',
            'JavaScript', 'TypeScript', 'PHP', 'Ruby', 'Go', 'Rust',
            'Django', 'Flask', 'Express', 'Spring', 'Laravel',
            'MongoDB', 'PostgreSQL', 'MySQL', 'Redis', 'Elasticsearch',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes',
            'Machine Learning', 'AI', 'Data Science', 'DevOps'
        ]
        
        # Buscar tecnologías en el contenido
        text_to_search = f"{content} {subject}".lower()
        
        for tech in technologies:
            if tech.lower() in text_to_search:
                return tech
        
        return None
    
    def extract_position_type(self, content: str, subject: str) -> str:
        """
        Extrae el tipo de posición/búsqueda del contenido del email.
        
        Args:
            content: Contenido del email
            subject: Asunto del email
            
        Returns:
            Tipo de posición o "Desarrollador" por defecto
        """
        import re
        
        # Patrones para tipos de posición
        patterns = [
            (r'desarrollador', 'Desarrollador'),
            (r'developer', 'Developer'),
            (r'programador', 'Programador'),
            (r'programmer', 'Programmer'),
            (r'ingeniero', 'Ingeniero'),
            (r'engineer', 'Engineer'),
            (r'arquitecto', 'Arquitecto'),
            (r'architect', 'Architect'),
            (r'analista', 'Analista'),
            (r'analyst', 'Analyst'),
            (r'consultor', 'Consultor'),
            (r'consultant', 'Consultant'),
            (r'tech lead', 'Tech Lead'),
            (r'líder técnico', 'Líder Técnico'),
            (r'senior', 'Senior'),
            (r'junior', 'Junior'),
            (r'full stack', 'Full Stack'),
            (r'frontend', 'Frontend'),
            (r'backend', 'Backend'),
            (r'mobile', 'Mobile'),
            (r'data scientist', 'Data Scientist'),
            (r'devops', 'DevOps')
        ]
        
        text_to_search = f"{content} {subject}".lower()
        
        for pattern, position_type in patterns:
            if re.search(pattern, text_to_search):
                return position_type
        
        return "Desarrollador"
    
    def extract_clean_email(self, email_source: str) -> str:
        """
        Extrae el email limpio de una cadena codificada o nombre con email.
        Esta función funciona con CUALQUIER email, no solo con fran.sempe@gmail.com.
        
        Args:
            email_source: Cadena codificada o email simple.
            Ejemplos:
                - "=?UTF-8?Q?Name?= <email@domain.com>" → "email@domain.com"
                - "=?UTF-8?B?Name?= <otro@email.com>" → "otro@email.com"
                - "simple@email.com" → "simple@email.com"
            
        Returns:
            Email limpio extraído de la cadena (cualquier email válido)
        """
        import re
        
        try:
            # Si ya es un email simple, devolverlo
            if '@' in email_source and not email_source.startswith('=?'):
                return email_source.strip()
            
            # Buscar email entre < >
            email_match = re.search(r'<([^>]+@[^>]+)>', email_source)
            if email_match:
                return email_match.group(1).strip()
            
            # Buscar email al final de la cadena
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', email_source)
            if email_match:
                return email_match.group(1).strip()
            
            # Si no se encuentra, devolver la cadena original
            return email_source.strip()
            
        except Exception as e:
            evaluation_logger.log_error("Extraer Email Limpio", f"Error extrayendo email: {str(e)}")
            return email_source.strip()
    
    def send_confirmation_email(self, to_email: str, interview_name: str, agent_name: str, 
                              agent_id: str, interview_id: str, success: bool = True) -> bool:
        """
        Envía un email de confirmación al emisor notificando la creación de la entrevista.
        
        Args:
            to_email: Email del emisor
            interview_name: Nombre de la entrevista creada
            agent_name: Nombre del agente asignado
            agent_id: ID del agente
            interview_id: ID de la entrevista creada
            success: Si la creación fue exitosa
            
        Returns:
            True si el email se envió correctamente, False en caso contrario
        """
        try:
            evaluation_logger.log_task_start("Envío Email Confirmación", f"Enviando confirmación a {to_email}")
            
            # Configurar asunto según el resultado
            if success:
                subject = f"✅ Entrevista Creada: {interview_name}"
            else:
                subject = f"❌ Error Creando Entrevista: {interview_name}"
            
            # Crear cuerpo del email
            if success:
                body = f"""
Hola,

Te confirmamos que hemos recibido y procesado tu solicitud de entrevista.

📋 **DETALLES DE LA ENTREVISTA CREADA:**
• Nombre: {interview_name}
• ID de Entrevista: {interview_id}
• Agente Asignado: {agent_name}
• ID del Agente: {agent_id}
• Estado: ✅ Creada exitosamente

🤖 **INFORMACIÓN DEL AGENTE:**
El agente {agent_name} ha sido asignado automáticamente para manejar esta entrevista basado en los requisitos técnicos especificados.

📧 **PRÓXIMOS PASOS:**
El agente comenzará a procesar las candidaturas y evaluaciones según los criterios establecidos.

Si tienes alguna pregunta o necesitas modificar algo, no dudes en contactarnos.

Saludos,
Sistema de Evaluación de Candidatos
                """
            else:
                body = f"""
Hola,

Lamentamos informarte que hubo un problema al procesar tu solicitud de entrevista.

📋 **DETALLES DE LA SOLICITUD:**
• Nombre: {interview_name}
• Estado: ❌ Error en la creación

🔧 **ACCIONES RECOMENDADAS:**
• Verifica que el formato del email sea correcto
• Asegúrate de incluir la información del cliente
• Intenta enviar nuevamente el email

Si el problema persiste, por favor contacta al equipo técnico.

Saludos,
Sistema de Evaluación de Candidatos
                """
            
            # Enviar email usando la API de email directamente
            email_api_url = os.getenv("EMAIL_API_URL", "http://127.0.0.1:8004/send-simple-email")
            
            payload = {
                "to_email": to_email,  # Enviar al email del emisor original
                "subject": subject,
                "body": body
            }
            
            evaluation_logger.log_task_progress("Envío Email Confirmación", f"Enviando a {to_email} via {email_api_url}")
            
            try:
                response = requests.post(
                    email_api_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                response.raise_for_status()
                
                evaluation_logger.log_task_complete("Envío Email Confirmación", f"Email enviado exitosamente a {to_email}")
                return True
                
            except requests.exceptions.RequestException as e:
                evaluation_logger.log_error("Envío Email Confirmación", f"Error enviando email: {str(e)}")
                return False
                
        except Exception as e:
            evaluation_logger.log_error("Envío Email Confirmación", f"Error enviando confirmación: {str(e)}")
            return False

@tool
def start_email_monitoring() -> str:
    """
    NOTA: El monitoreo ahora se realiza a través de webhooks de Microsoft Graph.
    Esta función retorna información sobre el estado del sistema.

    Returns:
        JSON string con el estado del monitoreo
    """
    try:
        evaluation_logger.log_task_start("Inicio Monitoreo", "Email Monitor Agent")

        monitor = GraphEmailMonitor()

        evaluation_logger.log_task_complete("Inicio Monitoreo", "Sistema de monitoreo configurado (webhooks)")

        return json.dumps({
            "status": "success",
            "message": "El monitoreo se realiza a través de webhooks de Microsoft Graph",
            "user_id": monitor.outlook_user_id,
            "jd_pattern": monitor.jd_pattern,
            "note": "Los emails se procesan automáticamente cuando llegan al webhook endpoint"
        }, indent=2)

    except Exception as e:
        evaluation_logger.log_error("Inicio Monitoreo", f"Error: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error: {str(e)}"
        }, indent=2)

@tool
def process_email_from_graph(message_id: str, user_id: str = None) -> str:
    """
    Procesa un email desde Microsoft Graph usando el message_id.
    Esta función debe ser llamada desde el webhook endpoint cuando llega una notificación.

    Args:
        message_id: ID del mensaje de Microsoft Graph
        user_id: ID del usuario de Outlook (opcional, usa OUTLOOK_USER_ID si no se proporciona)

    Returns:
        JSON string con el resultado del procesamiento
    """
    try:
        evaluation_logger.log_task_start("Procesar Email Graph", f"Procesando mensaje {message_id}")

        monitor = GraphEmailMonitor()
        result = monitor.process_email_from_graph(message_id, user_id)

        if result:
            evaluation_logger.log_task_complete("Procesar Email Graph", f"Email procesado exitosamente: {message_id}")
            return json.dumps({
                "status": "success",
                "message": "Email procesado exitosamente",
                "email_data": {
                    "subject": result.get("subject", ""),
                    "sender": result.get("sender", ""),
                    "message_id": message_id
                }
            }, indent=2)
        else:
            evaluation_logger.log_task_progress("Procesar Email Graph", f"Email no procesado (no es -JD): {message_id}")
            return json.dumps({
                "status": "ignored",
                "message": "El email no es una búsqueda de trabajo (-JD) o no se pudo procesar",
                "message_id": message_id
            }, indent=2)

    except Exception as e:
        evaluation_logger.log_error("Procesar Email Graph", f"Error procesando email: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error procesando email: {str(e)}",
            "message_id": message_id
        }, indent=2)

@tool
def simulate_incoming_email(subject: str, content: str, sender: str = "test@example.com") -> str:
    """
    Simula la recepción de un email para testing

    Args:
        subject: Asunto del email
        content: Contenido del email
        sender: Remitente del email

    Returns:
        JSON string con el resultado de la simulación
    """
    try:
        evaluation_logger.log_task_start("Simulación Email", "Email Simulator")

        monitor = GraphEmailMonitor()

        # Verificar si es una búsqueda de trabajo
        if monitor.is_job_search_email(subject, content):
            email_data = {
                'subject': subject,
                'content': content,
                'sender': sender,
                'date': time.strftime("%Y-%m-%d %H:%M:%S")
            }

            monitor.process_email_content(email_data)

            evaluation_logger.log_task_complete("Simulación Email", f"Email simulado procesado: {subject}")

            return json.dumps({
                "status": "success",
                "message": "Email simulado procesado exitosamente",
                "email_data": email_data
            }, indent=2)
        else:
            evaluation_logger.log_task_progress("Simulación Email", f"Email ignorado - subject no coincide: {subject}")

            return json.dumps({
                "status": "ignored",
                "message": f"Email ignorado - no se detectó como búsqueda de trabajo",
                "jd_pattern": monitor.jd_pattern
            }, indent=2)

    except Exception as e:
        evaluation_logger.log_error("Simulación Email", f"Error simulando email: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error simulando email: {str(e)}"
        }, indent=2)