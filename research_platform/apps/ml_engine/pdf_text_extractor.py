"""
Thin helper for extracting plain text from a PDF file-like object
or a file path. Used by section_summarizer and vector_store.
"""
import logging

logger = logging.getLogger(__name__)


def extract_pdf_text_from_path(pdf_path: str) -> str:
    """Extract text from a PDF at the given filesystem path."""
    try:
        import PyPDF2
        text = ""
        with open(pdf_path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as exc:
        logger.warning("PDF path extraction failed for %s: %s", pdf_path, exc)
        return ""


def extract_pdf_text_from_file(pdf_file) -> str:
    """
    Extract text from a Django FieldFile / file-like object.
    Seeks back to position 0 after reading so callers can re-use the file.
    """
    try:
        import PyPDF2
        text = ""
        try:
            pdf_file.seek(0)
        except Exception as seek_err:
            logger.debug("Could not seek PDF file to start (non-fatal): %s", seek_err)
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        try:
            pdf_file.seek(0)
        except Exception as seek_err:
            logger.debug("Could not seek PDF file back to start (non-fatal): %s", seek_err)
        return text
    except Exception as exc:
        logger.warning("PDF file extraction failed: %s", exc)
        return ""
