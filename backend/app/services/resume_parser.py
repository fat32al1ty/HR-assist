from io import BytesIO

from docx import Document
from pypdf import PdfReader


def extract_text(content: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        return _extract_pdf_text(content)

    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(content)

    raise ValueError("Unsupported file type")


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(page.strip() for page in pages if page.strip())


def _extract_docx_text(content: bytes) -> str:
    document = Document(BytesIO(content))
    paragraphs = [
        paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()
    ]
    return "\n".join(paragraphs)
