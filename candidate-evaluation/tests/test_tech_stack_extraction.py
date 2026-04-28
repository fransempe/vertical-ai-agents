from utils.tech_stack import extract_tech_stack_from_jd


def test_extract_tech_stack_from_jd_detects_examples_and_aliases():
    tech_stack = extract_tech_stack_from_jd(
        """
        Buscamos perfil con experiencia en SAP, manejo avanzado de Microsoft Excel,
        soporte de redes LAN y desarrollo frontend con Next.js.
        """,
        "Frontend NextJS",
    )

    assert tech_stack == ["NextJS", "SAP", "Excel", "LAN"]


def test_extract_tech_stack_from_jd_deduplicates_preserving_first_appearance():
    tech_stack = extract_tech_stack_from_jd(
        "React, ReactJS y react.js con Node.js, SQL Server y SQL.",
    )

    assert tech_stack == ["React", "NodeJS", "SQL", "SQL Server"]
