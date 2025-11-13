#!/usr/bin/env python3
"""
Módulo para tracking de tokens en ejecuciones de CrewAI
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from fallback_estimator import estimate_from_result


class TokenTracker:
    """Clase para rastrear el uso de tokens en ejecuciones de CrewAI"""
    
    def __init__(self, log_dir: str = "logs/token_tracking"):
        """
        Inicializa el tracker de tokens
        
        Args:
            log_dir: Directorio donde se guardarán los logs de tokens
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_run = None
        self.run_data = None
    
    def start_run(self, crew_name: str, meta: Optional[Dict[str, Any]] = None) -> str:
        """
        Inicia un nuevo run de tracking
        
        Args:
            crew_name: Nombre del crew que se está ejecutando
            meta: Metadatos adicionales del run (ej: meet_id, jd_interview_id)
            
        Returns:
            run_id: ID único del run
        """
        run_id = f"{crew_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.current_run = run_id
        self.run_data = {
            "run_id": run_id,
            "crew_name": crew_name,
            "start_time": datetime.now().isoformat(),
            "meta": meta or {},
            "steps": [],
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0
        }
        return run_id
    
    def add_crew_result(
        self,
        result: Any,
        step_name: str,
        agent: Optional[str] = None,
        task: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """
        Agrega el resultado de una ejecución de crew al tracking
        
        Args:
            result: Resultado del crew.kickoff()
            step_name: Nombre del paso (ej: "crew.kickoff")
            agent: Nombre del agente (opcional)
            task: Nombre de la tarea (opcional)
            extra: Información adicional (ej: usage_metrics)
        """
        if not self.run_data:
            return
        
        step_data = {
            "step_name": step_name,
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "task": task
        }
        
        # Intentar extraer información de tokens del resultado
        usage_info = {}
        
        # Intentar obtener tokens de usage_metrics si está disponible
        if extra and "usage_metrics" in extra:
            usage_metrics = extra["usage_metrics"]
            if usage_metrics:
                # Si es un diccionario, usarlo directamente
                if isinstance(usage_metrics, dict):
                    usage_info.update(usage_metrics)
                else:
                    # Si es un objeto (como UsageMetrics), extraer sus atributos
                    if hasattr(usage_metrics, 'total_tokens'):
                        usage_info['total_tokens'] = usage_metrics.total_tokens
                    if hasattr(usage_metrics, 'prompt_tokens'):
                        usage_info['prompt_tokens'] = usage_metrics.prompt_tokens
                    if hasattr(usage_metrics, 'completion_tokens'):
                        usage_info['completion_tokens'] = usage_metrics.completion_tokens
        
        # Intentar obtener tokens del resultado directamente
        if hasattr(result, 'usage'):
            usage = result.usage
            if hasattr(usage, 'total_tokens'):
                usage_info['total_tokens'] = usage.total_tokens
            if hasattr(usage, 'prompt_tokens'):
                usage_info['prompt_tokens'] = usage.prompt_tokens
            if hasattr(usage, 'completion_tokens'):
                usage_info['completion_tokens'] = usage.completion_tokens
        elif hasattr(result, 'tokens'):
            usage_info['total_tokens'] = result.tokens
        elif hasattr(result, 'token_usage') and isinstance(result.token_usage, dict):
            usage_info.update(result.token_usage)
        
        # Si no se obtuvieron tokens o son 0, usar estimación de fallback
        total_tokens = usage_info.get('total_tokens', 0)
        if total_tokens == 0 or not usage_info:
            fallback_estimate = estimate_from_result(result)
            if fallback_estimate:
                usage_info = fallback_estimate
                usage_info['estimated'] = True  # Marcar como estimado
                print(f"⚠️ No se pudieron obtener tokens del resultado, usando estimación: {fallback_estimate['total_tokens']} tokens")
            else:
                usage_info['estimated'] = False
                usage_info.setdefault('total_tokens', 0)
                usage_info.setdefault('prompt_tokens', 0)
                usage_info.setdefault('completion_tokens', 0)
        else:
            usage_info['estimated'] = False
        
        # Actualizar totales
        if 'total_tokens' in usage_info:
            self.run_data["total_tokens"] += usage_info.get('total_tokens', 0)
        if 'prompt_tokens' in usage_info:
            self.run_data["total_prompt_tokens"] += usage_info.get('prompt_tokens', 0)
        if 'completion_tokens' in usage_info:
            self.run_data["total_completion_tokens"] += usage_info.get('completion_tokens', 0)
        
        step_data["usage"] = usage_info
        
        # Agregar información extra (asegurando que sea serializable)
        if extra:
            serializable_extra = {}
            for key, value in extra.items():
                if key == "usage_metrics" and value is not None:
                    # Convertir UsageMetrics a diccionario si es necesario
                    if isinstance(value, dict):
                        serializable_extra[key] = value
                    elif hasattr(value, 'total_tokens') or hasattr(value, 'prompt_tokens') or hasattr(value, 'completion_tokens'):
                        # Es un objeto UsageMetrics, convertirlo a dict
                        serializable_extra[key] = {
                            "total_tokens": getattr(value, 'total_tokens', None),
                            "prompt_tokens": getattr(value, 'prompt_tokens', None),
                            "completion_tokens": getattr(value, 'completion_tokens', None)
                        }
                    else:
                        serializable_extra[key] = value
                elif isinstance(value, (str, int, float, bool, type(None))):
                    serializable_extra[key] = value
                elif isinstance(value, dict):
                    serializable_extra[key] = value
                elif isinstance(value, list):
                    # Verificar que los elementos de la lista sean serializables
                    serializable_extra[key] = [
                        item if isinstance(item, (str, int, float, bool, type(None), dict)) else str(item)
                        for item in value
                    ]
                else:
                    # Convertir otros objetos a string
                    serializable_extra[key] = str(value)
            step_data["extra"] = serializable_extra
        
        self.run_data["steps"].append(step_data)
    
    def finish_run(self) -> str:
        """
        Finaliza el run y guarda el log
        
        Returns:
            path: Ruta del archivo de log guardado
        """
        if not self.run_data:
            return ""
        
        self.run_data["end_time"] = datetime.now().isoformat()
        
        # Calcular duración
        start = datetime.fromisoformat(self.run_data["start_time"])
        end = datetime.fromisoformat(self.run_data["end_time"])
        duration = (end - start).total_seconds()
        self.run_data["duration_seconds"] = duration
        
        # Guardar archivo
        filename = f"{self.current_run}.json"
        filepath = self.log_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.run_data, f, indent=2, ensure_ascii=False)
        
        # Resetear para siguiente run
        run_id = self.current_run
        self.current_run = None
        self.run_data = None
        
        return str(filepath)

