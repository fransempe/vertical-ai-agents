#!/usr/bin/env python3
"""
Script principal para el agente de monitoreo de emails
Escucha emails con subjects específicos: ReactJS-JD, NodeJS-JD, Angular-JD, AIEngineering-JD, Java-JD
"""

import os
import sys
from datetime import datetime
from tools.email_tools import EmailMonitor, simulate_incoming_email
from utils.logger import evaluation_logger

def main():
    """Función principal que ejecuta el monitoreo de emails"""
    try:
        print("="*80)
        print("📧 AGENTE DE MONITOREO DE EMAILS - JOB DESCRIPTIONS")
        print("="*80)

        # Inicializar logging
        start_time = datetime.now()
        evaluation_logger.logger.info("="*80)
        evaluation_logger.logger.info("📧 INICIANDO AGENTE DE MONITOREO DE EMAILS")
        evaluation_logger.logger.info(f"⏰ Fecha y hora de inicio: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        evaluation_logger.logger.info("="*80)

        # Crear instancia del monitor
        monitor = EmailMonitor()

        print(f"📧 Monitoring email: {monitor.email_address}")
        print(f"🎯 Target subjects: {', '.join(monitor.target_subjects)}")
        print("\n🔄 Para testing, puedes usar la función simulate_incoming_email")
        print("⏰ El agente estará escuchando continuamente...")
        print("🛑 Presiona Ctrl+C para detener\n")

        # Iniciar monitoreo
        monitor.start_monitoring()

    except KeyboardInterrupt:
        evaluation_logger.log_task_complete("Monitoreo Email", "Monitoreo detenido por el usuario")
        print("\n✅ Monitoreo detenido exitosamente")

    except Exception as e:
        evaluation_logger.log_error("Monitoreo Email", f"Error crítico: {str(e)}")
        print(f"\n❌ Error crítico: {str(e)}")
        raise

def test_email_simulation():
    """Función para probar la simulación de emails"""
    print("\n🧪 MODO TESTING - SIMULACIÓN DE EMAILS")
    print("="*50)

    # Ejemplos de simulación
    test_emails = [
        {
            "subject": "ReactJS-JD - Senior Frontend Developer",
            "content": "We are looking for a Senior React.js Developer to join our team...",
            "sender": "hr@company.com"
        },
        {
            "subject": "NodeJS-JD - Backend Engineer Position",
            "content": "Exciting opportunity for a Node.js backend engineer...",
            "sender": "recruiter@startup.com"
        },
        {
            "subject": "Angular-JD - Frontend Developer",
            "content": "Angular developer needed for enterprise application...",
            "sender": "recruiting@tech.com"
        },
        {
            "subject": "AIEngineering-JD - Machine Learning Engineer",
            "content": "Join our AI team to build cutting-edge ML solutions...",
            "sender": "ai-jobs@company.com"
        },
        {
            "subject": "Java-JD - Full Stack Java Developer",
            "content": "Join our Java development team as a full stack developer...",
            "sender": "jobs@enterprise.com"
        },
        {
            "subject": "Python Developer - No Match",
            "content": "This email should be ignored...",
            "sender": "noreply@company.com"
        }
    ]

    for test_email in test_emails:
        result = simulate_incoming_email(
            subject=test_email["subject"],
            content=test_email["content"],
            sender=test_email["sender"]
        )
        print(f"\n📋 Test result: {result}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Email Monitor Agent')
    parser.add_argument('--test', action='store_true', help='Run email simulation tests')
    args = parser.parse_args()

    if args.test:
        test_email_simulation()
    else:
        main()