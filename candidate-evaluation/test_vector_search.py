#!/usr/bin/env python3
"""
Script de prueba para las funciones de búsqueda vectorial
Ejecutar: python test_vector_search.py
"""

import os
import sys

from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(__file__))

from tools.vector_tools import (
    delete_knowledge_chunks,
    generate_embedding,
    get_supabase_client,
    index_all_candidates,
    index_all_jd_interviews,
    index_candidate,
    index_jd_interview,
    insert_knowledge_chunk,
    search_similar_chunks,
)

load_dotenv()


def test_generate_embedding():
    """Prueba la generación de embeddings"""
    print("\n" + "=" * 60)
    print("TEST 1: Generar Embedding")
    print("=" * 60)

    try:
        text = "Candidato con React y TypeScript"
        embedding = generate_embedding(text)
        print("✅ Embedding generado exitosamente")
        print(f"   Texto: {text}")
        print(f"   Dimensiones: {len(embedding)}")
        print(f"   Primeros 5 valores: {embedding[:5]}")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_insert_chunk():
    """Prueba la inserción de un chunk"""
    print("\n" + "=" * 60)
    print("TEST 2: Insertar Knowledge Chunk")
    print("=" * 60)

    try:
        content = "Candidato de prueba: Juan Pérez con React y TypeScript"
        embedding = generate_embedding(content)

        chunk_id = insert_knowledge_chunk(
            content=content,
            embedding=embedding,
            entity_type="candidate",
            entity_id="test-candidate-123",
            metadata={"tech_stack": ["React", "TypeScript"], "test": True},
        )

        print("✅ Chunk insertado exitosamente")
        print(f"   Chunk ID: {chunk_id}")
        print(f"   Content: {content[:50]}...")
        return chunk_id
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


def test_search_similar():
    """Prueba la búsqueda de chunks similares"""
    print("\n" + "=" * 60)
    print("TEST 3: Buscar Chunks Similares")
    print("=" * 60)

    try:
        query = "¿Qué candidatos tienen React?"
        results = search_similar_chunks(
            query_text=query,
            match_threshold=0.5,  # Threshold más bajo para testing
            match_count=5,
            entity_type_filter="candidate",
        )

        print("✅ Búsqueda completada")
        print(f"   Query: {query}")
        print(f"   Resultados encontrados: {len(results)}")

        for i, result in enumerate(results[:3], 1):
            print(f"\n   Resultado {i}:")
            print(f"   - Similitud: {result.get('similarity', 0):.3f}")
            print(f"   - Tipo: {result.get('entity_type')}")
            print(f"   - Contenido: {result.get('content', '')[:100]}...")

        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_index_single_candidate():
    """Prueba indexar un candidato individual"""
    print("\n" + "=" * 60)
    print("TEST 4: Indexar Candidato Individual")
    print("=" * 60)

    try:
        # Obtener un candidato de prueba directamente de Supabase
        supabase = get_supabase_client()
        response = supabase.table("candidates").select("*").limit(1).execute()

        candidates = []
        for row in response.data:
            candidate = {
                "id": row.get("id"),
                "name": row.get("name"),
                "email": row.get("email"),
                "phone": row.get("phone"),
                "cv_url": row.get("cv_url"),
                "tech_stack": row.get("tech_stack"),
                "observations": row.get("observations"),
                "created_at": row.get("created_at"),
            }
            candidates.append(candidate)

        if not candidates or len(candidates) == 0:
            print("⚠️  No hay candidatos en la BD para indexar")
            return False

        candidate = candidates[0]
        print(f"   Indexando candidato: {candidate.get('name', 'Unknown')}")

        chunk_id = index_candidate(candidate)

        print("✅ Candidato indexado exitosamente")
        print(f"   Chunk ID: {chunk_id}")
        print(f"   Candidato: {candidate.get('name')} ({candidate.get('email')})")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_index_single_jd():
    """Prueba indexar una JD Interview individual"""
    print("\n" + "=" * 60)
    print("TEST 5: Indexar JD Interview Individual")
    print("=" * 60)

    try:
        # Obtener una JD Interview de prueba directamente de Supabase
        supabase = get_supabase_client()
        response = supabase.table("jd_interviews").select("*").eq("status", "active").limit(1).execute()

        jd_interviews = []
        for row in response.data:
            interview = {
                "id": row.get("id"),
                "interview_name": row.get("interview_name"),
                "agent_id": row.get("agent_id"),
                "job_description": row.get("job_description"),
                "tech_stack": row.get("tech_stack"),
                "client_id": row.get("client_id"),
                "status": row.get("status"),
                "created_at": row.get("created_at"),
            }
            jd_interviews.append(interview)

        if not jd_interviews or len(jd_interviews) == 0:
            print("⚠️  No hay JD Interviews en la BD para indexar")
            return False

        jd_interview = jd_interviews[0]
        print(f"   Indexando JD: {jd_interview.get('interview_name', 'Unknown')}")

        chunk_id = index_jd_interview(jd_interview)

        print("✅ JD Interview indexada exitosamente")
        print(f"   Chunk ID: {chunk_id}")
        print(f"   JD: {jd_interview.get('interview_name')}")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_index_all_candidates():
    """Prueba indexar todos los candidatos (limitado)"""
    print("\n" + "=" * 60)
    print("TEST 6: Indexar Todos los Candidatos (limitado a 5)")
    print("=" * 60)

    try:
        count = index_all_candidates(limit=5)
        print("✅ Indexación completada")
        print(f"   Candidatos indexados: {count}")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_index_all_jds():
    """Prueba indexar todas las JD Interviews"""
    print("\n" + "=" * 60)
    print("TEST 7: Indexar Todas las JD Interviews")
    print("=" * 60)

    try:
        count = index_all_jd_interviews()
        print("✅ Indexación completada")
        print(f"   JD Interviews indexadas: {count}")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_search_after_indexing():
    """Prueba búsqueda después de indexar"""
    print("\n" + "=" * 60)
    print("TEST 8: Búsqueda Después de Indexar")
    print("=" * 60)

    try:
        queries = [
            "¿Qué candidatos tienen React?",
            "¿Qué búsquedas hay para desarrolladores frontend?",
            "Candidatos con TypeScript y Node.js",
        ]

        for query in queries:
            print(f"\n   Query: {query}")
            results = search_similar_chunks(query_text=query, match_threshold=0.6, match_count=3)

            print(f"   Resultados: {len(results)}")
            for i, result in enumerate(results[:2], 1):
                print(f"   {i}. [{result.get('similarity', 0):.3f}] {result.get('content', '')[:80]}...")

        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def cleanup_test_data():
    """Limpia datos de prueba"""
    print("\n" + "=" * 60)
    print("CLEANUP: Eliminando datos de prueba")
    print("=" * 60)

    try:
        deleted = delete_knowledge_chunks("test-candidate-123", "candidate")
        print(f"✅ Datos de prueba eliminados: {deleted} chunks")
        return True
    except Exception as e:
        print(f"⚠️  Error en cleanup: {str(e)}")
        return False


def main():
    """Ejecuta todos los tests"""
    print("\n" + "=" * 60)
    print("SCRIPT DE PRUEBA: Búsqueda Vectorial con pgvector")
    print("=" * 60)
    print("\nEste script prueba las funciones de embeddings y búsqueda vectorial.")
    print("Asegúrate de haber ejecutado setup-pgvector.sql en Supabase primero.\n")

    results = {}

    # Test 1: Generar embedding
    results["generate_embedding"] = test_generate_embedding()

    # Test 2: Insertar chunk
    test_chunk_id = test_insert_chunk()
    results["insert_chunk"] = test_chunk_id is not None

    # Test 3: Buscar chunks similares
    results["search_similar"] = test_search_similar()

    # Test 4: Indexar candidato individual
    results["index_candidate"] = test_index_single_candidate()

    # Test 5: Indexar JD individual
    results["index_jd"] = test_index_single_jd()

    # Test 6: Indexar todos los candidatos (limitado)
    print("\n⚠️  Este test indexará hasta 5 candidatos. ¿Continuar? (s/n): ", end="")
    response = input().strip().lower()
    if response == "s":
        results["index_all_candidates"] = test_index_all_candidates()
    else:
        print("   Test omitido")
        results["index_all_candidates"] = None

    # Test 7: Indexar todas las JDs
    print("\n⚠️  Este test indexará todas las JD Interviews. ¿Continuar? (s/n): ", end="")
    response = input().strip().lower()
    if response == "s":
        results["index_all_jds"] = test_index_all_jds()
    else:
        print("   Test omitido")
        results["index_all_jds"] = None

    # Test 8: Búsqueda después de indexar
    results["search_after_indexing"] = test_search_after_indexing()

    # Cleanup
    if test_chunk_id:
        cleanup_test_data()

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE TESTS")
    print("=" * 60)
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL" if result is False else "⏭️  SKIP"
        print(f"{status}: {test_name}")

    passed = sum(1 for r in results.values() if r is True)
    total = sum(1 for r in results.values() if r is not None)

    print(f"\nResultado: {passed}/{total} tests pasados")

    if passed == total:
        print("\n🎉 ¡Todos los tests pasaron! El sistema de búsqueda vectorial está funcionando correctamente.")
    else:
        print("\n⚠️  Algunos tests fallaron. Revisa los errores arriba.")


if __name__ == "__main__":
    main()
