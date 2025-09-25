from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, Iterable, List, Sequence, Tuple

from docx import Document
from pdfminer.high_level import extract_text

SECTION_RE = re.compile(r"\[(?:PART|PHẦN)\s*(\d)\]", re.IGNORECASE)
INDEX_RE = re.compile(r"^(?:câu|question)?\s*(\d+)(?:[\.\-:)]\s*)?(.*)$", re.IGNORECASE)

TRUE_VALUES = {"d", "đ", "t", "true", "y", "yes", "đúng"}
FALSE_VALUES = {"s", "f", "false", "n", "no", "sai"}


def extract_answer_text(uploaded_file) -> str:
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if name.endswith(".docx"):
        document = Document(uploaded_file)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if name.endswith(".pdf"):
        data = uploaded_file.read()
        return extract_text(BytesIO(data))
    data = uploaded_file.read()
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _iter_indexed_lines(lines: Iterable[str]) -> List[Tuple[int | None, str]]:
    entries: List[Tuple[int | None, str]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        match = INDEX_RE.match(line)
        if match:
            index = int(match.group(1))
            remainder = match.group(2).strip()
            entries.append((index, remainder))
        else:
            entries.append((None, line))
    return entries


def _normalize_order(entries: List[Tuple[int | None, str]], expected_count: int | None = None) -> List[str]:
    normalized: List[Tuple[int, str]] = []
    next_index = 1
    seen = set()
    for index, value in entries:
        if index is None:
            index = next_index
        if index < 1 or index in seen:
            raise ValueError("Invalid or duplicated question number")
        normalized.append((index, value))
        seen.add(index)
        next_index = index + 1

    normalized.sort(key=lambda item: item[0])
    for expected, (index, _) in enumerate(normalized, start=1):
        if index != expected:
            raise ValueError("Missing question number {}".format(expected))

    values = [value for _, value in normalized]
    if expected_count is not None and len(values) != expected_count:
        raise ValueError("Expected %d answers" % expected_count)
    return values


def parse_part1_lines(lines: Iterable[str], expected_count: int | None = None) -> List[str]:
    answers: List[str] = []
    normalized = _normalize_order(_iter_indexed_lines(lines), expected_count)
    for value in normalized:
        token = value.split()
        if not token:
            raise ValueError("Missing choice for a multiple-choice question")
        candidate = re.sub(r"[^a-dA-D]", "", token[0]).upper()
        if candidate not in {"A", "B", "C", "D"}:
            raise ValueError("Invalid choice %s" % token[0])
        answers.append(candidate)
    return answers


def _parse_true_false_token(token: str) -> bool:
    cleaned = token.strip().lower()
    cleaned = cleaned.replace(".", "")
    if cleaned in TRUE_VALUES:
        return True
    if cleaned in FALSE_VALUES:
        return False
    raise ValueError("Invalid true/false value: %s" % token)


def parse_part2_lines(
    lines: Iterable[str],
    statements: int = 4,
    expected_count: int | None = None,
) -> List[List[bool]]:
    answers: List[List[bool]] = []
    normalized = _normalize_order(_iter_indexed_lines(lines), expected_count)
    for value in normalized:
        tokens = [token for token in re.split(r"[\s,;]+", value) if token]
        if len(tokens) != statements:
            raise ValueError("Each True/False question must have %d values" % statements)
        answers.append([_parse_true_false_token(token) for token in tokens])
    return answers


def parse_part3_lines(lines: Iterable[str], expected_count: int | None = None) -> List[str]:
    answers: List[str] = []
    normalized = _normalize_order(_iter_indexed_lines(lines), expected_count)
    for value in normalized:
        answer = re.sub(r"\s+", "", value)
        answers.append(answer)
    return answers


def parse_answer_document(
    text: str,
    statements: int = 4,
) -> Dict[str, List]:
    sections: Dict[int, List[str]] = {1: [], 2: [], 3: []}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section = SECTION_RE.match(line)
        if section:
            current = int(section.group(1))
            continue
        if current in sections:
            sections[current].append(line)

    part1 = parse_part1_lines(sections[1]) if sections[1] else None
    part2 = (
        parse_part2_lines(sections[2], statements=statements) if sections[2] else None
    )
    part3 = parse_part3_lines(sections[3]) if sections[3] else None

    return {"part1": part1, "part2": part2, "part3": part3}

