"""
Minimal PDF text extractor and chunker for the BART summarisation pipeline.

Dependencies: pypdf (install via `pip install pypdf`)
"""
import re
import logging
from typing import List

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF files and split into fixed-size word chunks."""

    def extract_text(self, pdf_path: str) -> str:
        """Return the full text content of a PDF file."""
        try:
            # Support both pypdf (>=3) and the legacy PyPDF2 package
            try:
                import pypdf as _pdf_lib
            except ImportError:
                import PyPDF2 as _pdf_lib  # type: ignore

            reader = _pdf_lib.PdfReader(pdf_path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)
        except ImportError:
            logger.error(
                "PDF library not found. Install with: pip install pypdf  (or pip install PyPDF2)"
            )
            return ""
        except Exception as exc:
            logger.error(f"Failed to extract text from PDF '{pdf_path}': {exc}")
            return ""

    def chunk_text(self, text: str, max_length: int = 400) -> List[str]:
        """Split *text* into chunks of at most *max_length* words."""
        words = text.split()
        if not words:
            return []
        chunks = []
        for i in range(0, len(words), max_length):
            chunk = " ".join(words[i : i + max_length])
            chunk = re.sub(r"\s+", " ", chunk).strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    def extract_and_chunk(self, pdf_path: str, max_words: int = 400) -> List[str]:
        """Extract text from *pdf_path* and return word-bounded chunks."""
        text = self.extract_text(pdf_path)
        if not text.strip():
            return []
        return self.chunk_text(text, max_length=max_words)
