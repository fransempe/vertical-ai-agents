import tiktoken
import json

# 💰 Precios por millón de tokens (USD)
MODEL_PRICES = {
    "gpt-5-nano":    {"input": 0.050, "output": 0.400},
    "gpt-4o":        {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15,  "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50,  "output": 1.50},  # Estimación – verificar futura actualización
}

# 🧮 Estima tokens para una lista de mensajes (Chat API) - INPUT TOKENS
def estimate_task_tokens(messages: list[dict], model: str = "gpt-4o-mini") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")  # fallback universal
    total = 0
    for msg in messages:
        text = f"{msg.get('role', '')}: {msg.get('content', '')}"
        total += len(enc.encode(text))
    return total

# 🔍 Desglosa tokens por componente del contexto
def breakdown_context_tokens(meet_data: dict, model: str = "gpt-4o-mini") -> dict:
    """
    Desglosa los tokens del contexto por componente:
    - conversation_data
    - job_description
    - tech_stack
    - resto del JSON (estructura, metadatos)
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    
    breakdown = {
        "conversation_data": 0,
        "job_description": 0,
        "tech_stack": 0,
        "resto_json": 0,
        "total_context": 0
    }
    
    if not meet_data:
        return breakdown
    
    # 1. Conversation data
    conversation = meet_data.get("conversation", {})
    conversation_data = conversation.get("conversation_data", [])
    if conversation_data:
        conversation_str = json.dumps(conversation_data, indent=2, ensure_ascii=False)
        breakdown["conversation_data"] = len(enc.encode(conversation_str))
    
    # 2. Job description
    jd_interview = meet_data.get("jd_interview", {})
    job_description = jd_interview.get("job_description", "")
    if job_description:
        breakdown["job_description"] = len(enc.encode(job_description))
    
    # 3. Tech stack
    candidate = conversation.get("candidate", {})
    tech_stack = candidate.get("tech_stack", [])
    if tech_stack:
        tech_stack_str = json.dumps(tech_stack, ensure_ascii=False)
        breakdown["tech_stack"] = len(enc.encode(tech_stack_str))
    
    # 4. Resto del JSON (estructura, metadatos, otros campos)
    # Calcular el total del JSON completo y restar los componentes ya calculados
    full_json_str = json.dumps(meet_data, indent=2, ensure_ascii=False)
    total_tokens = len(enc.encode(full_json_str))
    
    # Calcular tokens de los componentes principales
    components_tokens = (
        breakdown["conversation_data"] +
        breakdown["job_description"] +
        breakdown["tech_stack"]
    )
    
    # El resto son metadatos, estructura JSON, y otros campos
    breakdown["resto_json"] = max(0, total_tokens - components_tokens)
    breakdown["total_context"] = total_tokens
    
    return breakdown

# 🧮 Estima tokens de completion basado en expected_output o texto de ejemplo
def estimate_completion_tokens(expected_output: str = None, model: str = "gpt-4o-mini") -> int:
    """
    Estima tokens de completion basado en el expected_output o un estimado razonable.
    Si no se proporciona expected_output, usa un estimado basado en tareas de evaluación típicas.
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")  # fallback universal
    
    if expected_output:
        # Si hay expected_output, estimar basado en eso
        return len(enc.encode(expected_output))
    else:
        # Estimado razonable para una evaluación completa de meet (basado en logs reales: ~5,000 tokens)
        # Incluye análisis de habilidades blandas, técnicas, comparación con JD, y determinación de match
        estimated_text = """
        {
          "meet_id": "...",
          "candidate": {...},
          "jd_interview": {...},
          "conversation_analysis": {
            "soft_skills": {
              "communication": "análisis detallado...",
              "leadership": "análisis detallado...",
              "teamwork": "análisis detallado...",
              "adaptability": "análisis detallado...",
              "problem_solving": "análisis detallado...",
              "time_management": "análisis detallado...",
              "emotional_intelligence": "análisis detallado...",
              "continuous_learning": "análisis detallado..."
            },
            "technical_assessment": {
              "knowledge_level": "...",
              "practical_experience": "...",
              "technical_questions": [...],
              "completeness_summary": {...},
              "alerts": [...]
            }
          },
          "jd_analysis": {...},
          "match_evaluation": {
            "is_potential_match": true/false,
            "compatibility_score": 0-100,
            "technical_match": {...},
            "soft_skills_match": "análisis comparativo extenso...",
            "experience_match": "análisis comparativo extenso...",
            "strengths": [...],
            "concerns": [...],
            "final_recommendation": "...",
            "justification": "justificación detallada y extensa de la decisión..."
          }
        }
        """
        return len(enc.encode(estimated_text))

# 💰 Calcula costo aproximado separando input y output
def estimate_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o-mini") -> dict:
    """
    Calcula el costo separando input y output tokens.
    
    Returns:
        dict con 'input_cost', 'output_cost', 'total_cost', 'total_tokens'
    """
    p = MODEL_PRICES.get(model, {"input": 1, "output": 1})
    input_cost = (input_tokens / 1_000_000) * p["input"]
    output_cost = (output_tokens / 1_000_000) * p["output"]
    total_cost = input_cost + output_cost
    total_tokens = input_tokens + output_tokens
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "total_tokens": total_tokens
    }

# 🔍 Valida y loguea en CrewAI (usa tu evaluation_logger)
def log_token_estimation(logger, messages: list[dict], model: str = "gpt-4o-mini", task_name: str = "LLM Task", expected_output: str = None):
    input_tokens = estimate_task_tokens(messages, model)
    completion_tokens = estimate_completion_tokens(expected_output, model)
    cost_breakdown = estimate_cost(input_tokens, completion_tokens, model)
    
    total_tokens = cost_breakdown['total_tokens']
    total_cost = cost_breakdown['total_cost']
    
    if input_tokens > 10000:
        logger.log_task_warning(
            task_name, 
            f"⚠️ Prompt muy grande: {input_tokens:,} input tokens (~${cost_breakdown['input_cost']:.4f} USD). Considera resumir el input."
        )
    else:
        logger.log_task_progress(
            task_name, 
            f"🧮 Estimación: {total_tokens:,} tokens totales "
            f"({input_tokens:,} input + {completion_tokens:,} completion) | "
            f"Costo aprox: ${total_cost:.4f} USD | Modelo: {model}"
        )
    
    return {
        "input_tokens": input_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": total_cost,
        "cost_breakdown": cost_breakdown
    }
