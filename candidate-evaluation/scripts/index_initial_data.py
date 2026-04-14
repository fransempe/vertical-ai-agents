#!/usr/bin/env python3
"""
Script para indexar datos iniciales en la knowledge base
Ejecutar: python scripts/index_initial_data.py
"""

import os
import sys

from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tools.vector_tools import (
    get_supabase_client,
    index_all_candidate_jd_status,
    index_all_candidates,
    index_all_jd_interviews,
    index_all_meet_evaluations,
    index_all_meets,
)

load_dotenv()


def index_initial_data():
    """Indexa todos los datos iniciales"""
    print("\n" + "=" * 60)
    print("INDEXACIÓN INICIAL DE DATOS")
    print("=" * 60)

    try:
        # Verificar conexión
        _ = get_supabase_client()
        print("✅ Conexión a Supabase establecida")

        # Indexar candidatos
        print("\n📋 Indexando candidatos...")
        candidates_count = index_all_candidates()
        print(f"✅ {candidates_count} candidatos indexados")

        # Indexar JD Interviews
        print("\n📋 Indexando JD Interviews...")
        jd_count = index_all_jd_interviews()
        print(f"✅ {jd_count} JD Interviews indexadas")

        # Indexar meets
        print("\n📋 Indexando meets...")
        meets_count = index_all_meets()
        print(f"✅ {meets_count} meets indexados")

        # Indexar evaluaciones de meets
        print("\n📋 Indexando evaluaciones de meets...")
        meet_evals_count = index_all_meet_evaluations()
        print(f"✅ {meet_evals_count} meet_evaluations indexadas")

        # Indexar candidate_jd_status
        print("\n📋 Indexando candidate_jd_status...")
        candidate_jd_count = index_all_candidate_jd_status()
        print(f"✅ {candidate_jd_count} candidate_jd_status indexados")

        # Resumen
        print("\n" + "=" * 60)
        print("RESUMEN")
        print("=" * 60)
        print(f"✅ Candidatos indexados: {candidates_count}")
        print(f"✅ JD Interviews indexadas: {jd_count}")
        print(f"✅ Meets indexados: {meets_count}")
        print(f"✅ Evaluaciones de meets indexadas: {meet_evals_count}")
        print(f"✅ Candidate JD Status indexados: {candidate_jd_count}")
        print(
            f"✅ Total de chunks creados: {candidates_count + jd_count + meets_count + meet_evals_count + candidate_jd_count}"
        )
        print("\n🎉 Indexación inicial completada exitosamente!")

        return {
            "candidates": candidates_count,
            "jd_interviews": jd_count,
            "meets": meets_count,
            "meet_evaluations": meet_evals_count,
            "candidate_jd_status": candidate_jd_count,
            "total": candidates_count + jd_count + meets_count + meet_evals_count + candidate_jd_count,
        }

    except Exception as e:
        print(f"\n❌ Error durante la indexación: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("\n⚠️  Este script indexará TODOS los candidatos, JD Interviews, meets y evaluaciones de meets.")
    print("¿Deseas continuar? (s/n): ", end="")
    response = input().strip().lower()

    if response == "s":
        index_initial_data()
    else:
        print("Indexación cancelada.")
