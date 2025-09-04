import logging
import os
from datetime import datetime
from typing import Optional

class EvaluationLogger:
    """Sistema de logging personalizado para el proceso de evaluación de candidatos"""
    
    def __init__(self, log_name: str = "candidate_evaluation"):
        self.log_name = log_name
        self.logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Crear logger principal
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(logging.INFO)
        
        # Evitar duplicar handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Configura los handlers para archivo y consola"""
        # Handler para archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self.logs_dir, f"{self.log_name}_{timestamp}.log")
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formato detallado
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_task_start(self, task_name: str, agent_name: str):
        """Registra el inicio de una tarea"""
        self.logger.info(f"🚀 INICIANDO TAREA: {task_name} | Agente: {agent_name}")
    
    def log_task_progress(self, task_name: str, message: str):
        """Registra progreso de una tarea"""
        self.logger.info(f"⏳ {task_name}: {message}")
    
    def log_task_complete(self, task_name: str, result_summary: str):
        """Registra la finalización de una tarea"""
        self.logger.info(f"✅ COMPLETADA: {task_name} | Resumen: {result_summary}")
    
    def log_conversation_analysis(self, conversation_id: str, candidate_name: str, analysis_results: dict):
        """Registra análisis detallado de conversación"""
        self.logger.info(f"📊 ANÁLISIS CONVERSACIÓN | ID: {conversation_id} | Candidato: {candidate_name}")
        self.logger.info(f"   • Puntaje General: {analysis_results.get('overall_score', 'N/A')}/10")
        self.logger.info(f"   • Habilidades Blandas: {analysis_results.get('soft_skills_score', 'N/A')}/10")
        self.logger.info(f"   • Comunicación: {analysis_results.get('communication_score', 'N/A')}/10")
        self.logger.info(f"   • Aspectos Técnicos: {analysis_results.get('technical_score', 'N/A')}/10")
    
    def log_email_sent(self, recipient: str, subject: str, status: str):
        """Registra envío de email"""
        status_emoji = "✅" if status == "success" else "❌"
        self.logger.info(f"{status_emoji} EMAIL: {recipient} | Asunto: {subject} | Estado: {status}")
    
    def log_error(self, task_name: str, error_message: str):
        """Registra errores"""
        self.logger.error(f"❌ ERROR en {task_name}: {error_message}")
    
    def log_statistics(self, stats: dict):
        """Registra estadísticas finales"""
        self.logger.info("📈 ESTADÍSTICAS FINALES:")
        for key, value in stats.items():
            self.logger.info(f"   • {key}: {value}")

# Instancia global del logger
evaluation_logger = EvaluationLogger()