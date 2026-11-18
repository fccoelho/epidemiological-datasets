"""Keep the numbers advertised in README.md in sync with the repository.

README.md repeats several counts (registered sources, accessor modules,
documentation pages, example notebooks).  They silently rot every time a
source is added, so this test recomputes each one from the repository and
fails with the expected value when the prose drifts.

No network access and no installed package required: everything is read
from the source tree, and pyproject.toml is parsed with a small line-based
reader so the test also runs on Python 3.10 (which lacks ``tomllib``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
SOURCES_DIR = REPO_ROOT / "src" / "epidatasets" / "sources"
DOCS_SOURCES_DIR = REPO_ROOT / "docs" / "sources"
EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"

ENTRY_POINT_GROUP = 'epidatasets.sources'


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def _entry_points() -> dict[str, str]:
    """Map name -> "module:Class" for ``[project.entry-points."epidatasets.sources"]``."""
    lines = PYPROJECT.read_text(encoding="utf-8").splitlines()
    entries: dict[str, str] = {}
    in_section = False
    for raw in lines:
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            header = line.strip("[]").replace('"', "").replace("'", "")
            in_section = header.endswith(ENTRY_POINT_GROUP)
            continue
        if not in_section or not line or line.startswith("#"):
            continue
        if "=" in line and not line.startswith("["):
            name, value = line.split("=", 1)
            entries[name.strip()] = value.strip().strip('"').strip("'")
    return entries


def _entry_point_names() -> list[str]:
    return list(_entry_points())


def _accessor_modules() -> list[str]:
    return sorted(
        p.stem
        for p in SOURCES_DIR.glob("*.py")
        if p.stem not in {"__init__", "conftest"}
    )


def _doc_pages() -> list[Path]:
    """Per-source API pages (the ``sources/index.md`` overview is not a source)."""
    return sorted(p for p in DOCS_SOURCES_DIR.glob("*.md") if p.stem != "index")


def _notebooks() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.ipynb"))


def _all_numbers(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text)


class TestSourceCounts:
    """The "how many data sources" numbers must match the registry."""

    def test_entry_points_resolve_to_existing_modules(self) -> None:
        problems: list[str] = []
        for name, target in _entry_points().items():
            module_path, _, class_name = target.partition(":")
            relative = module_path.replace(".", "/") + ".py"
            if not (REPO_ROOT / "src" / relative).is_file():
                problems.append(f"{name}: missing module {module_path}")
                continue
            if class_name:
                source = (REPO_ROOT / "src" / relative).read_text(encoding="utf-8")
                if not re.search(rf"^class {re.escape(class_name)}\b", source, re.MULTILINE):
                    problems.append(f"{name}: no class {class_name} in {module_path}")
        assert not problems, "broken entry-points: " + "; ".join(problems)

    def test_every_accessor_module_is_registered(self) -> None:
        registered = {
            target.partition(":")[0].rsplit(".", 1)[-1]
            for target in _entry_points().values()
        }
        modules = set(_accessor_modules())
        assert registered == modules, (
            "src/epidatasets/sources/*.py and the plugin registry disagree — "
            f"module without entry-point: {sorted(modules - registered)}; "
            f"entry-point without module: {sorted(registered - modules)}"
        )

    def test_prose_source_count(self) -> None:
        expected = str(len(_entry_point_names()))
        text = _readme_text()
        patterns = [
            r"\*\*(\d+) epidemiological data sources\*\*",
            r"access (\d+) data sources",
            r"interface to (\d+) epidemiological data sources",
        ]
        found: list[tuple[str, str]] = []
        for pattern in patterns:
            for value in _all_numbers(text, pattern):
                found.append((pattern, value))
        assert found, "README.md no longer states the number of data sources"
        wrong = [(p, v) for p, v in found if v != expected]
        assert not wrong, (
            f"README.md states the wrong number of data sources (expected {expected}): {wrong}"
        )

    def test_statistics_block_source_count(self) -> None:
        expected = str(len(_entry_point_names()))
        values = _all_numbers(_readme_text(), r"\*\*Data sources:\*\* (\d+) registered")
        assert values, "README.md lost the 'Data sources: N registered' statistics line"
        assert values == [expected], (
            f"'Data sources: N registered' says {values}, expected [{expected}]"
        )

    def test_tree_accessor_module_count(self) -> None:
        expected = str(len(_accessor_modules()))
        values = _all_numbers(_readme_text(), r"# (\d+) data source accessors")
        assert values, "README.md lost the accessor count in the repository tree"
        assert values == [expected], (
            f"repository tree says {values} accessor modules, expected [{expected}]"
        )


class TestDocumentationCounts:
    """Documentation page and notebook counts must match the docs tree."""

    def test_docs_source_page_count(self) -> None:
        expected = str(len(_doc_pages()))
        values = _all_numbers(_readme_text(), r"# Per-source API docs \((\d+) pages\)")
        assert values, "README.md lost the per-source docs page count in the repository tree"
        assert values == [expected], (
            f"repository tree says {values} docs pages, expected [{expected}]"
        )

    def test_every_source_has_a_documentation_page(self) -> None:
        missing = sorted(set(_entry_point_names()) - {p.stem for p in _doc_pages()})
        assert not missing, f"data sources without a docs/sources page: {missing}"

    def test_documentation_pages_are_in_the_nav(self) -> None:
        nav = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
        missing = sorted(
            page.stem for page in _doc_pages() if f"sources/{page.name}" not in nav
        )
        assert not missing, f"docs pages missing from the mkdocs nav: {missing}"

    def test_notebook_count(self) -> None:
        expected = str(len(_notebooks()))
        values = _all_numbers(_readme_text(), r"\*\*Example notebooks:\*\* (\d+)")
        assert values, "README.md lost the 'Example notebooks: N' statistics line"
        assert values == [expected], (
            f"'Example notebooks: N' says {values}, expected [{expected}]"
        )

    @pytest.mark.parametrize(
        ("relative_path", "pattern"),
        [
            ("docs/index.md", r"\*\*(\d+) data sources\*\*"),
            ("docs/sources/index.md", r"\*\*(\d+) epidemiological data sources\*\*"),
        ],
    )
    def test_docs_prose_source_count(self, relative_path: str, pattern: str) -> None:
        expected = str(len(_entry_point_names()))
        values = _all_numbers(
            (REPO_ROOT / relative_path).read_text(encoding="utf-8"), pattern
        )
        assert values, f"{relative_path} no longer states the number of data sources"
        assert values == [expected], (
            f"{relative_path} says {values} data sources, expected [{expected}]"
        )

    @pytest.mark.parametrize("directory", [DOCS_SOURCES_DIR, EXAMPLES_DIR])
    def test_documentation_directories_exist(self, directory: Path) -> None:
        assert directory.is_dir(), f"missing documentation directory: {directory}"
