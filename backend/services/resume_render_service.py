from datetime import date, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates"
JAKE_TEMPLATE_DIR = "resume/jake"
DEFAULT_SECTIONS = {
    "contact": True,
    "education": True,
    "projects": True,
    "skills": True,
    "certificates": True,
}

_LATEX_ESCAPES = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
    "‘": "`",
    "’": "'",
    "“": "``",
    "”": "''",
    "‐": "-",
    "‑": "-",
    "‒": "--",
    "–": "--",
    "—": "---",
    "―": "---",
}


def latex_escape(value: Any) -> str:
    """Escape user-provided text for safe inclusion in LaTeX."""
    return "".join(_LATEX_ESCAPES.get(character, character) for character in str(value))


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _format_date(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%b %Y")
    return str(value) if value else ""


def _date_range(item: Any, start_name: str, end_name: str) -> str:
    start = _format_date(_field(item, start_name))
    end = _format_date(_field(item, end_name))
    if start and end:
        return f"{start} -- {end}"
    return start or end


def _selected_items(profile: Any, selection: Any, category: str) -> list[Any]:
    if selection is None or category not in selection:
        return list(_field(profile, category, None) or [])
    entries = selection[category]
    return [
        entry.get("item", entry) if isinstance(entry, dict) else _field(entry, "item", entry)
        for entry in entries
    ]


def _item_context(item: Any, category: str) -> dict[str, Any]:
    if category == "education":
        return {
            "institution": _field(item, "institution", ""),
            "degree": _field(item, "degree", ""),
            "field_of_study": _field(item, "field_of_study", ""),
            "dates": _date_range(item, "start_date", "end_date"),
        }
    if category == "projects":
        return {
            "title": _field(item, "title", ""),
            "tech_stack": _field(item, "tech_stack", None) or [],
            "bullets": _field(item, "bullets", None) or [],
            "dates": _date_range(item, "start_date", "end_date"),
            "url": _field(item, "url", ""),
        }
    if category == "skills":
        return {
            "name": _field(item, "name", ""),
            "category": _field(item, "category", ""),
            "proficiency": _field(item, "proficiency", ""),
        }
    return {
        "name": _field(item, "name", ""),
        "issuer": _field(item, "issuer", ""),
        "date": _format_date(_field(item, "date")),
        "url": _field(item, "url", ""),
    }


class ResumeRenderService:
    """Render profile facts and optional ranked selections into LaTeX."""

    def __init__(self, template_root: Path = TEMPLATE_ROOT) -> None:
        self.environment = Environment(
            loader=FileSystemLoader(str(template_root)),
            block_start_string=r"\BLOCK{",
            block_end_string="}",
            variable_start_string=r"\VAR{",
            variable_end_string="}",
            comment_start_string=r"\COMMENT{",
            comment_end_string="}",
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )
        self.environment.filters["latex_escape"] = latex_escape

    def render(
        self,
        profile: Any,
        selection: Any = None,
        sections: dict[str, bool] | None = None,
    ) -> str:
        section_toggles = DEFAULT_SECTIONS.copy()
        if sections is not None:
            unknown_sections = sections.keys() - section_toggles.keys()
            if unknown_sections:
                raise ValueError(
                    f"Unknown resume section(s): {', '.join(sorted(unknown_sections))}"
                )
            section_toggles.update(sections)

        context = {
            "name": _field(profile, "name", ""),
            "email": _field(profile, "email", ""),
            "phone": _field(profile, "phone", ""),
            "links": _field(profile, "links", None) or [],
            "sections": section_toggles,
            "education": [
                _item_context(item, "education")
                for item in _field(profile, "education", None) or []
            ],
            "projects": [
                _item_context(item, "projects")
                for item in _selected_items(profile, selection, "projects")
            ],
            "skills": [
                _item_context(item, "skills")
                for item in _selected_items(profile, selection, "skills")
            ],
            "certificates": [
                _item_context(item, "certificates")
                for item in _selected_items(profile, selection, "certificates")
            ],
        }
        template = self.environment.get_template(f"{JAKE_TEMPLATE_DIR}/resume.tex.j2")
        return template.render(**context)


resume_render_service = ResumeRenderService()
