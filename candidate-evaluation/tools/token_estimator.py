import tiktoken
import json

# 💰 Precios por millón de tokens (USD)
MODEL_PRICES = {
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

# 🧮 Estima tokens para una lista de mensajes (Chat API)
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

# 💰 Calcula costo aproximado
def estimate_cost(tokens: int, model: str = "gpt-4o-mini") -> float:
    p = MODEL_PRICES.get(model, {"input": 1, "output": 1})
    avg_price = (p["input"] + p["output"]) / 2
    return (tokens / 1_000_000) * avg_price

# 🔍 Valida y loguea en CrewAI (usa tu evaluation_logger)
def log_token_estimation(logger, messages: list[dict], model: str = "gpt-4o-mini", task_name: str = "LLM Task"):
    tokens = estimate_task_tokens(messages, model)
    cost = estimate_cost(tokens, model)
    
    if tokens > 10000:
        logger.log_task_warning(task_name, f"⚠️ Prompt muy grande: {tokens} tokens (~${cost:.4f} USD). Considera resumir el input.")
    else:
        logger.log_task_progress(task_name, f"🧮 Estimación de tokens: {tokens} | Costo aprox: ${cost:.4f} | Modelo: {model}")
    
    return {"tokens": tokens, "estimated_cost_usd": cost}
