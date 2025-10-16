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
from cv_crew import create_cv_analysis_crew
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

class CVRequest(BaseModel):
    filename: str

class CVAnalysisResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str = None
    filename: str = None
    candidate_data: dict = None
    candidate_created: bool | None = None
    candidate_error: str | None = None
    candidate_result: dict | None = None
    candidate_status: str | None = None

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
        
        try:
            # Si es un CrewOutput, extraer su contenido
            if hasattr(result, 'raw'):
                try:
                    # Intentar parsear el raw como JSON
                    result_dict = json.loads(result.raw)
                except json.JSONDecodeError:
                    # Si no es JSON válido, crear un dict con el contenido raw
                    result_dict = {"raw_result": result.raw}
                    # Si el raw contiene el reporte formateado, intentar extraerlo
            else:
                # Si no es CrewOutput, intentar convertir a dict
                try:
                    result_dict = json.loads(str(result))
                    # Extraer el reporte formateado si existe

                except json.JSONDecodeError:
                    result_dict = {"raw_result": str(result)}
                    # Si el resultado contiene el reporte formateado, intentar extraerlo
        except Exception:
            # Fallback en caso de cualquier error
            result_dict = {"raw_result": str(result)}

        return AnalysisResponse(
            status="success",
            message="Análisis completado exitosamente",
            timestamp=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=execution_time,
            results_file=filename,
            result=result_dict,
        )
        
    except Exception as e:
        evaluation_logger.log_error("API", f"Error en análisis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el análisis: {str(e)}")

@app.post("/read-cv", response_model=CVAnalysisResponse)
async def read_cv(request: CVRequest):
    """
    Endpoint para analizar un CV desde S3 y extraer datos del candidato
    
    Args:
        request: Objeto con el nombre del archivo en S3
        
    Returns:
        CVAnalysisResponse con los datos extraídos del candidato
    """
    try:
        start_time = datetime.now()
        
        # Verificar variables de entorno
        required_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'OPENAI_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            evaluation_logger.log_error("CV API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(
                status_code=500, 
                detail=f"Variables de entorno faltantes: {missing_vars}"
            )
        
        # Log inicio del proceso
        evaluation_logger.log_task_start("CV API", f"Iniciando análisis de CV: {request.filename}")
        
        # Crear y ejecutar crew
        crew = create_cv_analysis_crew(request.filename)
        result = crew.kickoff()
        
        # Calcular tiempo de ejecución
        end_time = datetime.now()
        execution_time = str(end_time - start_time)
        
        evaluation_logger.log_task_complete("CV API", f"Análisis completado en {execution_time}")
        
        # Extraer el resultado
        result_text = str(result)
        if hasattr(result, 'raw'):
            result_text = result.raw
        
        # Intentar detectar y parsear JSON del resultado de create_candidate (si el agente lo incluyó)
        candidate_created = None
        candidate_error = None
        candidate_result = None
        try:
            import re, json as _json
            # Buscar posibles bloques JSON en el texto
            json_like = re.findall(r"\{[\s\S]*?\}", result_text)
            parsed = []
            for block in json_like:
                try:
                    obj = _json.loads(block)
                    parsed.append(obj)
                except Exception:
                    continue
            # Heurística: quedarnos con el último que tenga 'success' o 'error_type'
            for obj in reversed(parsed):
                if isinstance(obj, dict) and ("success" in obj or "error_type" in obj or "email" in obj):
                    candidate_result = obj
                    break
            if candidate_result is not None:
                if 'success' in candidate_result:
                    candidate_created = bool(candidate_result.get('success'))
                if not candidate_created:
                    candidate_error = candidate_result.get('error') or candidate_result.get('error_type')
        except Exception:
            # Si falla el parseo, lo ignoramos
            pass

        # Determinar estado legible
        candidate_status = None
        if candidate_result is not None:
            error_type = (candidate_result.get('error_type') or '').lower()
            if candidate_created is True:
                candidate_status = 'created'
            elif error_type == 'alreadyexists':
                candidate_status = 'exists'
            elif candidate_created is False and not error_type:
                candidate_status = 'failed'
        
        # Mensaje claro
        base_message = "Análisis de CV completado exitosamente"
        if candidate_status == 'created':
            base_message += " - Candidato agregado"
        elif candidate_status == 'exists':
            base_message += " - Candidato ya existía"
        elif candidate_status == 'failed':
            base_message += " - No se pudo crear el candidato"

        return CVAnalysisResponse(
            status="success",
            message=base_message,
            timestamp=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=execution_time,
            filename=request.filename,
            candidate_data={"analysis": result_text},
            candidate_created=candidate_created,
            candidate_error=candidate_error,
            candidate_result=candidate_result,
            candidate_status=candidate_status
        )
        
    except Exception as e:
        evaluation_logger.log_error("CV API", f"Error en análisis de CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el análisis del CV: {str(e)}")

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