import imaplib
import email
import time
import json
from email.header import decode_header
from typing import List, Dict, Any, Optional
from crewai.tools import tool
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.logger import evaluation_logger

load_dotenv()

class EmailMonitor:
    def __init__(self):
        self.email_address = os.getenv("EMAIL_ADDRESS", "ai.vertical.agents.sender@gmail.com")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.target_subjects = ["ReactJS-JD", "NodeJS-JD", "Angular-JD", "AIEngineering-JD", "Java-JD"]
        self.is_monitoring = False
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        
        # Inicializar Supabase
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase = create_client(url, key)

    def connect_to_email(self):
        """
        Conecta al servidor IMAP de Gmail
        """
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            return mail
        except Exception as e:
            evaluation_logger.log_error("Conexión Email", f"Error conectando: {str(e)}")
            raise

    def check_for_new_emails(self) -> List[Dict[str, Any]]:
        """
        Verifica nuevos emails con los subjects específicos

        Returns:
            Lista de emails nuevos que coinciden con los subjects objetivo
        """
        try:
            evaluation_logger.log_task_progress("Monitoreo Email", f"Verificando emails en: {self.email_address}")

            mail = self.connect_to_email()
            mail.select('inbox')

            # Buscar emails no leídos
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()

            new_emails = []

            for email_id in email_ids:
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Decodificar subject
                        subject = decode_header(msg["Subject"])[0][0]
                        if isinstance(subject, bytes):
                            subject = subject.decode()

                        # Verificar si el subject contiene alguno de los prefijos objetivo
                        if any(target in subject for target in self.target_subjects):
                            # Obtener contenido del email
                            content = self.get_email_content(msg)

                            email_data = {
                                'subject': subject,
                                'content': content,
                                'sender': msg.get("From"),
                                'date': msg.get("Date"),
                                'email_id': email_id.decode()
                            }
                            new_emails.append(email_data)

            mail.logout()
            evaluation_logger.log_task_complete("Monitoreo Email", f"Verificación completada - {len(new_emails)} emails encontrados")
            return new_emails

        except Exception as e:
            evaluation_logger.log_error("Monitoreo Email", f"Error verificando emails: {str(e)}")
            return []

    def get_email_content(self, msg) -> str:
        """
        Extrae el contenido de texto del email
        """
        content = ""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            content += payload.decode('utf-8', errors='ignore')
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    content = payload.decode('utf-8', errors='ignore')
        except Exception as e:
            evaluation_logger.log_error("Extracción Contenido", f"Error extrayendo contenido: {str(e)}")
            content = "Error extrayendo contenido del email"

        return content

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
            
            # Mapeo de subjects a tech_stack
            subject_to_tech = {
                "ReactJS-JD": ["ReactJS", "React"],
                "NodeJS-JD": ["NodeJS", "Node.js", "Node"],
                "Angular-JD": ["Angular"],
                "AIEngineering-JD": ["AI", "Artificial Intelligence", "Machine Learning", "ML"],
                "Java-JD": ["Java"]
            }
            
            # Buscar el tech stack en el subject
            matched_tech = None
            for subject_key, tech_keywords in subject_to_tech.items():
                if subject_key in subject:
                    matched_tech = tech_keywords
                    break
            
            if not matched_tech:
                return None
            
            # Buscar agente que tenga el tech_stack correspondiente
            for agent in agents:
                agent_tech_stack = agent.get('tech_stack', '').lower()
                agent_name = agent.get('name', '').lower()
                
                # Verificar si alguno de los keywords está en el tech_stack o nombre del agente
                for tech_keyword in matched_tech:
                    if tech_keyword.lower() in agent_tech_stack or tech_keyword.lower() in agent_name:
                        return agent
            
            return None
            
        except Exception as e:
            evaluation_logger.log_error("Matching Email-Agent", f"Error haciendo match: {str(e)}")
            return None

    def insert_jd_interview(self, interview_name: str, agent_id: str, job_description: str, 
                           email_source: str) -> Optional[Dict[str, Any]]:
        """
        Inserta un nuevo registro en la tabla jd_interviews
        
        Args:
            interview_name: Nombre de la entrevista
            agent_id: ID del agente asignado
            job_description: Descripción del trabajo o contenido del email
            email_source: Email de origen
            
        Returns:
            Diccionario con el resultado del insert, o None si falla
        """
        try:
            evaluation_logger.log_task_start("Insert JD Interview", "Insertando registro en jd_interviews")
            
            data = {
                "interview_name": interview_name,
                "agent_id": agent_id,
                "job_description": job_description,
                "email_source": email_source
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
                interview_name = f"Interview - {subject}"
                agent_id = matched_agent.get('agent_id')
                
                inserted_record = self.insert_jd_interview(
                    interview_name=interview_name,
                    agent_id=agent_id,
                    job_description=content,
                    email_source=sender
                )
                
                print("\n💾 RESULTADO DEL INSERT EN jd_interviews:")
                print("=" * 80)
                if inserted_record:
                    print(f"✅ REGISTRO INSERTADO EXITOSAMENTE:")
                    print(f"   - ID: {inserted_record.get('id', 'N/A')}")
                    print(f"   - Interview Name: {inserted_record.get('interview_name', 'N/A')}")
                    print(f"   - Agent ID: {inserted_record.get('agent_id', 'N/A')}")
                    print(f"   - Job Description: {inserted_record.get('job_description', 'N/A')[:100]}...")
                    print(f"   - Email Source: {inserted_record.get('email_source', 'N/A')}")
                    print(f"   - Created At: {inserted_record.get('created_at', 'N/A')}")
                else:
                    print("❌ ERROR AL INSERTAR REGISTRO")
                print("=" * 80 + "\n")
                
            else:
                print("❌ NO SE ENCONTRÓ AGENTE MATCHING")
            print("=" * 80 + "\n")

            evaluation_logger.log_task_complete("Procesamiento Email", f"Email procesado: {subject}")

        except Exception as e:
            evaluation_logger.log_error("Procesamiento Email", f"Error procesando email: {str(e)}")

    def start_monitoring(self) -> None:
        """
        Inicia el monitoreo continuo de la bandeja de entrada
        """
        print("🔍 Iniciando monitoreo de bandeja de entrada...")
        print(f"📧 Email: {self.email_address}")
        print(f"🎯 Subjects objetivo: {', '.join(self.target_subjects)}")
        print("⏰ Presiona Ctrl+C para detener el monitoreo")
        print("-" * 80)

        self.is_monitoring = True

        try:
            while self.is_monitoring:
                new_emails = self.check_for_new_emails()

                for email_data in new_emails:
                    subject = email_data.get('subject', '')

                    # Verificar si el subject contiene alguno de los prefijos objetivo
                    if any(target in subject for target in self.target_subjects):
                        self.process_email_content(email_data)

                # Esperar antes de la siguiente verificación
                time.sleep(30)  # Verificar cada 30 segundos

        except KeyboardInterrupt:
            print("\n⏹️ Monitoreo detenido por el usuario")
            self.is_monitoring = False
        except Exception as e:
            evaluation_logger.log_error("Monitoreo Email", f"Error en el monitoreo: {str(e)}")
            print(f"\n❌ Error en el monitoreo: {str(e)}")
            self.is_monitoring = False

@tool
def start_email_monitoring() -> str:
    """
    Inicia el monitoreo de emails para detectar job descriptions

    Returns:
        JSON string con el estado del monitoreo
    """
    try:
        evaluation_logger.log_task_start("Inicio Monitoreo", "Email Monitor Agent")

        monitor = EmailMonitor()
        monitor.start_monitoring()

        evaluation_logger.log_task_complete("Inicio Monitoreo", "Monitoreo iniciado exitosamente")

        return json.dumps({
            "status": "success",
            "message": "Monitoreo de emails iniciado",
            "email": monitor.email_address,
            "target_subjects": monitor.target_subjects
        }, indent=2)

    except Exception as e:
        evaluation_logger.log_error("Inicio Monitoreo", f"Error iniciando monitoreo: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error iniciando monitoreo: {str(e)}"
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

        monitor = EmailMonitor()

        # Verificar si el subject contiene alguno de los prefijos objetivo
        if any(target in subject for target in monitor.target_subjects):
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
                "message": f"Email ignorado - subject '{subject}' no contiene ningún prefijo objetivo",
                "target_subjects": monitor.target_subjects
            }, indent=2)

    except Exception as e:
        evaluation_logger.log_error("Simulación Email", f"Error simulando email: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Error simulando email: {str(e)}"
        }, indent=2)