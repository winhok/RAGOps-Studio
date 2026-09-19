from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile
from app.core.errors import AppError

def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in {'.txt', '.md'}:
            return content.decode('utf-8-sig', errors='strict')
        if suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise AppError('Encrypted PDFs are not supported')
            if len(reader.pages) > 200:
                raise AppError('PDF exceeds the 200 page limit')
            return '\n\n'.join((page.extract_text() or '' for page in reader.pages))
        if suffix == '.docx':
            with ZipFile(BytesIO(content)) as archive:
                if len(archive.infolist()) > 2000 or sum((i.file_size for i in archive.infolist())) > 20000000:
                    raise AppError('Expanded DOCX exceeds the size limit')
            return docx_markdown(content)
    except AppError:
        raise
    except (UnicodeError, BadZipFile, ValueError, OSError) as exc:
        raise AppError('The file cannot be parsed. Check its format and encoding.') from exc
    except Exception as exc:
        raise AppError('Document parsing failed; no content was published') from exc
    raise AppError('Supported file types: .md, .txt, .pdf, .docx')


def markdown_text(text: str) -> str:
    return re.sub(r'([\\`*_\[\]<>#|])', r'\\\1', text.strip())


def docx_markdown(content: bytes) -> str:
    """Preserve body order and indexable Word structure without external services."""
    from docx import Document
    from docx.table import Table
    from docx.oxml.ns import qn

    document = Document(BytesIO(content))
    parts = []
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            rows = [[markdown_text(cell.text).replace('\n', '<br>') for cell in row.cells] for row in block.rows]
            if not rows or not any(cell for row in rows for cell in row):
                continue
            # Keep every row, including the first; merged cells may repeat their text.
            parts.append('\n'.join(['| ' + ' | '.join(rows[0]) + ' |', '| ' + ' | '.join('---' for _ in rows[0]) + ' |', *['| ' + ' | '.join(row) + ' |' for row in rows[1:]]]))
            continue
        if not block.text.strip():
            continue
        text = markdown_text(block.text)
        level, marker = None, ''
        properties = [block._p.pPr]
        style = block.style
        for _ in range(10):
            if style is None:
                break
            name = style.name or ''
            heading = re.fullmatch(r'(?:Heading|标题)\s*([1-6])', name, re.I)
            if heading and level is None:
                level = int(heading[1])
            if name == 'Title' and level is None:
                level = 1
            if name.startswith('List Bullet'):
                marker = '- '
            elif name.startswith('List Number'):
                marker = '1. '
            properties.append(style.element.pPr)
            style = style.base_style
        for prop in properties:
            if prop is None:
                continue
            outline = prop.find(qn('w:outlineLvl'))
            if outline is not None and level is None:
                value = int(outline.get(qn('w:val')))
                if 0 <= value <= 5:
                    level = value + 1
            numbering = prop.find(qn('w:numPr'))
            if numbering is not None and not marker:
                num_id = numbering.find(qn('w:numId'))
                if num_id is not None and num_id.get(qn('w:val')) != '0':
                    marker = '- '
        parts.append(('#' * level + ' ' if level else marker) + text)
    return '\n\n'.join(parts)
