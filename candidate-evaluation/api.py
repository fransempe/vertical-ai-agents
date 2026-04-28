#!/usr/bin/env python3
"""
API simple para disparar el proceso de análisis de candidatos
"""

import base64
import json
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from supabase import create_client

from cv_crew import create_cv_analysis_crew
from matching_engine import run_deterministic_matching
from single_meet_crew import create_single_meet_evaluation_crew
from tools.elevenlabs_tools import (
    create_elevenlabs_agent,
    generate_elevenlabs_prompt_from_jd,
    update_elevenlabs_agent_prompt,
)
from tools.supabase_tools import (
    get_client_email,
    get_meet_evaluation_data,
    log_matching_inputs_debug,
    save_meet_evaluation,
)
from tools.vector_tools import get_supabase_client, search_similar_chunks
from utils.audit_log import (
    record_cv_candidate_audit_event,
    record_elevenlabs_agent_audit_event,
    record_evaluation_audit_event,
    record_matching_audit_event,
)
from utils.helpers import clean_uuid
from utils.logger import evaluation_logger
from utils.tech_stack import extract_tech_stack_from_jd

# ====== Helpers ======


def format_soft_skills(soft_skills: dict) -> str:
    """Formatea las habilidades blandas para el email"""
    if not soft_skills:
        return "No disponible"

    formatted = []
    skill_names = {
        "communication": "Comunicación",
        "leadership": "Liderazgo",
        "teamwork": "Trabajo en Equipo",
        "adaptability": "Adaptabilidad",
        "problem_solving": "Resolución de Problemas",
        "time_management": "Gestión del Tiempo",
        "emotional_intelligence": "Inteligencia Emocional",
        "continuous_learning": "Aprendizaje Continuo",
    }

    for key, value in soft_skills.items():
        skill_name = skill_names.get(key, key.replace("_", " ").title())
        if isinstance(value, str) and value:
            formatted.append(f"• {skill_name}: {value}")
        elif isinstance(value, (int, float)):
            formatted.append(f"• {skill_name}: {value}/10")

    return "\n".join(formatted) if formatted else "No disponible"


def format_technical_questions(questions: list) -> str:
    """Formatea las preguntas técnicas para el email"""
    if not questions:
        return "No disponible"

    formatted = []
    for i, q in enumerate(questions, 1):
        question_text = q.get("question", "N/A")
        answered = q.get("answered", "N/A")
        formatted.append(f"  {i}. {question_text} - Contestada: {answered}")

    return "\n".join(formatted) if formatted else "No disponible"


def format_english_assessment(english_assessment: dict) -> str:
    """Formatea la evaluación de inglés para el email"""
    if not isinstance(english_assessment, dict) or not english_assessment:
        return "No disponible"

    fields = [
        ("Nivel estimado", english_assessment.get("cefr_level")),
        ("Fluidez", english_assessment.get("fluency")),
        ("Vocabulario", english_assessment.get("vocabulary")),
        ("Gramática", english_assessment.get("grammar")),
        ("Comprensión", english_assessment.get("comprehension")),
        ("Claridad", english_assessment.get("clarity")),
        ("Resumen", english_assessment.get("summary")),
    ]
    formatted = [f"• {label}: {value}" for label, value in fields if value]

    evidence = english_assessment.get("evidence")
    if isinstance(evidence, list) and evidence:
        formatted.append("• Evidencia:")
        for item in evidence:
            if not isinstance(item, dict):
                continue
            question = item.get("question", "N/A")
            answer = item.get("answer", "N/A")
            evaluation = item.get("evaluation", "N/A")
            formatted.append(f"  - {question} | Respuesta: {answer} | Evaluación: {evaluation}")

    return "\n".join(formatted) if formatted else "No disponible"


def load_email_template(template_name: str) -> str:
    """
    Carga una plantilla de email desde el directorio templates/email

    Args:
        template_name: Nombre del archivo de plantilla (ej: 'evaluation_match.html')

    Returns:
        Contenido de la plantilla como string
    """
    template_path = Path(__file__).parent / "templates" / "email" / template_name
    try:
        with open(template_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        evaluation_logger.log_error("Email Template", f"Plantilla no encontrada: {template_path}")
        return ""
    except Exception as e:
        evaluation_logger.log_error("Email Template", f"Error cargando plantilla: {str(e)}")
        return ""


def render_email_template(template_name: str, **kwargs) -> str:
    """
    Carga y renderiza una plantilla de email con las variables proporcionadas

    Args:
        template_name: Nombre del archivo de plantilla
        **kwargs: Variables para reemplazar en la plantilla

    Returns:
        Plantilla renderizada con las variables reemplazadas
    """
    template = load_email_template(template_name)
    if not template:
        return ""

    try:
        return template.format(**kwargs)
    except KeyError as e:
        evaluation_logger.log_error("Email Template", f"Variable faltante en plantilla: {e}")
        return template
    except Exception as e:
        evaluation_logger.log_error("Email Template", f"Error renderizando plantilla: {str(e)}")
        return template


def b64decode(s: str) -> str:
    """
    Decodifica string Base64 con padding tolerante

    Args:
        s: String en Base64

    Returns:
        String decodificado
    """
    pad = "=" * (-len(s) % 4)
    return base64.b64decode(s + pad).decode("utf-8", "replace")


app = FastAPI(
    title="Candidate Evaluation API",
    description="API para disparar el proceso de análisis de candidatos",
    version="1.0.0",
)

# Storage para runs (en producción usar Redis o DB)
matching_runs: dict[str, dict] = {}


class SingleMeetRequest(BaseModel):
    meet_id: str


class AnalysisResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str | None = None
    results_file: str | None = None
    result: dict | None = None
    jd_interview_id: str | None = None
    evaluation_id: str | None = None


class CVRequest(BaseModel):
    filename: str
    client_id: str = None
    user_id: str = None


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


class MatchingRequest(BaseModel):
    user_id: str = None
    client_id: str = None


class MatchingResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    execution_time: str = None
    matches: list = None
    total_matches: int = None


class RunStatusResponse(BaseModel):
    status: str
    runId: str = None
    progress: float = None
    message: str = None
    result: dict = None
    error: str = None


@app.post("/read-cv", response_model=CVAnalysisResponse)
async def read_cv(request: CVRequest):
    """
    Endpoint para analizar un CV desde S3 y extraer datos del candidato

    Args:
        request: Objeto con el nombre del archivo en S3

    Returns:
        CVAnalysisResponse con los datos extraídos del candidato
    """
    audit_recorded = False
    try:
        start_time = datetime.now()
        # Verificar variables de entorno
        required_env_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            evaluation_logger.log_error("CV API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(status_code=500, detail=f"Variables de entorno faltantes: {missing_vars}")

        # Log inicio del proceso
        evaluation_logger.log_task_start("CV API", f"Iniciando análisis de CV: {request.filename}")

        # Crear y ejecutar crew
        crew = create_cv_analysis_crew(request.filename, user_id=request.user_id, client_id=request.client_id)

        print("=" * 80)
        print("🚀 INICIANDO EJECUCIÓN DEL CREW (CV Analysis)")
        print("=" * 80)

        result = await run_in_threadpool(crew.kickoff)

        # Calcular tiempo de ejecución
        end_time = datetime.now()
        execution_time = str(end_time - start_time)

        evaluation_logger.log_task_complete("CV API", f"Análisis completado en {execution_time}")

        # Extraer el resultado
        result_text = str(result)
        if hasattr(result, "raw"):
            result_text = result.raw

        # Intentar detectar y parsear JSON del resultado de create_candidate (si el agente lo incluyó)
        candidate_created = None
        candidate_error = None
        candidate_result = None
        try:
            import json as _json
            import re

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
                if "success" in candidate_result:
                    candidate_created = bool(candidate_result.get("success"))
                if not candidate_created:
                    candidate_error = candidate_result.get("error") or candidate_result.get("error_type")
        except Exception:
            # Si falla el parseo, lo ignoramos
            pass

        # Determinar estado legible
        candidate_status = None
        if candidate_result is not None:
            error_type = (candidate_result.get("error_type") or "").lower()
            if candidate_created is True:
                candidate_status = "created"
            elif error_type == "alreadyexists":
                candidate_status = "exists"
            elif candidate_created is False and not error_type:
                candidate_status = "failed"

        # Mensaje claro
        base_message = "Análisis de CV completado exitosamente"
        if candidate_status == "created":
            base_message += " - Candidato agregado"
        elif candidate_status == "exists":
            base_message += " - Candidato ya existía"
        elif candidate_status == "failed":
            base_message += " - No se pudo crear el candidato"

        audit_status = "failed" if candidate_status == "failed" else "success"
        record_cv_candidate_audit_event(
            filename=request.filename,
            action="candidate_creation_from_cv",
            status=audit_status,
            metadata={
                "endpoint": "POST /read-cv",
                "filename": request.filename,
                "user_id": request.user_id,
                "client_id": request.client_id,
                "execution_time": execution_time,
                "candidate_created": candidate_created,
                "candidate_status": candidate_status,
                "candidate_email": candidate_result.get("email") if isinstance(candidate_result, dict) else None,
                "candidate_error": candidate_error,
            },
            error_message=candidate_error if audit_status == "failed" else None,
        )
        audit_recorded = True

        return CVAnalysisResponse(
            status="success",
            message=base_message,
            timestamp=start_time.strftime("%Y-%m-%d %H:%M:%S"),
            execution_time=execution_time,
            filename=request.filename,
            candidate_data={"analysis": result_text},
            candidate_created=candidate_created,
            candidate_error=candidate_error,
            candidate_result=candidate_result,
            candidate_status=candidate_status,
        )

    except Exception as e:
        if not audit_recorded:
            failed_filename = getattr(request, "filename", "unknown")
            record_cv_candidate_audit_event(
                filename=failed_filename,
                action="candidate_creation_from_cv",
                status="failed",
                metadata={
                    "endpoint": "POST /read-cv",
                    "filename": failed_filename,
                    "user_id": getattr(request, "user_id", None),
                    "client_id": getattr(request, "client_id", None),
                },
                error_message=str(e),
            )
        evaluation_logger.log_error("CV API", f"Error en análisis de CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el análisis del CV: {str(e)}")


def do_matching_long_task(run_id: str, user_id: str | None, client_id: str | None):
    """
    Ejecuta el proceso de matching en background
    """
    try:
        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.0,
            "message": "Iniciando proceso de matching...",
            "runId": run_id,
        }

        start_time = datetime.now()

        # Verificar variables de entorno
        required_env_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            error_msg = f"Variables de entorno faltantes: {missing_vars}"
            matching_runs[run_id] = {
                "status": "error",
                "error": error_msg,
                "runId": run_id,
            }
            record_matching_audit_event(
                run_id=run_id,
                action="candidate_matching",
                status="failed",
                metadata={
                    "process": "do_matching_long_task",
                    "user_id": user_id,
                    "client_id": client_id,
                    "missing_env_vars": missing_vars,
                },
                error_message=error_msg,
            )
            return

        # Log inicio del proceso
        if user_id and client_id:
            evaluation_logger.log_task_start(
                "Matching API", f"Iniciando proceso de matching filtrado por user_id: {user_id}, client_id: {client_id}"
            )
            print(f"[MATCHING API] 🚀 Iniciando matching con filtros - user_id: {user_id}, client_id: {client_id}")
        else:
            evaluation_logger.log_task_start("Matching API", "Iniciando proceso de matching (sin filtros)")
            print("[MATCHING API] 🚀 Iniciando matching SIN filtros (todos los candidatos)")

        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.2,
            "message": "Cargando datos y ejecutando matching determinístico...",
            "runId": run_id,
        }

        print("[MATCHING API] 📋 Matching determinístico (fase 2: stack/JD)...")
        log_matching_inputs_debug(user_id=user_id, client_id=client_id)

        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.4,
            "message": "Ejecutando matching...",
            "runId": run_id,
        }

        matches_list = run_deterministic_matching(user_id=user_id, client_id=client_id)
        evaluation_logger.log_task_progress(
            "Matching API", f"Matches determinísticos: {len(matches_list)} candidato(s) con al menos una búsqueda"
        )
        print(f"[MATCHING API] ✅ Matching determinístico: {len(matches_list)} grupo(s) de candidatos con matches")

        matching_runs[run_id] = {
            "status": "running",
            "progress": 0.7,
            "message": "Finalizando...",
            "runId": run_id,
        }

        end_time = datetime.now()
        execution_time = str(end_time - start_time)

        evaluation_logger.log_task_complete("Matching API", f"Matching completado en {execution_time}")

        total_matches = len(matches_list)

        result_data = {
            "status": "success",
            "message": "Matching de candidatos completado exitosamente (motor determinístico)",
            "timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "execution_time": execution_time,
            "matches": matches_list,
            "total_matches": total_matches,
        }

        matching_runs[run_id] = {
            "status": "done",
            "progress": 1.0,
            "message": "Matching completado exitosamente",
            "result": result_data,
            "runId": run_id,
        }
        record_matching_audit_event(
            run_id=run_id,
            action="candidate_matching",
            status="success",
            metadata={
                "process": "do_matching_long_task",
                "user_id": user_id,
                "client_id": client_id,
                "execution_time": execution_time,
                "total_matches": total_matches,
            },
        )

    except Exception as e:
        error_msg = str(e)
        evaluation_logger.log_error("Matching API", f"Error en matching: {error_msg}")
        matching_runs[run_id] = {"status": "error", "error": error_msg, "runId": run_id}
        record_matching_audit_event(
            run_id=run_id,
            action="candidate_matching",
            status="failed",
            metadata={
                "process": "do_matching_long_task",
                "user_id": user_id,
                "client_id": client_id,
            },
            error_message=error_msg,
        )


@app.post("/match-candidates")
async def match_candidates(request: MatchingRequest = None):
    """
    Endpoint para iniciar matching entre candidatos (tech_stack) y entrevistas (job_description)
    Retorna inmediatamente con un runId para consultar el estado

    Args:
        request: Objeto con user_id y client_id opcionales para filtrar candidatos

    Returns:
        JSON con runId para consultar el estado del proceso
    """
    try:
        user_id = request.user_id if request else None
        client_id = request.client_id if request else None

        # Generar runId único
        run_id = str(uuid.uuid4())

        # Inicializar estado
        matching_runs[run_id] = {"status": "queued", "progress": 0.0, "message": "Proceso en cola...", "runId": run_id}

        # Ejecutar en background usando threading
        thread = threading.Thread(target=do_matching_long_task, args=(run_id, user_id, client_id), daemon=True)
        thread.start()

        # Retornar inmediatamente con runId
        return Response(
            content=json.dumps(
                {
                    "runId": run_id,
                    "status": "queued",
                    "message": "Matching iniciado, consulta el estado con GET /match-candidates/{runId}",
                }
            ),
            status_code=202,
            media_type="application/json",
        )

    except Exception as e:
        failed_run_id = locals().get("run_id", "unknown")
        failed_user_id = locals().get("user_id", None)
        failed_client_id = locals().get("client_id", None)
        record_matching_audit_event(
            run_id=failed_run_id,
            action="candidate_matching",
            status="failed",
            metadata={
                "endpoint": "POST /match-candidates",
                "phase": "queue",
                "user_id": failed_user_id,
                "client_id": failed_client_id,
            },
            error_message=str(e),
        )
        evaluation_logger.log_error("Matching API", f"Error iniciando matching: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error iniciando matching: {str(e)}")


@app.get("/match-candidates/{run_id}")
async def get_matching_status(run_id: str):
    """
    Endpoint para consultar el estado del proceso de matching

    Args:
        run_id: ID del proceso de matching

    Returns:
        Estado del proceso: queued, running, done, o error
    """
    if run_id not in matching_runs:
        raise HTTPException(status_code=404, detail="runId not found")

    run_data = matching_runs[run_id]

    # Formatear respuesta según el estado (formato compatible con RunStatus del frontend)
    if run_data["status"] == "done":
        return {"status": "done", "result": run_data.get("result")}
    elif run_data["status"] == "error":
        return {"status": "error", "error": run_data.get("error", "Unknown error")}
    else:
        # queued o running
        return {
            "status": run_data["status"],
            "progress": run_data.get("progress", 0.0),
            "message": run_data.get("message", ""),
        }


@app.get("/status")
async def get_status():
    """
    Endpoint simple para verificar el estado de la API
    """
    return {
        "status": "active",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "service": "Candidate Evaluation API",
    }


@app.post("/evaluate-meet", response_model=AnalysisResponse)
async def evaluate_single_meet(request: SingleMeetRequest):
    """
    Endpoint que evalúa un solo meet para determinar si el candidato es un posible match
    basado en la JD del meet

    Args:
        request: Objeto con meet_id del meet a evaluar
    """
    try:
        meet_id = request.meet_id
        evaluation_logger.log_task_start("API", f"Iniciando evaluación de meet: {meet_id}")

        start_time = datetime.now()

        # Crear y ejecutar crew de evaluación individual
        # COMENTADO PARA PROBAR CON DATOS MOCKEADOS
        crew = create_single_meet_evaluation_crew(meet_id)

        print("=" * 80)
        print("🚀 INICIANDO EJECUCIÓN DEL CREW (Single Meet Evaluation)")
        print("=" * 80)

        result = await run_in_threadpool(crew.kickoff)

        # RECORDAR DESCOMENTAR LA LINEA QUE HACE EL FULL_RESULT = RESULT
        print("Cargando datos mockados desde utils/data.json")
        # result = json.load(open("utils/data.json", "r", encoding="utf-8"))
        # print("result: ", result)

        end_time = datetime.now()
        execution_time = end_time - start_time

        evaluation_logger.log_task_complete("API", f"Evaluación de meet completada - Tiempo: {execution_time}")

        # Extraer el contenido del resultado del crew
        full_result = None

        # 1) Caso ideal: el resultado YA es un dict JSON
        if isinstance(result, dict):
            full_result = result
        # 2) Caso CrewOutput u objeto similar con .raw/.content
        elif hasattr(result, "raw") and isinstance(result.raw, dict):
            full_result = result.raw
        elif hasattr(result, "content") and isinstance(result.content, dict):
            full_result = result.content
        else:
            # 3) Fallback: trabajar con string y buscar JSON dentro
            result_str = None
            if hasattr(result, "raw"):
                result_str = result.raw
            elif hasattr(result, "content"):
                result_str = result.content
            else:
                result_str = str(result)

            # Intentar parsear como JSON (puede venir en formato ```json ... ```)
            try:
                # Buscar JSON dentro de markdown code blocks
                json_match = re.search(r"```json\s*(\{.*\})\s*```", result_str, re.DOTALL)
                full_result = json.loads(json_match.group(1)) if json_match else json.loads(result_str)
            except (json.JSONDecodeError, AttributeError):
                # Si no es JSON válido, intentar extraer cualquier objeto JSON del texto
                try:
                    json_match = re.search(r"\{.*\}", result_str, re.DOTALL)
                    if json_match:
                        full_result = json.loads(json_match.group(0))
                    else:
                        evaluation_logger.log_error(
                            "API",
                            "No se pudo parsear el resultado como JSON (sin bloque JSON detectable)",
                        )
                        full_result = {}
                except Exception as parse_err:
                    evaluation_logger.log_error(
                        "API",
                        f"No se pudo parsear el resultado como JSON: {parse_err}",
                    )
                    full_result = {}

        # ===== Fallback crítico: asegurar meet_id, candidate.id y jd_interview.id =====
        if not isinstance(full_result, dict):
            full_result = {}

        # Siempre asegurar que haya meet_id en el resultado final
        if not full_result.get("meet_id"):
            full_result["meet_id"] = meet_id

        # Verificar si faltan candidate.id o jd_interview.id
        candidate_obj = full_result.get("candidate") or {}
        jd_obj = full_result.get("jd_interview") or {}
        needs_candidate = not isinstance(candidate_obj, dict) or not candidate_obj.get("id")
        needs_jd = not isinstance(jd_obj, dict) or not jd_obj.get("id")

        if needs_candidate or needs_jd:
            try:
                # Reutilizar la función get_meet_evaluation_data para obtener datos mínimos
                func_to_call = None
                if hasattr(get_meet_evaluation_data, "__wrapped__"):
                    func_to_call = get_meet_evaluation_data.__wrapped__
                elif hasattr(get_meet_evaluation_data, "func"):
                    func_to_call = get_meet_evaluation_data.func
                elif hasattr(get_meet_evaluation_data, "_func"):
                    func_to_call = get_meet_evaluation_data._func
                elif callable(get_meet_evaluation_data) and not hasattr(get_meet_evaluation_data, "name"):
                    func_to_call = get_meet_evaluation_data

                if func_to_call:
                    meet_data_json = func_to_call(meet_id)
                    meet_data = json.loads(meet_data_json) if isinstance(meet_data_json, str) else meet_data_json

                    conversation_data = meet_data.get("conversation") or {}
                    jd_data = meet_data.get("jd_interview") or {}
                    candidate_from_conv = conversation_data.get("candidate") or {}

                    # Rellenar candidate.id (y datos básicos) si falta
                    if needs_candidate and candidate_from_conv.get("id"):
                        full_result["candidate"] = {
                            "id": candidate_from_conv.get("id"),
                            "name": candidate_from_conv.get("name"),
                            "email": candidate_from_conv.get("email"),
                            "phone": candidate_from_conv.get("phone"),
                            "cv_url": candidate_from_conv.get("cv_url"),
                            "tech_stack": candidate_from_conv.get("tech_stack"),
                        }

                    # Rellenar jd_interview.id si falta
                    if needs_jd and jd_data.get("id"):
                        # Copiar datos clave de la JD para que queden disponibles en la evaluación
                        full_result["jd_interview"] = {
                            "id": jd_data.get("id"),
                            "interview_name": jd_data.get("interview_name"),
                            "job_description": jd_data.get("job_description"),
                            "tech_stack": jd_data.get("tech_stack"),
                            "client_id": jd_data.get("client_id"),
                            "created_at": jd_data.get("created_at"),
                        }

                    evaluation_logger.log_task_progress(
                        "API",
                        "full_result completado con meet_id/candidate.id/jd_interview.id desde get_meet_evaluation_data",
                    )
            except Exception as enrich_err:
                # Si falla el enriquecimiento, lo registramos pero no rompemos la API
                evaluation_logger.log_error(
                    "API",
                    f"Error enriqueciendo full_result con datos mínimos de meet: {enrich_err}",
                )

        # Extraer solo los campos finales del match_evaluation
        result_data: dict[str, Any] = {
            "final_recommendation": None,
            "justification": None,
            "is_potential_match": None,
            "compatibility_score": None,
            # Campo para exponer en el resultado final el resumen de emociones de voz
            "emotion_sentiment_summary": None,
            # Campo para exponer un resumen del análisis de seniority
            "seniority_analysis": None,
        }

        # Buscar en match_evaluation
        if isinstance(full_result, dict):
            match_eval = full_result.get("match_evaluation", {})
            if isinstance(match_eval, dict):
                result_data["final_recommendation"] = match_eval.get("final_recommendation")
                result_data["justification"] = match_eval.get("justification")
                result_data["is_potential_match"] = match_eval.get("is_potential_match")
                result_data["compatibility_score"] = match_eval.get("compatibility_score")
                # Exponer también el bloque de análisis de seniority si está disponible
                result_data["seniority_analysis"] = match_eval.get("seniority_analysis")

        # ===== Verificar si el agente procesó emotion_analysis =====
        # El agente ahora recibe emotion_analysis a través de get_meet_evaluation_data
        # y debe procesarlo en su análisis. Solo verificamos si lo hizo y agregamos datos raw si falta.
        try:
            if isinstance(full_result, dict):
                conversation_analysis = full_result.get("conversation_analysis") or {}
                emotion_summary = conversation_analysis.get("emotion_sentiment_summary")

                # Si el agente no procesó los datos de emociones, intentar obtenerlos y agregarlos como fallback
                if not emotion_summary or not emotion_summary.get("prosody_summary_text"):
                    url = os.getenv("SUPABASE_URL")
                    key = os.getenv("SUPABASE_KEY")
                    if url and key:
                        supabase = create_client(url, key)

                        # Tomar la conversación más reciente asociada al meet
                        conv_resp = (
                            supabase.table("conversations")
                            .select("emotion_analysis")
                            .eq("meet_id", meet_id)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                        )

                        if conv_resp.data and len(conv_resp.data) > 0:
                            emotion_analysis = conv_resp.data[0].get("emotion_analysis")
                            if emotion_analysis:
                                # Solo agregar datos raw si el agente no los procesó
                                if not emotion_summary:
                                    conversation_analysis["emotion_sentiment_summary"] = {
                                        "raw_emotion_analysis": emotion_analysis,
                                        "prosody_summary_text": None,
                                        "burst_summary_text": None,
                                    }
                                    full_result["conversation_analysis"] = conversation_analysis
                                    evaluation_logger.log_task_progress(
                                        "API",
                                        "Datos raw de emotion_analysis agregados (el agente no los procesó)",
                                    )
                                elif not emotion_summary.get("raw_emotion_analysis"):
                                    # Agregar solo raw_emotion_analysis si falta
                                    emotion_summary["raw_emotion_analysis"] = emotion_analysis
                                    conversation_analysis["emotion_sentiment_summary"] = emotion_summary
                                    full_result["conversation_analysis"] = conversation_analysis

                # Exponer resumen en result_data si existe
                if emotion_summary:
                    result_data["emotion_sentiment_summary"] = {
                        "prosody_summary_text": emotion_summary.get("prosody_summary_text"),
                        "burst_summary_text": emotion_summary.get("burst_summary_text"),
                    }
        except Exception as emotion_err:
            evaluation_logger.log_error(
                "API",
                f"Error al verificar/agregar emotion_analysis: {emotion_err}",
            )

        # Guardar evaluación en la base de datos - MEET_EVALUATIONS
        evaluation_id = None
        if isinstance(full_result, dict) and full_result:
            try:
                # Convertir full_result a JSON string para la función
                full_result_json = json.dumps(full_result, ensure_ascii=False)

                # Acceder a la función subyacente del Tool
                func_to_call = None
                if hasattr(save_meet_evaluation, "__wrapped__"):
                    func_to_call = save_meet_evaluation.__wrapped__
                elif hasattr(save_meet_evaluation, "func"):
                    func_to_call = save_meet_evaluation.func
                elif hasattr(save_meet_evaluation, "_func"):
                    func_to_call = save_meet_evaluation._func
                else:
                    # Intentar llamar directamente
                    func_to_call = save_meet_evaluation

                if func_to_call:
                    save_result = func_to_call(full_result_json)
                    save_result_data = json.loads(save_result) if isinstance(save_result, str) else save_result

                    if save_result_data.get("success"):
                        evaluation_id = save_result_data.get("evaluation_id")
                        action = save_result_data.get("action", "created")
                        evaluation_logger.log_task_complete(
                            "API", f"Evaluación guardada en meet_evaluation: {evaluation_id} (acción: {action})"
                        )
                        print(f"✅ Evaluación guardada en meet_evaluation: {evaluation_id}")
                    else:
                        error_msg = save_result_data.get("error", "Error desconocido")
                        evaluation_logger.log_error(
                            "API", f"Error guardando evaluación en meet_evaluation: {error_msg}"
                        )
                        print(f"⚠️ Error guardando evaluación: {error_msg}")
                else:
                    evaluation_logger.log_error(
                        "API", "No se pudo acceder a la función subyacente de save_meet_evaluation"
                    )
                    print("⚠️ No se pudo acceder a la función subyacente de save_meet_evaluation")
            except Exception as save_error:
                evaluation_logger.log_error("API", f"Error al guardar evaluación en meet_evaluation: {str(save_error)}")
                print(f"⚠️ Error al guardar evaluación: {str(save_error)}")
                import traceback

                evaluation_logger.log_error("API", f"Traceback: {traceback.format_exc()}")

        # Si es un posible match, enviar email del cliente del JD interview
        email_sent = False
        if result_data.get("is_potential_match") is True:
            try:
                # Obtener datos del meet para conseguir jd_interviews_id
                url = os.getenv("SUPABASE_URL")
                key = os.getenv("SUPABASE_KEY")
                supabase = create_client(url, key)

                # Obtener el meet con jd_interview y client
                meet_response = (
                    supabase.table("meets")
                    .select(
                        """
                    jd_interviews_id,
                    jd_interviews(
                        interview_name,
                        client_id,
                        clients(
                            email,
                            name,
                            responsible,
                            phone
                        )
                    )
                    """
                    )
                    .eq("id", meet_id)
                    .execute()
                )

                if meet_response.data and len(meet_response.data) > 0:
                    meet = meet_response.data[0]
                    jd_interviews_id = meet.get("jd_interviews_id")
                    jd_interview = meet.get("jd_interviews")

                    if jd_interview:
                        interview_name = jd_interview.get("interview_name", "N/A")
                        client = jd_interview.get("clients")

                        if client and client.get("email"):
                            client_email = client.get("email")
                            client_name = client.get("name", "N/A")
                            client_responsible = client.get("responsible", "N/A")
                            client_phone = client.get("phone", "N/A")

                            # Obtener datos completos para el email
                            candidate_data = full_result.get("candidate", {})
                            conversation_data = full_result.get("conversation_analysis", {})
                            emotion_summary = (
                                conversation_data.get("emotion_sentiment_summary", {})
                                if isinstance(conversation_data, dict)
                                else {}
                            )
                            prosody_summary_text = emotion_summary.get("prosody_summary_text")
                            burst_summary_text = emotion_summary.get("burst_summary_text")

                            # Obtener la conversación completa del meet
                            conversation_response = (
                                supabase.table("conversations")
                                .select("conversation_data")
                                .eq("meet_id", meet_id)
                                .execute()
                            )

                            conversation_text = "No disponible"
                            if conversation_response.data and len(conversation_response.data) > 0:
                                conv_data = conversation_response.data[0].get("conversation_data", {})
                                if isinstance(conv_data, dict):
                                    # Formatear conversación como texto
                                    messages = conv_data.get("messages", [])
                                    if messages:
                                        conv_lines = []
                                        for msg in messages:
                                            role = msg.get("role", "unknown")
                                            content = msg.get("content", "")
                                            if role == "user":
                                                conv_lines.append(f"👤 Candidato: {content}")
                                            elif role == "assistant" or role == "ai":
                                                conv_lines.append(f"🤖 Entrevistador: {content}")
                                            else:
                                                conv_lines.append(f"{role}: {content}")
                                        conversation_text = "\n\n".join(conv_lines)
                                elif isinstance(conv_data, str):
                                    conversation_text = conv_data

                            # Crear asunto del email
                            subject = f"✅ Match Potencial - {interview_name} - Score: {result_data.get('compatibility_score', 0)}%"

                            # Preparar datos para la plantilla
                            tech_stack = candidate_data.get("tech_stack", [])
                            tech_stack_str = ", ".join(tech_stack) if isinstance(tech_stack, list) else str(tech_stack)

                            technical_assessment = conversation_data.get("technical_assessment", {})
                            english_assessment = conversation_data.get("english_assessment", {})

                            # Renderizar plantilla de email
                            body = render_email_template(
                                "evaluation_match.html",
                                interview_name=interview_name,
                                compatibility_score=result_data.get("compatibility_score", 0),
                                final_recommendation=result_data.get("final_recommendation", "N/A"),
                                candidate_name=candidate_data.get("name", "N/A"),
                                candidate_email=candidate_data.get("email", "N/A"),
                                candidate_phone=candidate_data.get("phone", "N/A"),
                                candidate_tech_stack=tech_stack_str,
                                candidate_cv_url=candidate_data.get("cv_url", "N/A"),
                                soft_skills_formatted=format_soft_skills(conversation_data.get("soft_skills", {})),
                                emotion_prosody_summary_text=prosody_summary_text
                                or "No se detectaron emociones predominantes en la voz continua.",
                                emotion_burst_summary_text=burst_summary_text
                                or "No se detectaron emociones predominantes en los vocal bursts.",
                                knowledge_level=technical_assessment.get("knowledge_level", "N/A"),
                                practical_experience=technical_assessment.get("practical_experience", "N/A"),
                                technical_questions_formatted=format_technical_questions(
                                    technical_assessment.get("technical_questions", [])
                                ),
                                english_assessment_formatted=format_english_assessment(english_assessment),
                                justification=result_data.get("justification", "No disponible"),
                                conversation_text=conversation_text,
                                client_name=client_name,
                                client_responsible=client_responsible,
                                client_phone=client_phone,
                                client_email=client_email,
                                meet_id=meet_id,
                                jd_interviews_id=jd_interviews_id,
                            )

                            # Enviar email (requests comentado: datos mockeados)
                            _email_api_url = os.getenv("EMAIL_API_URL")

                            _payload = {
                                "to_email": client_email,
                                "subject": subject,
                                "body": body,
                            }

                            # COMENTADO PARA PROBAR CON DATOS MOCKEADOS
                            # response = requests.post(
                            #     _email_api_url,
                            #     json=_payload,
                            #     headers={'Content-Type': 'application/json'},
                            #     timeout=30
                            # )
                            # response.raise_for_status()
                            email_sent = True
                            evaluation_logger.log_task_complete(
                                "Envío Email Match", f"Email enviado exitosamente a {client_email}"
                            )
                        else:
                            evaluation_logger.log_error(
                                "Envío Email Match", "No se encontró email del cliente en la tabla clients"
                            )
                    else:
                        evaluation_logger.log_error("Envío Email Match", "No se encontró jd_interview para el meet")

            except Exception as email_error:
                evaluation_logger.log_error("Envío Email Match", f"Error enviando email de match: {str(email_error)}")
                # No fallar la respuesta por error en el email

        record_evaluation_audit_event(
            meet_id=meet_id,
            action="candidate_evaluation",
            status="success",
            metadata={
                "endpoint": "POST /evaluate-meet",
                "evaluation_id": evaluation_id,
                "execution_time": str(execution_time),
                "final_recommendation": result_data.get("final_recommendation"),
                "is_potential_match": result_data.get("is_potential_match"),
                "compatibility_score": result_data.get("compatibility_score"),
                "email_sent": email_sent,
            },
        )

        return AnalysisResponse(
            status="success",
            message=f"Evaluación del meet {meet_id} completada exitosamente"
            + (" - Email enviado" if email_sent else ""),
            timestamp=end_time.strftime("%Y-%m-%d %H:%M:%S"),
            execution_time=str(execution_time),
            result=result_data,
        )

    except Exception as e:
        failed_meet_id = getattr(request, "meet_id", "unknown")
        record_evaluation_audit_event(
            meet_id=failed_meet_id,
            action="candidate_evaluation",
            status="failed",
            metadata={"endpoint": "POST /evaluate-meet"},
            error_message=str(e),
        )
        evaluation_logger.log_error("API", f"Error en evaluación de meet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en la evaluación: {str(e)}")


class CreateAgentRequest(BaseModel):
    jd_interview_id: str


class UpdateAgentRequest(BaseModel):
    jd_interview_id: str


class CreateAgentResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    jd_interview_id: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None


class ChatbotRequest(BaseModel):
    message: str
    conversation_history: list[dict[str, str]] | None = []


class ChatbotResponse(BaseModel):
    response: str
    sources: list[dict[str, Any]] | None = []
    model: str | None = None
    timestamp: str | None = None


class CandidateInfoResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    candidate: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] | None = None  # Para búsquedas por nombre
    related_meets: list[dict[str, Any]] | None = None
    related_evaluations: list[dict[str, Any]] | None = None


def _update_elevenlabs_agent_impl(request: UpdateAgentRequest) -> dict:
    """Lógica síncrona (Supabase / ElevenLabs / indexación); run_in_threadpool desde el handler async."""
    try:
        start_time = datetime.now()
        jd_interview_id = request.jd_interview_id

        evaluation_logger.log_task_start(
            "Actualizar Agente ElevenLabs", f"Actualizando prompt para jd_interview_id: {jd_interview_id}"
        )

        required_env_vars = ["SUPABASE_URL", "SUPABASE_KEY", "ELEVENLABS_API_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            error_msg = f"Variables de entorno faltantes: {missing_vars}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

        jd_response = supabase.table("jd_interviews").select("*").eq("id", jd_interview_id).limit(1).execute()
        if not jd_response.data or len(jd_response.data) == 0:
            error_msg = f"No se encontró jd_interview con ID: {jd_interview_id}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        jd_data = jd_response.data[0]
        job_description = jd_data.get("job_description", "")
        interview_name = jd_data.get("interview_name", "")
        client_id = jd_data.get("client_id")
        agent_id = jd_data.get("agent_id")

        if not job_description:
            error_msg = f"El jd_interview {jd_interview_id} no tiene job_description"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        if not agent_id:
            error_msg = f"El jd_interview {jd_interview_id} no tiene agent_id asociado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        if not client_id:
            error_msg = f"El jd_interview {jd_interview_id} no tiene client_id asociado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        tech_stack = extract_tech_stack_from_jd(job_description, interview_name)

        func_to_call = None
        if hasattr(get_client_email, "__wrapped__"):
            func_to_call = get_client_email.__wrapped__
        elif hasattr(get_client_email, "func"):
            func_to_call = get_client_email.func
        elif hasattr(get_client_email, "_func"):
            func_to_call = get_client_email._func
        else:
            error_msg = "No se pudo acceder a la función get_client_email"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        client_email_result = func_to_call(client_id)
        client_email_data = (
            json.loads(client_email_result) if isinstance(client_email_result, str) else client_email_result
        )

        if "error" in client_email_data:
            error_msg = f"Error obteniendo email del cliente: {client_email_data.get('error')}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        sender_email = client_email_data.get("email", "")
        if not sender_email:
            error_msg = f"El cliente {client_id} no tiene email configurado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        prompt_data = generate_elevenlabs_prompt_from_jd(
            interview_name=interview_name,
            job_description=job_description,
            sender_email=sender_email,
        )
        generated_prompt = prompt_data.get("prompt", "").strip()
        if not generated_prompt:
            error_msg = "No se pudo generar un nuevo prompt para ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        estructura_obligatoria = """

**ESTRUCTURA OBLIGATORIA DE LA ENTREVISTA:**

Debes realizar EXACTAMENTE las siguientes preguntas en este orden:

1. **1 PREGUNTA DE RESPONSABILIDADES EN EXPERIENCIA LABORAL:**
   - Realiza 1 pregunta sobre experiencia laboral del candidato
   - Leer del JSON del get-candidate-info las propiedades "responsibilities" y "experiencia" y tomar algunas de las responsabilidades que tuvo el candidato para poder preguntar sobre esa responsabilidad.
   - Haz una pregunta a la vez y espera la respuesta antes de continuar

2. **1 PREGUNTA DE HABILIDADES BLANDAS:**
   - Realiza 1 pregunta breve sobre habilidades blandas del candidato
   - Ejemplos: comunicación, trabajo en equipo, liderazgo, resolución de problemas, adaptabilidad, gestión del tiempo
   - Esta pregunta debe evaluar las competencias interpersonales y profesionales del candidato
   - Haz una pregunta a la vez y espera la respuesta antes de continuar

3. **10 A 15 PREGUNTAS TÉCNICAS DEL PUESTO:**
   - Realiza entre 10 y 15 preguntas técnicas específicas basadas en la descripción del puesto
   - Las preguntas deben estar directamente relacionadas con las tecnologías, herramientas y conocimientos técnicos mencionados en la descripción del puesto
   - Sé específico y técnico, evaluando el conocimiento real del candidato
   - Haz una pregunta a la vez y espera la respuesta antes de continuar

4. **3 PREGUNTAS EN INGLÉS PARA EVALUAR IDIOMA:**
   - Al finalizar las preguntas técnicas, avisá claramente al candidato que ahora vas a cambiar a inglés para evaluar su nivel de idioma.
   - Decí algo similar a: "Ahora vamos a cambiar a inglés para hacer tres preguntas breves y evaluar tu nivel de idioma."
   - Elegí de forma random EXACTAMENTE 3 preguntas del siguiente banco, sin repetir, una a la vez, esperando la respuesta antes de continuar:
     1. "What is your current role and what are your main responsibilities?"
     2. "Can you describe a challenging project you worked on and how you handled it?"
     3. "What has been your biggest professional learning in the last year?"
     4. "What are you expecting from your next professional challenge?"
     5. "Based on the role description, why do you think this position is a good match for you?"
   - Pedí que responda en inglés y mantené esta parte de la entrevista en inglés.

**REGLAS IMPORTANTES:**
- Mantén un tono profesional pero amigable
- Evalúa las respuestas del candidato de manera objetiva
- Guía la conversación de manera estructurada
- Responde en español de manera clara y concisa
- NO hagas más de 1 pregunta sobre la experiencia del candidato
- NO hagas más de 1 pregunta de habilidades blandas
- Haz como mínimo 10 y como máximo 15 preguntas técnicas. NO hagas menos de 10 ni más de 15.
- Hacé EXACTAMENTE 3 preguntas en inglés, elegidas de forma random del banco indicado. NO hagas más ni menos que 3.
- En total deben ser entre 15 y 20 preguntas evaluativas: 1 de experiencia, 1 de habilidades blandas, entre 10 y 15 técnicas y 3 en inglés.
- Al finalizar las preguntas evaluativas, agrega SIEMPRE una pregunta final de cierre: "¿Tenés alguna pregunta o alguna duda?"
- Hacia el final de la entrevista, incentiva activamente al candidato a realizar preguntas sobre el proceso, el rol o el cliente
- Antes de cerrar la entrevista, indicá explícitamente: "Para finalizar la entrevista con éxito, hacé click en Finalizar y luego cierra la ventana del navegador"
- Después de esa indicación, agradece al candidato y cierra la entrevista"""

        full_prompt_text = generated_prompt + estructura_obligatoria

        update_result = update_elevenlabs_agent_prompt(agent_id=str(agent_id), prompt_text=full_prompt_text)
        if not update_result:
            error_msg = "No se pudo actualizar el agente de ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        updated_jd_data = {**jd_data, "tech_stack": tech_stack}
        tech_stack_update = (
            supabase.table("jd_interviews").update({"tech_stack": tech_stack}).eq("id", jd_interview_id).execute()
        )
        if not tech_stack_update.data:
            error_msg = f"No se pudo guardar tech_stack en jd_interview {jd_interview_id}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        updated_jd_data = tech_stack_update.data[0]
        evaluation_logger.log_task_progress(
            "Actualizar Agente ElevenLabs",
            f"Tech stack extraido y guardado en jd_interviews: {tech_stack}",
        )

        execution_time = str(datetime.now() - start_time)
        evaluation_logger.log_task_complete(
            "Actualizar Agente ElevenLabs", f"Agente {agent_id} actualizado exitosamente en {execution_time}"
        )

        try:
            from tools.vector_tools import index_jd_interview

            index_jd_interview(updated_jd_data)
            evaluation_logger.log_task_progress(
                "Actualizar Agente ElevenLabs", f"JD Interview re-indexada en knowledge base: {jd_interview_id}"
            )
        except Exception as index_error:
            evaluation_logger.log_error(
                "Actualizar Agente ElevenLabs", f"Error re-indexando JD Interview: {str(index_error)}"
            )

        return {
            "status": "success",
            "message": "Agente de ElevenLabs actualizado correctamente con la JD actualizada",
            "jd_interview_id": jd_interview_id,
            "agent_id": str(agent_id),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error al actualizar agente de ElevenLabs: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("API", error_msg)
        import traceback

        evaluation_logger.log_error("API", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.patch("/update-elevenlabs-agent")
async def update_elevenlabs_agent_endpoint(request: UpdateAgentRequest):
    """
    Endpoint que actualiza SOLO el prompt de un agente de ElevenLabs
    basado en el jd_interview_id (usa la JD actualizada).
    """
    return await run_in_threadpool(_update_elevenlabs_agent_impl, request)


def _create_elevenlabs_agent_impl(request: CreateAgentRequest) -> CreateAgentResponse:
    """Lógica síncrona (Supabase / ElevenLabs / indexación); run_in_threadpool desde el handler async."""
    try:
        jd_interview_id = request.jd_interview_id

        evaluation_logger.log_task_start(
            "Crear Agente ElevenLabs", f"Creando agente para jd_interview_id: {jd_interview_id}"
        )

        # Verificar variables de entorno
        required_env_vars = ["SUPABASE_URL", "SUPABASE_KEY", "ELEVENLABS_API_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            evaluation_logger.log_error("API", f"Variables de entorno faltantes: {missing_vars}")
            raise HTTPException(status_code=500, detail=f"Variables de entorno faltantes: {missing_vars}")

        # Conectar a Supabase
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

        # 1. Obtener datos del jd_interview
        print(f"📊 Obteniendo datos del jd_interview: {jd_interview_id}")
        jd_response = supabase.table("jd_interviews").select("*").eq("id", jd_interview_id).limit(1).execute()

        if not jd_response.data or len(jd_response.data) == 0:
            error_msg = f"No se encontró jd_interview con ID: {jd_interview_id}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        jd_data = jd_response.data[0]
        job_description = jd_data.get("job_description", "")
        interview_name = jd_data.get("interview_name", "")
        client_id = jd_data.get("client_id")

        if not job_description:
            error_msg = f"El jd_interview {jd_interview_id} no tiene job_description"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        if not client_id:
            error_msg = f"El jd_interview {jd_interview_id} no tiene client_id asociado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        tech_stack = extract_tech_stack_from_jd(job_description, interview_name)
        print(f"🧩 Tech stack extraído del JD: {tech_stack}")

        # 2. Obtener email del cliente
        print(f"📧 Obteniendo email del cliente: {client_id}")
        # Acceder a la función subyacente del Tool
        func_to_call = None
        if hasattr(get_client_email, "__wrapped__"):
            func_to_call = get_client_email.__wrapped__
        elif hasattr(get_client_email, "func"):
            func_to_call = get_client_email.func
        elif hasattr(get_client_email, "_func"):
            func_to_call = get_client_email._func
        else:
            error_msg = "No se pudo acceder a la función get_client_email"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        client_email_result = func_to_call(client_id)
        client_email_data = (
            json.loads(client_email_result) if isinstance(client_email_result, str) else client_email_result
        )

        if "error" in client_email_data:
            error_msg = f"Error obteniendo email del cliente: {client_email_data.get('error')}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # Email y nombre real del cliente desde la tabla clients
        sender_email = client_email_data.get("email", "")
        client_name = client_email_data.get("name") or ""
        if not sender_email:
            error_msg = f"El cliente {client_id} no tiene email configurado"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # 3. Crear agente de ElevenLabs
        print("🤖 Creando agente de ElevenLabs...")
        print(f"   - Interview Name: {interview_name}")
        print(f"   - Job Description (original): {job_description[:100]}...")
        print(f"   - Sender Email (cliente): {sender_email}")
        if client_name:
            print(f"   - Client Name (DB): {client_name}")

        # Enriquecer la job_description con el nombre del cliente si no está presente,
        # para que el agente generador de prompt y el agente de voz puedan responder
        # dudas sobre el cliente y usarlo en el nombre del agente.
        job_description_for_agent = job_description
        if client_name and "Cliente:" not in job_description:
            job_description_for_agent = f"Cliente: {client_name} - Descripción del Puesto:\n{job_description}"
            print("   - Job Description enriquecida con nombre de cliente para generación de prompt.")

        # Generar nombre temporal del agente (se actualizará con el generado por CrewAI)
        agent_name_temp = interview_name or f"Agente {jd_interview_id[:8]}"

        elevenlabs_result = create_elevenlabs_agent(
            agent_name=agent_name_temp,
            interview_name=interview_name,
            job_description=job_description_for_agent,
            sender_email=sender_email,
        )

        if not elevenlabs_result:
            error_msg = "No se pudo crear el agente de ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        # 4. Extraer agent_id del resultado
        agent_id_elevenlabs = None
        agent_name_final = agent_name_temp

        if isinstance(elevenlabs_result, dict):
            # Intentar obtener el agent_id de diferentes campos posibles
            agent_id_elevenlabs = (
                elevenlabs_result.get("agent_id")
                or elevenlabs_result.get("id")
                or elevenlabs_result.get("agentId")
                or elevenlabs_result.get("_id")
            )
            # Obtener nombre del agente si está disponible
            agent_name_final = elevenlabs_result.get("name", agent_name_temp)
        elif hasattr(elevenlabs_result, "agent_id"):
            agent_id_elevenlabs = elevenlabs_result.agent_id
        elif hasattr(elevenlabs_result, "id"):
            agent_id_elevenlabs = elevenlabs_result.id

        if not agent_id_elevenlabs:
            error_msg = "No se pudo extraer el agent_id del resultado de ElevenLabs"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        print("✅ Agente creado exitosamente:")
        print(f"   - Agent ID: {agent_id_elevenlabs}")
        print(f"   - Agent Name: {agent_name_final}")

        # 5. Actualizar el registro en jd_interviews con el agent_id y tech_stack extraido
        print("💾 Actualizando jd_interviews con agent_id y tech_stack...")
        update_data = {"agent_id": str(agent_id_elevenlabs), "tech_stack": tech_stack}

        update_response = supabase.table("jd_interviews").update(update_data).eq("id", jd_interview_id).execute()

        if not update_response.data:
            error_msg = f"No se pudo actualizar el registro jd_interview {jd_interview_id}"
            evaluation_logger.log_error("API", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        print("✅ Registro actualizado exitosamente en jd_interviews")

        # Indexar JD Interview actualizada en knowledge base (indexación incremental)
        try:
            from tools.vector_tools import index_jd_interview

            updated_jd = update_response.data[0]
            index_jd_interview(updated_jd)
            evaluation_logger.log_task_progress(
                "Crear Agente ElevenLabs", f"JD Interview re-indexada en knowledge base: {jd_interview_id}"
            )
        except Exception as index_error:
            # No fallar si falla la indexación
            evaluation_logger.log_error(
                "Crear Agente ElevenLabs", f"Error re-indexando JD Interview: {str(index_error)}"
            )

        evaluation_logger.log_task_complete(
            "Crear Agente ElevenLabs", f"Agente creado y guardado exitosamente: {agent_id_elevenlabs}"
        )

        record_elevenlabs_agent_audit_event(
            jd_interview_id=jd_interview_id,
            action="elevenlabs_agent_creation",
            status="success",
            metadata={
                "endpoint": "POST /create-elevenlabs-agent",
                "agent_id": str(agent_id_elevenlabs),
                "agent_name": agent_name_final,
                "interview_name": interview_name,
                "client_id": client_id,
            },
        )

        return CreateAgentResponse(
            status="success",
            message="Agente de ElevenLabs creado y guardado exitosamente",
            timestamp=datetime.now().isoformat(),
            jd_interview_id=jd_interview_id,
            agent_id=str(agent_id_elevenlabs),
            agent_name=agent_name_final,
        )

    except HTTPException as http_error:
        failed_jd_interview_id = getattr(request, "jd_interview_id", "unknown")
        record_elevenlabs_agent_audit_event(
            jd_interview_id=failed_jd_interview_id,
            action="elevenlabs_agent_creation",
            status="failed",
            metadata={
                "endpoint": "POST /create-elevenlabs-agent",
                "status_code": http_error.status_code,
            },
            error_message=str(http_error.detail),
        )
        raise
    except Exception as e:
        failed_jd_interview_id = getattr(request, "jd_interview_id", "unknown")
        record_elevenlabs_agent_audit_event(
            jd_interview_id=failed_jd_interview_id,
            action="elevenlabs_agent_creation",
            status="failed",
            metadata={"endpoint": "POST /create-elevenlabs-agent"},
            error_message=str(e),
        )
        error_msg = f"Error al crear agente de ElevenLabs: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("API", error_msg)
        import traceback

        evaluation_logger.log_error("API", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/create-elevenlabs-agent", response_model=CreateAgentResponse)
async def create_elevenlabs_agent_endpoint(request: CreateAgentRequest):
    """
    Endpoint que crea un agente de ElevenLabs basado en un jd_interview_id
    y actualiza el registro en jd_interviews con el agent_id generado.

    Args:
        request: Objeto con jd_interview_id del registro a procesar

    Returns:
        Respuesta con el estado de la operación y el agent_id creado
    """
    return await run_in_threadpool(_create_elevenlabs_agent_impl, request)


def _chatbot_impl(request: ChatbotRequest) -> ChatbotResponse:
    """Lógica síncrona (Supabase / búsqueda vectorial / OpenAI); run_in_threadpool desde el handler async."""
    try:
        start_time = datetime.now()
        message = request.message
        conversation_history = request.conversation_history or []

        evaluation_logger.log_task_start("Chatbot", f"Procesando mensaje: {message[:50]}...")

        # Verificar variables de entorno
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY no configurada")

        # 1. Verificar si hay chunks en la base de datos
        total_chunks = 0
        try:
            supabase = get_supabase_client()
            count_result = supabase.table("knowledge_chunks").select("id", count="exact").limit(1).execute()
            total_chunks = count_result.count if hasattr(count_result, "count") else 0
            evaluation_logger.log_task_progress("Chatbot", f"Total de chunks en BD: {total_chunks}")
        except Exception as e:
            evaluation_logger.log_error("Chatbot", f"Error contando chunks: {str(e)}")

        # 2. Buscar chunks relevantes usando búsqueda vectorial
        similar_chunks = []
        if total_chunks > 0:
            try:
                # Intentar con diferentes thresholds, empezando por el más permisivo
                thresholds = [0.3, 0.4, 0.5]  # Probar con thresholds más bajos
                for threshold in thresholds:
                    similar_chunks = search_similar_chunks(
                        query_text=message, match_threshold=threshold, match_count=10, entity_type_filter=None
                    )
                    if len(similar_chunks) > 0:
                        evaluation_logger.log_task_progress(
                            "Chatbot", f"Encontrados {len(similar_chunks)} chunks con threshold {threshold}"
                        )
                        break
                    else:
                        evaluation_logger.log_task_progress(
                            "Chatbot", f"No se encontraron chunks con threshold {threshold}, intentando siguiente..."
                        )

                if len(similar_chunks) == 0:
                    evaluation_logger.log_task_progress(
                        "Chatbot", "No se encontraron chunks con ningún threshold, pero hay datos en BD"
                    )
            except Exception as e:
                evaluation_logger.log_error("Chatbot", f"Error en búsqueda vectorial: {str(e)}")
                import traceback

                evaluation_logger.log_error("Chatbot", f"Traceback: {traceback.format_exc()}")
        else:
            evaluation_logger.log_task_progress("Chatbot", "No hay chunks indexados en la base de datos")

        # 3. Construir contexto a partir de los chunks
        context_parts = []
        sources = []
        for chunk in similar_chunks:
            content = chunk.get("content", "")
            entity_type = chunk.get("entity_type", "")
            entity_id = chunk.get("entity_id", "")
            metadata = chunk.get("metadata", {})

            context_parts.append(content)
            sources.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "metadata": metadata,
                    "content_preview": content[:100] + "..." if len(content) > 100 else content,
                }
            )

        context = (
            "\n\n".join(context_parts) if context_parts else "No se encontró información relevante en la base de datos."
        )

        # 4. Construir mensajes para OpenAI
        has_context = len(context_parts) > 0

        if has_context:
            system_prompt = """Eres un asistente experto en el sistema de reclutamiento Agora HR. 
Ayudas a los usuarios con preguntas sobre candidatos, entrevistas, matching, y funcionalidades del sistema.

INSTRUCCIONES:
- Responde en español de manera clara y concisa
- Usa el contexto proporcionado para dar respuestas precisas basadas en los datos reales
- Proporciona información específica de los candidatos, tecnologías, experiencias, etc. cuando esté disponible en el contexto
- Sé profesional y amigable
- Si el contexto menciona IDs o datos técnicos, puedes referenciarlos pero enfócate en la información útil para el usuario"""
        elif total_chunks > 0:
            # Hay chunks pero no se encontraron resultados relevantes
            system_prompt = f"""Eres un asistente experto en el sistema de reclutamiento Agora HR. 
Ayudas a los usuarios con preguntas sobre candidatos, entrevistas, matching, y funcionalidades del sistema.

IMPORTANTE: Hay datos indexados en la base de conocimiento ({total_chunks} chunks), pero la búsqueda no encontró resultados relevantes para esta consulta específica.

INSTRUCCIONES:
- Responde en español de manera clara y concisa
- Explica que hay datos indexados pero que la consulta no encontró coincidencias específicas
- Sugiere reformular la pregunta de manera diferente
- Proporciona información general sobre cómo funciona el sistema
- Sé profesional y amigable"""
        else:
            system_prompt = """Eres un asistente experto en el sistema de reclutamiento Agora HR. 
Ayudas a los usuarios con preguntas sobre candidatos, entrevistas, matching, y funcionalidades del sistema.

IMPORTANTE: Actualmente no hay datos indexados en la base de conocimiento, por lo que no puedo acceder a información específica de candidatos o entrevistas.

INSTRUCCIONES:
- Responde en español de manera clara y concisa
- Explica que los datos aún no están indexados y que necesita ejecutar el script de indexación inicial
- Proporciona información general sobre cómo funciona el sistema
- Sé profesional y amigable
- Sugiere que ejecute el script: python agents/candidate-evaluation/scripts/index_initial_data.py"""

        messages = [{"role": "system", "content": system_prompt}]

        # Agregar historial de conversación
        for msg in conversation_history[-5:]:  # Últimos 5 mensajes
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant"] and content:
                messages.append({"role": role, "content": content})

        # Agregar contexto y pregunta actual
        if context_parts:
            messages.append(
                {
                    "role": "system",
                    "content": f"CONTEXTO RELEVANTE DE LA BASE DE DATOS:\n{context}\n\nUsa esta información para responder la pregunta del usuario de manera específica y detallada.",
                }
            )
        else:
            # Si no hay contexto, agregar información sobre el estado del sistema
            messages.append(
                {
                    "role": "system",
                    "content": "NOTA: No se encontraron datos indexados en la base de conocimiento. Esto significa que aún no se han indexado los candidatos y JD Interviews. Para que el chatbot funcione correctamente, es necesario ejecutar el script de indexación inicial.",
                }
            )

        messages.append({"role": "user", "content": message})

        # 4. Llamar a OpenAI
        from openai import OpenAI

        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, temperature=0.7, max_tokens=500
        )

        bot_response = response.choices[0].message.content

        model_used = response.model

        execution_time = str(datetime.now() - start_time)
        evaluation_logger.log_task_complete("Chatbot", f"Respuesta generada en {execution_time}")

        return ChatbotResponse(
            response=bot_response,
            sources=sources[:3] if sources else [],  # Máximo 3 fuentes
            model=model_used,
            timestamp=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error en chatbot: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("Chatbot", error_msg)
        import traceback

        evaluation_logger.log_error("Chatbot", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/chatbot", response_model=ChatbotResponse)
async def chatbot_endpoint(request: ChatbotRequest):
    """
    Endpoint del chatbot que usa búsqueda vectorial (RAG) para responder preguntas
    sobre candidatos, entrevistas y el sistema.

    Args:
        request: Objeto con el mensaje del usuario y el historial de conversación

    Returns:
        Respuesta del chatbot con contexto relevante de la base de datos
    """
    return await run_in_threadpool(_chatbot_impl, request)


def _get_candidate_info_impl(candidate_id: str, include_related: bool) -> CandidateInfoResponse:
    """Lógica síncrona (Supabase); run_in_threadpool desde el handler async."""
    try:
        start_time = datetime.now()
        evaluation_logger.log_task_start("Get Candidate Info", f"Buscando candidato por ID: {candidate_id}")

        # Limpiar y validar UUID
        cleaned_candidate_id = clean_uuid(candidate_id)

        if not cleaned_candidate_id:
            evaluation_logger.log_task_complete("Get Candidate Info", f"candidate_id inválido: '{candidate_id}'")
            return CandidateInfoResponse(
                status="error",
                message=f"El candidate_id proporcionado ('{candidate_id}') no es un UUID válido",
                timestamp=datetime.now().isoformat(),
            )

        supabase = get_supabase_client()

        # Buscar candidato por ID
        evaluation_logger.log_task_progress("Get Candidate Info", f"Buscando por ID: {cleaned_candidate_id}")
        response = supabase.table("candidates").select("*").eq("id", cleaned_candidate_id).limit(1).execute()

        if not response.data or len(response.data) == 0:
            evaluation_logger.log_task_complete("Get Candidate Info", "No se encontró el candidato")
            return CandidateInfoResponse(
                status="not_found",
                message=f"No se encontró candidato con ID: {cleaned_candidate_id}",
                timestamp=datetime.now().isoformat(),
            )

        candidate_row = response.data[0]

        # Procesar candidato - Respuesta acortada: solo nombre, skills y experiencia
        full_name = candidate_row.get("name", "")

        # Extraer skills (tech_stack)
        tech_stack = candidate_row.get("tech_stack", [])
        skills = tech_stack if isinstance(tech_stack, list) else []

        # Extraer experiencia desde observations
        observations = candidate_row.get("observations", {})
        experience = None
        if isinstance(observations, dict):
            work_experience = observations.get("work_experience")
            if work_experience:
                experience = work_experience
            elif observations.get("other"):
                experience = observations.get("other")

        # Construir respuesta simplificada
        candidate_info = {"name": full_name, "skills": skills, "experience": experience}

        execution_time = str(datetime.now() - start_time)
        evaluation_logger.log_task_complete(
            "Get Candidate Info", f"Información obtenida exitosamente en {execution_time}"
        )

        return CandidateInfoResponse(
            status="success",
            message="Información del candidato obtenida exitosamente",
            timestamp=datetime.now().isoformat(),
            candidate=candidate_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error obteniendo información del candidato: {str(e)}"
        print(f"❌ {error_msg}")
        evaluation_logger.log_error("Get Candidate Info", error_msg)
        import traceback

        evaluation_logger.log_error("Get Candidate Info", f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/get-candidate-info/{candidate_id}", response_model=CandidateInfoResponse)
async def get_candidate_info(candidate_id: str, include_related: bool = True):
    """
    Endpoint para obtener información de candidatos por ID (path parameter).
    Diseñado para ser usado como herramienta por ElevenLabs Agents.

    Args:
        candidate_id: ID único del candidato (UUID) - path parameter
        include_related: Si True, incluye información de meets y evaluaciones relacionadas

    Returns:
        Información del candidato con datos completos
    """
    return await run_in_threadpool(_get_candidate_info_impl, candidate_id, include_related)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
