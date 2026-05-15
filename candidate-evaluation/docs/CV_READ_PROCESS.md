# Procedimiento de lectura de CV

Este documento describe el flujo de `POST /read-cv`, la extraccion del CV y la carga/enriquecimiento del candidato.

## Flujo actual

1. `api.py` recibe `filename`, `user_id` y `client_id` en `POST /read-cv`.
2. Valida variables de entorno minimas: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `OPENAI_API_KEY`.
3. Crea el crew especializado con `create_cv_analysis_crew(filename, user_id, client_id)`.
4. El agente `CV Analysis Specialist` descarga el archivo desde S3 con `download_cv_from_s3`.
5. La key de S3 se resuelve bajo el prefijo `cvs/` si el nombre no lo incluye.
6. La herramienta detecta el formato por extension: `pdf`, `docx` o `doc`.
7. Para PDF intenta extraer texto con este orden:
   - `pdfplumber`
   - `PyPDF2`
   - `pdfminer.six`
   - AWS Textract OCR
8. Si el documento es escaneado o imagen, Textract funciona como fallback OCR. El modo actual es sincronico y queda limitado a 5 MB.
9. Con el texto extraido, el agente llama `extract_candidate_data` para obtener hints deterministas: emails, telefonos, LinkedIn, tecnologias, rol y perfil sugerido.
10. El agente arma el candidato final y el JSON de `observations`, incluyendo experiencia laboral, rubros, idiomas, educacion/formacion, certificaciones, cursos, rol/perfil y datos adicionales.
11. El agente llama `create_candidate`.
12. `create_candidate` normaliza `tech_stack` y parsea `observations`.
13. Si el email no existe, inserta el registro y devuelve `action: "created"`.
14. Si el email ya existe, actualiza/enriquece el registro existente y devuelve `action: "updated"`.
15. Si se reciben `user_id` y `client_id`, intenta crear la relacion en `candidate_recruiters`.
16. El candidato creado o actualizado se indexa en la knowledge base con `index_candidate`.
17. `api.py` interpreta el resultado y responde `candidate_status` como `created`, `updated`, `exists` o `failed`.

## Semantica de creado/actualizado

`create_candidate` ya no corta el flujo con `AlreadyExists` cuando encuentra un email existente. En su lugar:

- Devuelve `success: true`, `action: "created"` y `candidate_created: true` si inserta un candidato nuevo.
- Devuelve `success: true`, `action: "updated"`, `candidate_created: false` y `candidate_updated: true/false` si encontro un candidato existente.
- Mantiene `AlreadyExists` como compatibilidad de lectura en `api.py` si algun resultado legacy lo devuelve.

La actualizacion es conservadora:

- Completa `name`, `phone` y `linkedin` solo si el registro existente no tenia valor.
- Actualiza `cv_url` con el CV procesado.
- Fusiona `tech_stack` sin duplicados.
- Fusiona `observations`, combinando listas y preservando informacion existente cuando el nuevo valor viene vacio.

## Mejoras recomendadas para OCR y enriquecimiento

- Agregar diagnostico previo del archivo: paginas, tamanio, PDF encriptado, presencia de capa de texto y ratio de texto por pagina.
- Para PDFs grandes o multipagina escaneados, usar Textract asincronico con S3 (`StartDocumentTextDetection`) en lugar de `DetectDocumentText`.
- Guardar `raw_text_by_page`, metodo usado por pagina, errores y warnings de extraccion.
- Validar el resultado estructurado con Pydantic antes de crear/actualizar el candidato.
- Ampliar `observations` con `projects`, `seniority_estimate`, `total_experience_months`, `current_position`, `current_company`, `location`, `availability`, `portfolio_url`, `github_url`, `personal_website`, `source_language` y `extraction_confidence`.
- Normalizar tecnologias contra un catalogo de aliases y guardar evidencia de aparicion.

## Tests y cobertura

Los tests unitarios principales estan en:

- `tests/test_api_read_cv.py`: estados de `POST /read-cv`, incluyendo `created`, `updated`, legacy `AlreadyExists`, errores de entorno y fallos del crew.
- `tests/test_cv_tools.py`: descarga S3 mockeada, extraccion PDF/DOCX/DOC, fallback OCR y heuristicas de hints.
- `tests/test_supabase_tools.py`: insercion de candidatos, actualizacion por email existente, merge de `tech_stack`/`observations`, relacion `candidate_recruiters` e indexacion tolerante a fallos.

Comandos recomendados desde `candidate-evaluation`:

```bash
pytest tests/test_api_read_cv.py tests/test_cv_tools.py tests/test_supabase_tools.py
pytest tests/test_api_read_cv.py tests/test_cv_tools.py tests/test_supabase_tools.py --cov=. --cov-report=term-missing
```
