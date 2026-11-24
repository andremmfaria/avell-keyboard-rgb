"""Documentation checks: local links resolve, docs are cross linked, no em or en dashes."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EM_DASH = "\u2014"
EN_DASH = "\u2013"

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SRC_RE = re.compile(r"""<img[^>]*\ssrc=["']([^"']+)["']""")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def markdown_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "todo.md", ROOT / "tests" / "hardware" / "README.md"]
    files += sorted(DOCS.glob("*.md"))
    return files


def doc_files() -> list[Path]:
    return sorted(DOCS.glob("*.md"))


def prose_lines(path: Path) -> list[str]:
    """Lines of the file outside fenced code blocks."""
    lines: list[str] = []
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            lines.append(line)
    return lines


def slug(heading: str) -> str:
    """GitHub style anchor for a heading."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text)


def anchors(path: Path) -> set[str]:
    found: dict[str, int] = {}
    result: set[str] = set()
    for line in prose_lines(path):
        match = HEADING_RE.match(line)
        if not match:
            continue
        base = slug(match.group(1))
        count = found.get(base, 0)
        found[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def local_links(path: Path) -> list[tuple[str, str]]:
    """(target file part, anchor) for every link to a local file or anchor."""
    links: list[tuple[str, str]] = []
    for line in prose_lines(path):
        stripped = re.sub(r"`[^`]*`", "", line)
        targets = LINK_RE.findall(stripped) + SRC_RE.findall(stripped)
        for target in targets:
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            file_part, _, anchor = target.partition("#")
            links.append((unquote(file_part), anchor))
    return links


def linked_docs(path: Path) -> set[Path]:
    """Files in docs/ that `path` links to, other than itself."""
    found: set[Path] = set()
    for file_part, _ in local_links(path):
        if not file_part:
            continue
        resolved = (path.parent / file_part).resolve()
        if resolved.parent == DOCS and resolved.suffix == ".md" and resolved != path.resolve():
            found.add(resolved)
    return found


def test_docs_exist() -> None:
    names = {p.name for p in doc_files()}
    assert "README.md" in names
    assert len(names) >= 9


def test_local_links_resolve() -> None:
    problems: list[str] = []
    for path in markdown_files():
        for file_part, anchor in local_links(path):
            target = path if not file_part else (path.parent / file_part).resolve()
            label = f"{path.relative_to(ROOT)}: {file_part}#{anchor}".rstrip("#")
            if not target.exists():
                problems.append(f"{label} does not exist")
                continue
            if anchor and target.suffix == ".md" and anchor not in anchors(target):
                problems.append(f"{label} has no matching heading")
    assert not problems, "\n".join(problems)


def test_docs_readme_links_every_doc() -> None:
    linked = linked_docs(DOCS / "README.md")
    missing = [p.name for p in doc_files() if p.name != "README.md" and p not in linked]
    assert not missing, f"docs/README.md does not link: {missing}"


def test_root_readme_links_every_doc() -> None:
    root_links = {
        (ROOT / file_part).resolve()
        for file_part, _ in local_links(ROOT / "README.md")
        if file_part
    }
    missing = [p.name for p in doc_files() if p.resolve() not in root_links]
    assert not missing, f"README.md does not link: {missing}"


def test_every_doc_links_two_other_docs() -> None:
    problems = [
        f"{p.name} links only {sorted(q.name for q in linked_docs(p))}"
        for p in doc_files()
        if len(linked_docs(p)) < 2
    ]
    assert not problems, "\n".join(problems)


def test_every_doc_ends_with_related_documentation() -> None:
    for path in doc_files():
        headings = [
            line for line in prose_lines(path) if line.startswith("#") and HEADING_RE.match(line)
        ]
        assert headings[-1].strip() == "## Related documentation", path.name


def test_hardware_readme_links_docs() -> None:
    hardware = ROOT / "tests" / "hardware" / "README.md"
    targets = {(hardware.parent / f).resolve() for f, _ in local_links(hardware) if f}
    assert (DOCS / "development.md").resolve() in targets
    assert (DOCS / "hardware.md").resolve() in targets
    assert (ROOT / "tests" / "hardware" / "README.md").resolve() in {
        (DOCS / f).resolve() for f, _ in local_links(DOCS / "development.md") if f
    }


def test_no_em_or_en_dashes() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in markdown_files()
        if EM_DASH in (text := path.read_text(encoding="utf-8")) or EN_DASH in text
    ]
    assert not offenders, f"em or en dashes in: {offenders}"


def test_nfpm_installs_every_doc() -> None:
    nfpm = (ROOT / "nfpm.yaml").read_text(encoding="utf-8")
    missing = [p.name for p in doc_files() if f"src: docs/{p.name}\n" not in nfpm]
    assert not missing, f"nfpm.yaml does not install: {missing}"
    check = (ROOT / "deploy" / "check-packages.sh").read_text(encoding="utf-8")
    unchecked = [p.stem for p in doc_files() if not re.search(rf"\b{re.escape(p.stem)}\b", check)]
    assert not unchecked, f"deploy/check-packages.sh does not check: {unchecked}"
