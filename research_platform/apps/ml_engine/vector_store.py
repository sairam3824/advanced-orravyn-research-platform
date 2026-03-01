"""
ChromaDB vector store for research paper RAG.

Papers are indexed when approved. Each paper is chunked into ~400-word
segments and embedded with sentence-transformers all-MiniLM-L6-v2.
"""
import logging

logger = logging.getLogger(__name__)

_client = None
_collection = None


def get_collection():
    """Return (or lazily initialise) the ChromaDB collection."""
    global _client, _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        from django.conf import settings

        db_path = str(settings.BASE_DIR / 'chroma_db')
        _client = chromadb.PersistentClient(path=db_path)
        embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = _client.get_or_create_collection(
            name="research_papers",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        return _collection
    except Exception as exc:
        logger.error("ChromaDB initialisation failed: %s", exc)
        return None


def _extract_pdf_text(pdf_path: str) -> str:
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
        logger.warning("PDF text extraction failed for %s: %s", pdf_path, exc)
        return ""


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50):
    words = text.split()
    step = max(chunk_size - overlap, 1)
    chunks = []
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def index_paper(paper_id: int) -> None:
    """
    Index an approved paper into ChromaDB.
    Called from a background thread after paper approval.
    """
    collection = get_collection()
    if collection is None:
        return

    from apps.papers.models import Paper

    try:
        paper = Paper.objects.get(pk=paper_id, is_approved=True)
    except Paper.DoesNotExist:
        logger.warning("Paper %s not found or not approved; skipping indexing.", paper_id)
        return

    text_parts = []
    if paper.title:
        text_parts.append(f"Title: {paper.title}")
    if paper.authors:
        text_parts.append(f"Authors: {paper.authors}")
    if paper.abstract:
        text_parts.append(paper.abstract)
    if paper.summary:
        text_parts.append(paper.summary)
    if paper.pdf_path:
        try:
            pdf_text = _extract_pdf_text(paper.pdf_path.path)
            if pdf_text:
                text_parts.append(pdf_text)
        except Exception as exc:
            logger.warning("Could not read PDF for paper %s: %s", paper_id, exc)

    full_text = "\n\n".join(text_parts)
    if not full_text.strip():
        logger.warning("No indexable text for paper %s.", paper_id)
        return

    chunks = _chunk_text(full_text)
    if not chunks:
        return

    # Remove stale chunks before re-indexing
    _remove_chunks(collection, paper_id)

    ids = [f"paper_{paper_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "paper_id": paper_id,
            "title": paper.title or "",
            "authors": paper.authors or "",
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    logger.info("Indexed paper %s (%d chunks).", paper_id, len(chunks))


def remove_paper(paper_id: int) -> None:
    """Remove all chunks for a paper from ChromaDB."""
    collection = get_collection()
    if collection is None:
        return
    _remove_chunks(collection, paper_id)
    logger.info("Removed paper %s from vector store.", paper_id)


def _remove_chunks(collection, paper_id: int) -> None:
    try:
        existing = collection.get(where={"paper_id": paper_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception as exc:
        logger.warning("Could not remove existing chunks for paper %s: %s", paper_id, exc)


def search_papers(query: str, n_results: int = 5) -> list:
    """
    Semantic search over indexed paper chunks.
    Returns a list of dicts: [{content, metadata}, ...]
    """
    collection = get_collection()
    if collection is None:
        return []

    try:
        total = collection.count()
        if total == 0:
            return []
        n = min(n_results, total)
        results = collection.query(query_texts=[query], n_results=n)
        docs = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                docs.append({"content": doc, "metadata": meta})
        return docs
    except Exception as exc:
        logger.error("Vector search failed: %s", exc)
        return []
