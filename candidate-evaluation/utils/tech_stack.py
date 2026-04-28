"""Utilities to extract JD technology keywords deterministically."""

from __future__ import annotations

import re
import unicodedata

_KEYWORD_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Python", ("python", "python3")),
    ("JavaScript", ("javascript", "js", "ecmascript")),
    ("TypeScript", ("typescript", "ts")),
    ("Java", ("java",)),
    ("Kotlin", ("kotlin",)),
    ("Swift", ("swift",)),
    ("Objective-C", ("objective-c", "objective c")),
    ("C", ("c",)),
    ("C++", ("c++", "cpp")),
    ("C#", ("c#", "csharp")),
    (".NET", (".net", "dotnet", "asp.net")),
    ("Go", ("golang", "go")),
    ("Rust", ("rust",)),
    ("PHP", ("php",)),
    ("Ruby", ("ruby",)),
    ("Scala", ("scala",)),
    ("R", ("r",)),
    ("SQL", ("sql",)),
    ("NoSQL", ("nosql",)),
    ("HTML", ("html", "html5")),
    ("CSS", ("css", "css3")),
    ("Sass", ("sass", "scss")),
    ("React", ("react", "reactjs", "react.js")),
    ("React Native", ("react native", "reactnative")),
    ("NextJS", ("nextjs", "next.js", "next js")),
    ("Angular", ("angular", "angularjs")),
    ("Vue", ("vue", "vuejs", "vue.js")),
    ("Nuxt", ("nuxt", "nuxtjs", "nuxt.js")),
    ("Svelte", ("svelte",)),
    ("NodeJS", ("nodejs", "node.js", "node js")),
    ("Express", ("express", "expressjs")),
    ("NestJS", ("nestjs", "nest.js", "nest js")),
    ("Django", ("django",)),
    ("Flask", ("flask",)),
    ("FastAPI", ("fastapi",)),
    ("Spring", ("spring", "spring boot", "springboot")),
    ("Laravel", ("laravel",)),
    ("Rails", ("rails", "ruby on rails")),
    ("GraphQL", ("graphql",)),
    ("REST", ("rest", "restful", "api rest")),
    ("PostgreSQL", ("postgresql", "postgres")),
    ("MySQL", ("mysql",)),
    ("SQL Server", ("sql server", "mssql", "ms sql")),
    ("Oracle", ("oracle", "oracle db")),
    ("SQLite", ("sqlite",)),
    ("MongoDB", ("mongodb", "mongo")),
    ("Redis", ("redis",)),
    ("Elasticsearch", ("elasticsearch", "elastic search")),
    ("DynamoDB", ("dynamodb", "dynamo db")),
    ("Firebase", ("firebase",)),
    ("Supabase", ("supabase",)),
    ("AWS", ("aws", "amazon web services")),
    ("Azure", ("azure", "microsoft azure")),
    ("GCP", ("gcp", "google cloud", "google cloud platform")),
    ("Docker", ("docker",)),
    ("Kubernetes", ("kubernetes", "k8s")),
    ("Terraform", ("terraform",)),
    ("Ansible", ("ansible",)),
    ("Jenkins", ("jenkins",)),
    ("GitHub Actions", ("github actions",)),
    ("GitLab CI", ("gitlab ci", "gitlab-ci")),
    ("CircleCI", ("circleci", "circle ci")),
    ("Git", ("git",)),
    ("GitHub", ("github",)),
    ("GitLab", ("gitlab",)),
    ("Bitbucket", ("bitbucket",)),
    ("Jira", ("jira",)),
    ("Confluence", ("confluence",)),
    ("Slack", ("slack",)),
    ("Teams", ("microsoft teams", "teams")),
    ("SAP", ("sap", "sap hana", "s/4hana", "s4hana")),
    ("Salesforce", ("salesforce",)),
    ("ServiceNow", ("servicenow", "service now")),
    ("Workday", ("workday",)),
    ("Excel", ("excel", "microsoft excel", "ms excel")),
    ("Power BI", ("power bi", "powerbi")),
    ("Tableau", ("tableau",)),
    ("Looker", ("looker",)),
    ("Qlik", ("qlik",)),
    ("Snowflake", ("snowflake",)),
    ("Databricks", ("databricks",)),
    ("BigQuery", ("bigquery", "big query")),
    ("Redshift", ("redshift",)),
    ("Airflow", ("airflow",)),
    ("dbt", ("dbt",)),
    ("Spark", ("spark", "apache spark")),
    ("Kafka", ("kafka", "apache kafka")),
    ("RabbitMQ", ("rabbitmq", "rabbit mq")),
    ("Hadoop", ("hadoop",)),
    ("Pandas", ("pandas",)),
    ("NumPy", ("numpy",)),
    ("PySpark", ("pyspark",)),
    ("TensorFlow", ("tensorflow",)),
    ("PyTorch", ("pytorch",)),
    ("scikit-learn", ("scikit-learn", "sklearn", "scikit learn")),
    ("OpenAI", ("openai",)),
    ("LangChain", ("langchain",)),
    ("CrewAI", ("crewai", "crew ai")),
    ("LLM", ("llm", "llms")),
    ("QA", ("qa", "quality assurance")),
    ("Selenium", ("selenium",)),
    ("Cypress", ("cypress",)),
    ("Playwright", ("playwright",)),
    ("Jest", ("jest",)),
    ("Pytest", ("pytest",)),
    ("JUnit", ("junit",)),
    ("Postman", ("postman",)),
    ("Figma", ("figma",)),
    ("WordPress", ("wordpress",)),
    ("Shopify", ("shopify",)),
    ("Magento", ("magento",)),
    ("Linux", ("linux",)),
    ("Windows", ("windows",)),
    ("macOS", ("macos", "mac os")),
    ("Bash", ("bash",)),
    ("PowerShell", ("powershell",)),
    ("LAN", ("lan",)),
    ("WAN", ("wan",)),
    ("VPN", ("vpn",)),
    ("TCP/IP", ("tcp/ip", "tcp ip", "tcpip")),
    ("DNS", ("dns",)),
    ("DHCP", ("dhcp",)),
    ("Active Directory", ("active directory", "ad")),
    ("LDAP", ("ldap",)),
    ("VMware", ("vmware",)),
    ("Hyper-V", ("hyper-v", "hyper v")),
    ("Cisco", ("cisco",)),
)

_BOUNDARY_CHARS = r"A-Za-z0-9+#."


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_accents.lower()


def _keyword_pattern(variant: str) -> re.Pattern[str]:
    normalized_variant = re.escape(_normalize_text(variant))
    return re.compile(rf"(?<![{_BOUNDARY_CHARS}]){normalized_variant}(?![{_BOUNDARY_CHARS}])")


def extract_tech_stack_from_jd(job_description: str | None, interview_name: str | None = None) -> list[str]:
    """
    Extract known technology/tool keywords from a JD and search title.

    The return value is ordered by first appearance and deduplicated by display label.
    """
    parts = [interview_name or "", job_description or ""]
    text = _normalize_text("\n".join(part for part in parts if part))
    if not text.strip():
        return []

    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for display_name, variants in _KEYWORD_GROUPS:
        best_position: int | None = None
        for variant in variants:
            match = _keyword_pattern(variant).search(text)
            if match and (best_position is None or match.start() < best_position):
                best_position = match.start()

        if best_position is not None and display_name not in seen:
            found.append((best_position, display_name))
            seen.add(display_name)

    found.sort(key=lambda item: item[0])
    return [display_name for _, display_name in found]
