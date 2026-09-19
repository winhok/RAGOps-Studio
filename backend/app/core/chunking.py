from __future__ import annotations
import hashlib
from markdown_it import MarkdownIt
from .models import Chunk, Document
from .errors import AppError

class TableParagraph(str):
    """A parser-recognized table; pipe characters in code remain ordinary text."""

def normalize_markdown(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()

def markdown_sections(text: str) -> list[tuple[str, list[str]]]:
    normalized = normalize_markdown(text)
    tokens = MarkdownIt('commonmark').enable('table').parse(normalized)
    lines = normalized.splitlines()
    headings: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    paragraphs: list[str] = []
    current = ''
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == 'table_open':
            paragraphs.append(TableParagraph('\n'.join(lines[token.map[0]:token.map[1]])))
            while tokens[i].type != 'table_close':
                i += 1
            i += 1
            continue
        if token.type == 'heading_open':
            if paragraphs:
                sections.append((current, paragraphs))
            level = int(token.tag[1:])
            headings = headings[:level - 1]
            while len(headings) < level - 1:
                headings.append('')
            headings.append(tokens[i + 1].content.strip())
            current = ' / '.join((h for h in headings if h))
            paragraphs = []
            i += 3
            continue
        if token.type in {'inline', 'fence', 'code_block'} and token.content.strip():
            paragraphs.append(token.content.strip())
        i += 1
    if paragraphs:
        sections.append((current, paragraphs))
    return sections

def chunk_document(document: Document, *, chunk_size: int=700, overlap: int=80) -> list[Chunk]:
    if chunk_size < 160 or overlap < 0 or overlap >= chunk_size // 2:
        raise ValueError('Invalid chunk size or overlap')
    pieces: list[str] = []
    for heading, paragraphs in markdown_sections(document.content):
        prefix = heading[:chunk_size // 3] + '\n\n' if heading else ''
        limit = chunk_size - len(prefix)
        current = ''
        for paragraph in paragraphs:
            if isinstance(paragraph, TableParagraph):
                if current:
                    pieces.append(prefix + current)
                    current = ''
                rows = paragraph.splitlines()
                header = '\n'.join(rows[:2])
                table = header
                if len(header) > limit:
                    raise AppError('Table header exceeds the chunk size; shorten its cells before publication')
                for row in rows[2:]:
                    if len(header) + 1 + len(row) > limit:
                        raise AppError('Table row exceeds the chunk size; shorten its cells before publication')
                    if len(table) + 1 + len(row) > limit:
                        pieces.append(prefix + table)
                        table = header
                    table += '\n' + row
                pieces.append(prefix + table)
                continue
            if len(paragraph) > limit:
                if current:
                    pieces.append(prefix + current)
                    current = ''
                for start in range(0, len(paragraph), limit - overlap):
                    pieces.append(prefix + paragraph[start:start + limit])
                    if start + limit >= len(paragraph):
                        break
                continue
            candidate = f'{current}\n\n{paragraph}' if current else paragraph
            if len(candidate) > limit:
                pieces.append(prefix + current)
                current = paragraph
            else:
                current = candidate
        if current:
            pieces.append(prefix + current)
    result = []
    for index, text in enumerate(pieces):
        digest = hashlib.sha256(f'{document.tenant_id}:{document.id}:{document.version}:{index}:{text}'.encode()).hexdigest()
        result.append(Chunk(id=f'chk_{digest[:32]}', document_id=document.id, revision_id=document.revision_id, tenant_id=document.tenant_id, title=document.title, text=text, version=document.version, index=index, department_id=document.department_id, visibility=document.visibility, evidence_type=document.evidence_type, effective_at=document.effective_at, expires_at=document.expires_at, source_path=document.source_path, active=document.active, additional_evidence_types=document.additional_evidence_types))
    return result
