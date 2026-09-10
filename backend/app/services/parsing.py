from __future__ import annotations
from io import BytesIO
from pathlib import Path
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
            from docx import Document
            with ZipFile(BytesIO(content)) as archive:
                if sum((i.file_size for i in archive.infolist())) > 20000000:
                    raise AppError('Expanded DOCX exceeds the size limit')
            return '\n\n'.join((p.text for p in Document(BytesIO(content)).paragraphs))
    except AppError:
        raise
    except (UnicodeError, BadZipFile, ValueError, OSError) as exc:
        raise AppError('The file cannot be parsed. Check its format and encoding.') from exc
    except Exception as exc:
        raise AppError('Document parsing failed; no content was published') from exc
    raise AppError('Supported file types: .md, .txt, .pdf, .docx')
