"""
Motor de matching determinístico (Fase 2): solapamiento de tech_stack candidato vs JD
(tech_stack de la entrevista + palabras del job_description), con alias comunes.
Sin LLM: resultados reproducibles.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from supabase import create_client

def _normalize_token(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().lower()
    s = re.sub(r"[\s_\-]+", "", s)
    s = re.sub(r"[^a-z0-9+#.]", "", s)
    return s


# Grupos de alias: todos los tokens se normalizan al identificador canónico (primera palabra del grupo)
_ALIAS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("react", ("react", "reactjs", "react.js", "reactjs", "reactnative", "react native")),
    ("javascript", ("javascript", "js", "ecmascript", "es6", "es2015")),
    ("typescript", ("typescript", "ts")),
    ("nodejs", ("node", "nodejs", "node.js", "node js")),
    ("python", ("python", "python3", "py")),
    ("java", ("java",)),
    ("kotlin", ("kotlin",)),
    ("swift", ("swift",)),
    ("angular", ("angular", "angularjs", "angular.js")),
    ("vue", ("vue", "vuejs", "vue.js")),
    ("dotnet", (".net", "dotnet", "c#", "csharp", "asp.net")),
    ("php", ("php", "laravel", "symfony")),
    ("ruby", ("ruby", "rails", "ror")),
    ("go", ("golang", "go")),
    ("rust", ("rust",)),
    ("sql", ("sql", "mysql", "postgresql", "postgres", "mssql", "oracle", "sqlite")),
    ("mongodb", ("mongodb", "mongo")),
    ("redis", ("redis",)),
    ("aws", ("aws", "amazon web services", "ec2", "s3", "lambda")),
    ("gcp", ("gcp", "google cloud")),
    ("azure", ("azure", "microsoft azure")),
    ("docker", ("docker", "docker compose", "docker-compose")),
    ("kubernetes", ("kubernetes", "k8s", "k8")),
    ("terraform", ("terraform",)),
    ("git", ("git", "github", "gitlab", "bitbucket")),
    ("graphql", ("graphql",)),
    ("rest", ("rest", "restful", "api rest")),
    ("html", ("html", "html5")),
    ("css", ("css", "css3", "sass", "scss", "less")),
    ("spring", ("spring", "springboot", "spring boot")),
    ("django", ("django",)),
    ("flask", ("flask",)),
    ("fastapi", ("fastapi",)),
    ("nextjs", ("next", "nextjs", "next.js")),
    ("express", ("express", "expressjs")),
    ("jest", ("jest",)),
    ("cypress", ("cypress",)),
    ("selenium", ("selenium",)),
)


def _build_variant_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for canonical, variants in _ALIAS_GROUPS:
        idx[_normalize_token(canonical)] = canonical
        for v in variants:
            idx[_normalize_token(v)] = canonical
    return idx


_VARIANT_TO_CANONICAL = _build_variant_index()


def to_canonical(token: str) -> str:
    n = _normalize_token(token)
    if not n:
        return ""
    return _VARIANT_TO_CANONICAL.get(n, n)


def _candidate_canonicals(tech_stack: Any) -> set[str]:
    out: set[str] = set()
    if not tech_stack:
        return out
    if isinstance(tech_stack, str):
        try:
            parsed = json.loads(tech_stack)
            if isinstance(parsed, list):
                tech_stack = parsed
            else:
                tech_stack = [tech_stack]
        except json.JSONDecodeError:
            tech_stack = [tech_stack]
    if not isinstance(tech_stack, list):
        return out
    for item in tech_stack:
        if not isinstance(item, str):
            continue
        c = to_canonical(item.strip())
        if c:
            out.add(c)
    return out


def _jd_requirement_tokens(tech_stack_field: Any, job_description: str | None) -> set[str]:
    s: set[str] = set()
    ts = tech_stack_field
    if isinstance(ts, str) and ts.strip():
        for part in ts.split(","):
            c = to_canonical(part.strip())
            if c:
                s.add(c)
    desc = job_description or ""
    for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", desc):
        if len(w) < 2:
            continue
        c = to_canonical(w)
        if c:
            s.add(c)
    return s


def _substring_fallback(common: set[str], cand: set[str], jd_text: str) -> set[str]:
    """Si aún no hay intersección, detecta tokens del candidato presentes en el texto del JD."""
    if common or not cand:
        return common
    blob = (jd_text or "").lower()
    extra: set[str] = set()
    for t in cand:
        if len(t) >= 3 and t in blob:
            extra.add(t)
    return extra


def _score_from_overlap(common: set[str], cand: set[str]) -> int:
    if not common:
        return 0
    n = len(common)
    recall = n / max(len(cand), 1)
    base = 28 + n * 12 + int(recall * 35)
    return min(100, max(30, base))


def _fetch_candidates(supabase: Any, user_id: str | None, client_id: str | None) -> list[dict[str, Any]]:
    if user_id and client_id:
        recruiter_response = (
            supabase.table("candidate_recruiters")
            .select("candidate_id")
            .eq("user_id", user_id)
            .eq("client_id", client_id)
            .execute()
        )
        candidate_ids = [row.get("candidate_id") for row in (recruiter_response.data or []) if row.get("candidate_id")]
        if not candidate_ids:
            return []
        cand_resp = supabase.table("candidates").select("*").in_("id", candidate_ids).execute()
        return list(cand_resp.data or [])
    response = supabase.table("candidates").select("*").limit(1000).execute()
    return list(response.data or [])


def _fetch_jd_interviews(supabase: Any, client_id: str | None) -> list[dict[str, Any]]:
    q = supabase.table("jd_interviews").select("*").eq("status", "active")
    if client_id:
        q = q.eq("client_id", client_id)
    response = q.execute()
    return list(response.data or [])


def _fetch_existing_meets_map(supabase: Any) -> dict[str, list[str]]:
    jd_interviews_response = supabase.table("jd_interviews").select("id").eq("status", "active").execute()
    result: dict[str, list[str]] = {}
    for jd_row in jd_interviews_response.data or []:
        jd_interview_id = jd_row.get("id")
        if not jd_interview_id:
            continue
        meets_response = (
            supabase.table("meets")
            .select("candidate_id")
            .eq("jd_interviews_id", jd_interview_id)
            .execute()
        )
        ids: set[str] = set()
        for meet in meets_response.data or []:
            cid = meet.get("candidate_id")
            if cid:
                ids.add(str(cid))
        result[str(jd_interview_id)] = list(ids)
    return result


def _candidate_payload(row: dict[str, Any]) -> dict[str, Any]:
    ts = row.get("tech_stack")
    if isinstance(ts, str):
        try:
            ts = json.loads(ts)
        except json.JSONDecodeError:
            ts = [ts] if ts.strip() else []
    if ts is not None and not isinstance(ts, list):
        ts = []
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "email": row.get("email"),
        "phone": row.get("phone"),
        "cv_url": row.get("cv_url"),
        "tech_stack": ts,
        "observations": row.get("observations"),
    }


def _jd_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "interview_name": row.get("interview_name"),
        "agent_id": row.get("agent_id"),
        "job_description": row.get("job_description") or "",
        "tech_stack": row.get("tech_stack"),
        "client_id": row.get("client_id"),
        "created_at": row.get("created_at"),
    }


def run_deterministic_matching(
    user_id: str | None = None,
    client_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Devuelve la lista `matches` en el formato esperado por el backoffice / API:
    [{ "candidate": {...}, "matching_interviews": [ { jd_interviews, compatibility_score, match_analysis, observations_match } ] }, ...]
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no configurados")

    supabase = create_client(url, key)
    candidates_rows = _fetch_candidates(supabase, user_id, client_id)
    jd_rows = _fetch_jd_interviews(supabase, client_id)
    existing = _fetch_existing_meets_map(supabase)

    # candidato_id -> lista de entradas matching_interviews
    from collections import defaultdict

    interviews_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for crow in candidates_rows:
        cid = str(crow.get("id") or "")
        if not cid:
            continue
        cand_tokens = _candidate_canonicals(crow.get("tech_stack"))
        if not cand_tokens:
            continue

        for jd_row in jd_rows:
            jd_id = str(jd_row.get("id") or "")
            if not jd_id:
                continue
            if cid in existing.get(jd_id, []):
                continue

            jd_text = jd_row.get("job_description") or ""
            jd_req = _jd_requirement_tokens(jd_row.get("tech_stack"), jd_text)
            common = cand_tokens & jd_req
            common = _substring_fallback(common, cand_tokens, jd_text)

            score = _score_from_overlap(common, cand_tokens)
            if score <= 0:
                continue

            labels = ", ".join(sorted(common)) if common else "coincidencia por texto/JD"
            analysis = (
                f"Match determinístico: tecnologías alineadas ({labels}). "
            )

            interviews_by_candidate[cid].append(
                {
                    "jd_interviews": _jd_payload(jd_row),
                    "compatibility_score": score,
                    "match_analysis": analysis,
                    "observations_match": None,
                }
            )

    matches: list[dict[str, Any]] = []
    for crow in candidates_rows:
        cid = str(crow.get("id") or "")
        if cid not in interviews_by_candidate:
            continue
        items = interviews_by_candidate[cid]
        items.sort(key=lambda x: -int(x.get("compatibility_score") or 0))
        matches.append(
            {
                "candidate": _candidate_payload(crow),
                "matching_interviews": items,
            }
        )

    return matches
