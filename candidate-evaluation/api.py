#!/usr/bin/env python3
"""
API simple para disparar el proceso de análisis de candidatos
"""

import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from crew import create_data_processing_crew
from utils.logger import evaluation_logger

app = FastAPI(
    title="Candidate Evaluation API",
    description="API para disparar el proceso de análisis de candidatos",
    version="1.0.0"
)

class AnalysisResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str = None
    results_file: str = None
    result: dict = None

@app.post("/analyze", response_model=AnalysisResponse)
async def trigger_analysis():
    """
    Endpoint que dispara el proceso completo de análisis de candidatos
    """
    try:
        start_time = datetime.now()
        
        # Verificar variables de entorno
        required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            evaluation_logger.log_error("API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(
                status_code=500, 
                detail=f"Variables de entorno faltantes: {missing_vars}"
            )
        
        # Log inicio del proceso
        evaluation_logger.log_task_start("API", "Iniciando proceso de análisis")
        
        # Crear y ejecutar crew
        crew = create_data_processing_crew()
        result = crew.kickoff()
        
        # Guardar resultados
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_results_{timestamp}.json"
        
        try:
            result_json = json.loads(str(result))
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result_json, f, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            filename = filename.replace('.json', '.txt')
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(str(result))
        
        # Calcular tiempo de ejecución
        end_time = datetime.now()
        execution_time = str(end_time - start_time)
        
        evaluation_logger.log_task_complete("API", f"Proceso completado en {execution_time}")
        
        # Preparar el resultado para retornar
        try:
            result_dict = json.loads(str(result)) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            result_dict = {"raw_result": str(result)}

        return AnalysisResponse(
            status="success",
            message="Análisis completado exitosamente",
            timestamp=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=execution_time,
            results_file=filename,
            result=result_dict
        )
        
    except Exception as e:
        evaluation_logger.log_error("API", f"Error en análisis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el análisis: {str(e)}")

@app.get("/status")
async def get_status():
    """
    Endpoint simple para verificar el estado de la API
    """
    return {
        "status": "active",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "service": "Candidate Evaluation API"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)