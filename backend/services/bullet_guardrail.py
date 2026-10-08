import re


_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(?:[$€£]\s*)?\d[\d,]*(?:\.\d+)?(?:\s*%)?(?!\w)"
)
_PROPER_NOUN_PATTERN = re.compile(
    r"\b[A-Z][a-zA-Z0-9]*(?:[.+#-][A-Za-z0-9]+)*\b"
    r"(?:\s+\b[A-Z][a-zA-Z0-9]*(?:[.+#-][A-Za-z0-9]+)*\b)*"
)
_TECHNOLOGY_TERMS = (
    "Amazon Web Services", "Google Cloud Platform", "Microsoft Azure",
    "TensorFlow", "PyTorch", "scikit-learn", "Spring Boot", "Node.js",
    "Next.js", "FastAPI", "PostgreSQL", "MySQL", "MongoDB", "Kubernetes",
    "JavaScript", "TypeScript", "GraphQL", "OpenAI", "Redis", "Docker",
    "Jenkins", "Terraform", "Ansible", "Pandas", "NumPy", "React", "Vue.js",
    "Angular", "Django", "Flask", "Express.js", "Node", "Python", "Java",
    "Kotlin", "Swift", "Rust", "Golang", "Go", "C++", "C#", ".NET",
    "AWS", "GCP", "Azure", "SQL", "NoSQL", "HTML", "CSS", "SASS",
    "Linux", "Git", "GitHub", "GitLab", "Celery", "RabbitMQ", "Kafka",
    "Elasticsearch", "Snowflake", "Databricks", "Spark", "Hadoop",
    "PHP", "Ruby", "Rails", "Laravel", "Unity", "Unreal Engine",
    "API", "REST", "HTTP", "HTTPS", "JSON", "XML", "JWT", "OAuth",
    "CI/CD", "WebSocket",
)
_TECHNOLOGY_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(
        re.escape(term)
        for term in sorted(_TECHNOLOGY_TERMS, key=len, reverse=True)
    )
    + r")(?!\w)",
    re.IGNORECASE,
)
_ACTION_VERBS = {
    "achieved", "analyzed", "automated", "built", "collaborated", "created",
    "cut", "delivered", "designed", "developed", "drove", "enhanced",
    "established", "implemented", "improved", "increased", "integrated",
    "launched", "led", "maintained", "managed", "optimized", "reduced",
    "resolved", "streamlined", "tested", "transformed",
}


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _extract_tokens(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for match in _NUMBER_PATTERN.finditer(text):
        tokens.append(("number", match.group().strip()))

    technology_spans = []
    for match in _TECHNOLOGY_PATTERN.finditer(text):
        technology_spans.append(match.span())
        tokens.append(("technology", match.group().strip()))

    for match in _PROPER_NOUN_PATTERN.finditer(text):
        start, end = match.span()
        value = match.group().strip()
        if any(start < tech_end and end > tech_start for tech_start, tech_end in technology_spans):
            continue
        sentence_start = max(
            text.rfind("\n", 0, start),
            text.rfind(".", 0, start),
            text.rfind("!", 0, start),
            text.rfind("?", 0, start),
        ) + 1
        if (
            not text[sentence_start:start].strip()
            and value.split()[0].casefold() in _ACTION_VERBS
        ):
            continue
        tokens.append(("proper_noun", value))
    return tokens


def find_unverified_tokens(
    original: str,
    rewritten: str,
    tech_stack: list[str] | None = None,
) -> list[str]:
    """Return rewritten numbers, technologies, and names not grounded in source facts."""
    source_facts = f"{original}\n{' '.join(tech_stack or [])}"
    known = {
        (kind, _normalize(token))
        for kind, token in _extract_tokens(source_facts)
    }
    unverified = []
    seen = set()
    for kind, token in _extract_tokens(rewritten):
        identity = (kind, _normalize(token))
        if identity in known:
            continue
        displayed = f"{kind}: {token}"
        if displayed not in seen:
            seen.add(displayed)
            unverified.append(displayed)
    return unverified
