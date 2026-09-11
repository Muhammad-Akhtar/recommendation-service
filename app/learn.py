"""File-backed Learning / revision catalog (docs/ml + ml/).

Reads markdown and implementation files from disk. No Redis, Postgres, or Kafka.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ML = REPO_ROOT / "docs" / "ml"
ML_ROOT = REPO_ROOT / "ml"
INDEX_FILE = DOCS_ML / "00_ML_PLAN_INDEX.md"
CONTEXT_FILE = DOCS_ML / "ML_CONTEXT.md"

ALLOWED_PREFIXES = ("docs/ml/", "ml/")

PHASE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*\[`([^`]+)`\]\([^)]+\)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)
TASK_HEADING = re.compile(r"^### Task (\d+\.\d+)\s+—\s+(.+)$", re.MULTILINE)
DONE_FILE = re.compile(r"^- \[[xX]\] Done — `([^`]+)`", re.MULTILINE)
NEXT_ACTION = re.compile(r"\*\*NEXT ACTION:\s*(.+?)\*\*")
PHASE_TITLE = re.compile(r"^# Phase \d+\s+—\s+(.+)$", re.MULTILINE)

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
}

router = APIRouter(prefix="/api/learn", tags=["learn"])


class LearnFile(BaseModel):
    path: str
    language: str
    content: str


class LearnTaskSummary(BaseModel):
    id: str
    title: str
    done: bool
    implementation_path: str | None = None


class LearnPhaseSummary(BaseModel):
    number: int
    title: str
    status: str
    file: str
    has_implementation: bool
    task_ids: list[str] = Field(default_factory=list)


class LearnCatalog(BaseModel):
    phases: list[LearnPhaseSummary]
    next_action: str | None = None


class LearnPhaseDetail(BaseModel):
    number: int
    title: str
    status: str
    file: str
    markdown: str
    tasks: list[LearnTaskSummary]
    has_implementation: bool
    notes_available: bool


class LearnTaskDetail(BaseModel):
    id: str
    title: str
    spec: str
    done: bool
    implementation: LearnFile | None = None


class LearnNotes(BaseModel):
    files: list[LearnFile]


class LearnContext(BaseModel):
    markdown: str


def _language_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return LANGUAGE_BY_SUFFIX.get(suffix, "text")


def implementation_dir(phase_number: int) -> Path | None:
    matches = sorted(ML_ROOT.glob(f"phase{phase_number:02d}_*"))
    dirs = [p for p in matches if p.is_dir()]
    return dirs[0] if dirs else None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_catalog() -> LearnCatalog:
    if not INDEX_FILE.is_file():
        raise HTTPException(status_code=404, detail="Learning index not found")
    index = _read_text(INDEX_FILE)
    next_match = NEXT_ACTION.search(index)
    next_action = next_match.group(1).strip() if next_match else None

    phases: list[LearnPhaseSummary] = []
    for number_s, filename, topic, status in PHASE_ROW.findall(index):
        number = int(number_s)
        phase_path = DOCS_ML / filename
        markdown = _read_text(phase_path) if phase_path.is_file() else ""
        tasks = extract_tasks(markdown)
        impl = implementation_dir(number)
        phases.append(
            LearnPhaseSummary(
                number=number,
                title=topic.strip(),
                status=status.strip(),
                file=f"docs/ml/{filename}",
                has_implementation=impl is not None,
                task_ids=[t.id for t in tasks],
            )
        )
    return LearnCatalog(phases=phases, next_action=next_action)


def extract_tasks(markdown: str) -> list[LearnTaskSummary]:
    headings = list(TASK_HEADING.finditer(markdown))
    tasks: list[LearnTaskSummary] = []
    for i, match in enumerate(headings):
        start = match.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else _end_of_tasks(markdown, start)
        slice_md = markdown[start:end]
        done_match = DONE_FILE.search(slice_md)
        tasks.append(
            LearnTaskSummary(
                id=match.group(1),
                title=match.group(2).strip(),
                done=done_match is not None,
                implementation_path=done_match.group(1) if done_match else None,
            )
        )
    return tasks


def _end_of_tasks(markdown: str, start: int) -> int:
    """Task block ends at the next top-level ## after the current task heading."""
    rest = markdown[start + 1 :]
    heading = re.search(r"\n## ", rest)
    if heading:
        return start + 1 + heading.start()
    return len(markdown)


def task_spec(markdown: str, task_id: str) -> tuple[str, str] | None:
    headings = list(TASK_HEADING.finditer(markdown))
    for i, match in enumerate(headings):
        if match.group(1) != task_id:
            continue
        start = match.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else _end_of_tasks(markdown, start)
        return match.group(2).strip(), markdown[start:end].strip()
    return None


def phase_markdown_path(phase_number: int) -> Path | None:
    catalog = parse_catalog()
    for phase in catalog.phases:
        if phase.number == phase_number:
            return REPO_ROOT / phase.file
    return None


def phase_status(phase_number: int) -> LearnPhaseSummary:
    catalog = parse_catalog()
    for phase in catalog.phases:
        if phase.number == phase_number:
            return phase
    raise HTTPException(status_code=404, detail=f"Unknown phase {phase_number}")


def resolve_allowed_file(relative: str) -> Path:
    normalized = relative.replace("\\", "/").lstrip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if ".." in Path(normalized).parts or normalized.startswith(".."):
        raise HTTPException(status_code=404, detail="Path not allowed")
    if not normalized.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status_code=404, detail="Path not allowed")
    candidate = (REPO_ROOT / normalized).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Path not allowed") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


def load_file(relative: str) -> LearnFile:
    path = resolve_allowed_file(relative)
    rel = path.relative_to(REPO_ROOT).as_posix()
    return LearnFile(
        path=rel,
        language=_language_for(rel),
        content=_read_text(path),
    )


def notes_for_phase(phase_number: int) -> list[LearnFile]:
    folder = implementation_dir(phase_number)
    if folder is None:
        return []
    files: list[LearnFile] = []
    notes = folder / "NOTES.md"
    if notes.is_file():
        files.append(load_file(notes.relative_to(REPO_ROOT).as_posix()))
    for extra in sorted(folder.glob("*.md")):
        if extra.name in {"NOTES.md", "README.md"}:
            continue
        files.append(load_file(extra.relative_to(REPO_ROOT).as_posix()))
    return files


@router.get("/catalog", response_model=LearnCatalog)
def get_catalog() -> LearnCatalog:
    return parse_catalog()


@router.get("/context", response_model=LearnContext)
def get_context() -> LearnContext:
    if not CONTEXT_FILE.is_file():
        raise HTTPException(status_code=404, detail="Context file not found")
    return LearnContext(markdown=_read_text(CONTEXT_FILE))


@router.get("/phases/{phase_number}", response_model=LearnPhaseDetail)
def get_phase(phase_number: int) -> LearnPhaseDetail:
    summary = phase_status(phase_number)
    path = REPO_ROOT / summary.file
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Phase file not found")
    markdown = _read_text(path)
    title_match = PHASE_TITLE.search(markdown)
    title = title_match.group(1).strip() if title_match else summary.title
    return LearnPhaseDetail(
        number=summary.number,
        title=title,
        status=summary.status,
        file=summary.file,
        markdown=markdown,
        tasks=extract_tasks(markdown),
        has_implementation=summary.has_implementation,
        notes_available=bool(notes_for_phase(phase_number)),
    )


@router.get("/phases/{phase_number}/tasks/{task_id}", response_model=LearnTaskDetail)
def get_task(phase_number: int, task_id: str) -> LearnTaskDetail:
    summary = phase_status(phase_number)
    path = REPO_ROOT / summary.file
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Phase file not found")
    markdown = _read_text(path)
    parsed = task_spec(markdown, task_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail=f"Unknown task {task_id}")
    title, spec = parsed
    tasks = extract_tasks(markdown)
    match = next((t for t in tasks if t.id == task_id), None)
    implementation = None
    if match and match.implementation_path:
        implementation = load_file(match.implementation_path)
    return LearnTaskDetail(
        id=task_id,
        title=title,
        spec=spec,
        done=bool(match and match.done),
        implementation=implementation,
    )


@router.get("/phases/{phase_number}/notes", response_model=LearnNotes)
def get_notes(phase_number: int) -> LearnNotes:
    phase_status(phase_number)
    files = notes_for_phase(phase_number)
    if not files:
        raise HTTPException(status_code=404, detail="No notes for this phase")
    return LearnNotes(files=files)


@router.get("/file", response_model=LearnFile)
def get_file(path: str = Query(..., min_length=1)) -> LearnFile:
    return load_file(path)
