#!/usr/bin/env python3
"""
Módulo para estimación de tokens cuando no están disponibles en el resultado
"""


def rough_token_estimate(text: str) -> int:
    """
    Estima tokens basándose en la longitud del texto.
    ~4 caracteres por token en inglés; en español puede variar.
    Úsalo como aproximación conservadora.
    
    Args:
        text: Texto a estimar
        
    Returns:
        Número estimado de tokens
    """
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def estimate_from_messages(messages: list[dict]) -> dict:
    """
    Estima tokens desde una lista de mensajes (formato de conversación)
    
    Args:
        messages: Lista de diccionarios con mensajes (debe tener 'content' o 'message')
        
    Returns:
        Diccionario con prompt_tokens, completion_tokens y total_tokens estimados
    """
    total = 0
    for m in messages:
        total += rough_token_estimate(m.get("content") or m.get("message") or "")
    return {
        "prompt_tokens": total,
        "completion_tokens": 0,
        "total_tokens": total
    }


def estimate_from_result(result: any) -> dict:
    """
    Intenta estimar tokens desde el resultado del crew.
    Busca en diferentes atributos del resultado.
    
    Args:
        result: Resultado del crew.kickoff()
        
    Returns:
        Diccionario con tokens estimados o None si no se puede estimar
    """
    estimated = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }
    
    # Intentar obtener texto del resultado
    text_to_estimate = ""
    
    # Buscar en diferentes atributos
    if hasattr(result, 'raw') and result.raw:
        text_to_estimate = str(result.raw)
    elif hasattr(result, 'content') and result.content:
        text_to_estimate = str(result.content)
    elif hasattr(result, '__str__'):
        text_to_estimate = str(result)
    
    if text_to_estimate:
        estimated["total_tokens"] = rough_token_estimate(text_to_estimate)
        # Asumir que la mayoría son prompt tokens (conservador)
        estimated["prompt_tokens"] = int(estimated["total_tokens"] * 0.8)
        estimated["completion_tokens"] = int(estimated["total_tokens"] * 0.2)
        return estimated
    
    return None

