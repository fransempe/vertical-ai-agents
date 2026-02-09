"""
Helper functions for common operations
"""
from uuid import UUID
from typing import Optional


def is_valid_uuid(value: str | None) -> bool:
    """
    Valida si un valor es un UUID válido.
    
    Args:
        value: Valor a validar (puede ser string, bytes o None)
        
    Returns:
        True si es un UUID válido, False en caso contrario
    """
    if not value or not isinstance(value, (str, bytes)):
        return False
    try:
        UUID(str(value))
        return True
    except Exception:
        return False


def clean_uuid(value: str | None) -> Optional[str]:
    """
    Limpia un UUID removiendo comillas dobles, espacios y caracteres inválidos.
    Retorna None si no es un UUID válido después de limpiar.
    
    Args:
        value: UUID a limpiar (puede venir con comillas o espacios)
        
    Returns:
        UUID limpio y validado, o None si no es válido
    """
    if not value:
        return None
    
    # Convertir a string y limpiar
    cleaned = str(value).strip()
    
    # Remover comillas dobles al inicio y final
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]
    # Remover comillas simples al inicio y final
    if cleaned.startswith("'") and cleaned.endswith("'"):
        cleaned = cleaned[1:-1]
    
    # Remover espacios
    cleaned = cleaned.strip()
    
    # Validar que sea un UUID válido
    if is_valid_uuid(cleaned):
        return cleaned
    
    return None
