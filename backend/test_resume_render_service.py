from datetime import date
from types import SimpleNamespace

import pytest

from backend.services.resume_render_service import (
    ResumeRenderService,
    latex_escape,
)


@pytest.mark.parametrize(
    ("value", "escaped"),
    [
        ("C&C++", r"C\&C++"),
        ("100%", r"100\%"),
        ("a_b", r"a\_b"),
        ("$5", r"\$5"),
        ("#1", r"\#1"),
        ("{value}", r"\{value\}"),
        ("~^\\", r"\textasciitilde{}\textasciicircum{}\textbackslash{}"),
        ("“Hello”—‘world’", "``Hello''---`world'"),
    ],
)
def test_latex_escape(value, escaped):
    assert latex_escape(value) == escaped


def test_renderer_uses_selected_items_and_honors_section_toggles():
    profile = SimpleNamespace(
        name="Ada Lovelace",
        email="ada@example.com",
        phone="555-0100",
        links=["https://example.com"],
        education=[
            SimpleNamespace(
                institution="Example University",
                degree="B.S.",
                field_of_study="Computer Science",
                start_date=date(2020, 9, 1),
                end_date=date(2024, 5, 1),
            )
        ],
        projects=[
            SimpleNamespace(title="Unselected project", tech_stack=[], bullets=[])
        ],
        skills=[SimpleNamespace(name="Python", category="Languages", proficiency=None)],
        certificates=[],
    )
    selected_project = SimpleNamespace(
        title="Selected C&C++ project",
        tech_stack=["C&C++"],
        bullets=["Used 100% test coverage"],
        start_date=date(2023, 1, 1),
        end_date=None,
        url=None,
    )

    rendered = ResumeRenderService().render(
        profile,
        selection={
            "projects": [{"item": selected_project}],
            "skills": [],
            "certificates": [],
        },
        sections={"education": False, "certificates": False},
    )

    assert "Selected C\\&C++ project" in rendered
    assert "C\\&C++" in rendered
    assert "Used 100\\% test coverage" in rendered
    assert "Unselected project" not in rendered
    assert "Example University" not in rendered
    assert "\\section{Certifications}" not in rendered
    assert "\\section{Technical Skills}" not in rendered
    assert "\\VAR{" not in rendered


def test_renderer_rejects_unknown_section_toggle():
    profile = SimpleNamespace(name="Ada", links=[])

    with pytest.raises(ValueError, match="Unknown resume section"):
        ResumeRenderService().render(profile, sections={"references": True})
