#!/usr/bin/env python3
"""
Script de prueba para la API de análisis de candidatos
"""

import requests
import json

def test_api():
    """Prueba simple de la API"""
    base_url = "http://localhost:8000"
    
    print("🧪 Probando API de Análisis de Candidatos")
    print("="*50)
    
    # Test 1: Status endpoint
    try:
        print("\n1. Probando endpoint /status...")
        response = requests.get(f"{base_url}/status")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error conectando al servidor: {e}")
        return
    
    # Test 2: Analysis endpoint (solo mostrar cómo llamarlo)
    print("\n2. Endpoint /analyze disponible")
    print("Para disparar el análisis completo:")
    print("POST http://localhost:8000/analyze")
    print("Ejemplo con curl:")
    print('curl -X POST "http://localhost:8000/analyze"')
    print("\n⚠️  NOTA: Este proceso puede tomar varios minutos")

if __name__ == "__main__":
    test_api()