"""
Citation Extractor — auto-populates Citation records by:

  1. Extracting the References section from raw PDF text
  2. Splitting into individual reference entries
  3. Matching each entry against papers already in the DB
     - Pass 1: exact DOI match
     - Pass 2: exact title substring match
     - Pass 3: fuzzy title match (SequenceMatcher, threshold 0.72)
  4. Creating Citation(citing_paper, cited_paper) records for every match

Called from apps/papers/signals.py as a background task after upload.
"""
import re
import logging
from difflib import SequenceMatcher
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Detect start of a references/bibliography section ──────────────────────
# Covers: bare "References", "References:", Arabic "5. References",
# IEEE Roman-numeral "VII. References", and all-caps variants.
_ROMAN = r"(?:[IVXLCDM]+\.)?"
_REF_START_PATTERNS: List[re.Pattern] = [
    re.compile(rf"^\s*(?:\d*\.?\s*|{_ROMAN}\s*)references?:?\s*$",       re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*(?:\d*\.?\s*|{_ROMAN}\s*)bibliography:?\s*$",       re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*(?:\d*\.?\s*|{_ROMAN}\s*)works?\s+cited:?\s*$",     re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*(?:\d*\.?\s*|{_ROMAN}\s*)literature\s+cited:?\s*$", re.IGNORECASE | re.MULTILINE),
]

# ── Split individual entries inside a references block ──────────────────────
# Ordered by specificity — first splitter that yields > 1 part wins.
_ENTRY_SPLITTERS: List[re.Pattern] = [
    re.compile(r"(?=\n\s*\[\d+\])"),           # [1]  [2]  [3]
    re.compile(r"(?=\n\s*\d{1,3}\.\s+[A-Z])"), # 1.  2.  (followed by capital)
    re.compile(r"(?=\n\s*\d{1,3}\s+[A-Z])"),   # 1  2   (followed by capital)
]

# APA author-date: each entry starts at a line beginning with "LastName, Initial"
_APA_AUTHOR_START = re.compile(r"^[A-Z][a-zA-Z\u00C0-\u017E\-]{1,30},\s+[A-Z]")

# ── DOI extraction ─────────────────────────────────────────────────────────
# Priority 1: DOI embedded in a URL  https://doi.org/10.xxx/yyy
_DOI_URL_RE = re.compile(r"doi\.org[/:]?\s*(10\.\d{4,}/[^\s\)\]>]+)", re.IGNORECASE)
# Priority 2: Labelled  doi: 10.xxx/yyy  or  DOI: 10.xxx/yyy
_DOI_LABEL_RE = re.compile(r"\bdoi\s*[:\s]\s*(10\.\d{4,}/[^\s\)\]>]+)", re.IGNORECASE)
# Priority 3: Bare DOI anywhere in text
_DOI_BARE_RE = re.compile(r"\b(10\.\d{4,}/[^\s\)\]>,]+)")

# ── Title extraction ───────────────────────────────────────────────────────
_TITLE_QUOTED_RE = re.compile(
    r'["\u201c\u201d\u2018\u2019](.{10,150}?)["\u201c\u201d\u2018\u2019]'
)
_TITLE_CAPS_RE = re.compile(r"[A-Z][A-Za-z ,\-:]{15,120}[A-Za-z]")

# Minimum fuzzy ratio to accept a title match
_FUZZY_THRESHOLD = 0.72


def _split_apa(ref_text: str) -> List[str]:
    """
    Split APA-style reference block by detecting lines that start a new entry.
    An entry starts when a line begins with 'LastName, Initial' (capital + letters + comma).
    """
    lines = ref_text.split("\n")
    entries: List[str] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if _APA_AUTHOR_START.match(stripped) and current:
            entries.append(" ".join(current))
            current = [stripped]
        elif stripped:
            current.append(stripped)

    if current:
        entries.append(" ".join(current))

    return [e for e in entries if len(e) >= 20]


class CitationExtractor:
    """Extracts, parses, and links citations from a paper's reference list."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def extract_and_link(self, citing_paper_id: int, pdf_text: str) -> int:
        """
        Full pipeline: extract → parse → match → create Citation records
        and store all references (matched + unmatched) in paper.references_list.

        Args:
            citing_paper_id: PK of the paper whose PDF was just processed.
            pdf_text:         Full extracted text of that PDF.

        Returns:
            Number of new Citation records created.
        """
        from apps.papers.models import Paper, Citation

        try:
            citing_paper = Paper.objects.get(id=citing_paper_id)
        except Paper.DoesNotExist:
            logger.warning("CitationExtractor: paper %s not found.", citing_paper_id)
            return 0

        ref_text = self._extract_references_text(pdf_text)
        if not ref_text:
            logger.info(
                "CitationExtractor: no references section found in paper %s.",
                citing_paper_id,
            )
            return 0

        entries = self._parse_entries(ref_text)
        logger.info(
            "CitationExtractor: parsed %d reference entries from paper %s.",
            len(entries), citing_paper_id,
        )

        # Match entries to internal papers and annotate each entry with result
        matched_by_id: Dict[int, "Paper"] = {}
        all_papers_cache: Optional[List] = None

        references_list = []
        for entry in entries:
            paper = None

            if entry.get("doi"):
                paper = Paper.objects.filter(doi__iexact=entry["doi"]).first()

            if not paper and entry.get("title"):
                paper = Paper.objects.filter(
                    title__icontains=entry["title"][:80], is_approved=True
                ).first()

            if not paper:
                if all_papers_cache is None:
                    all_papers_cache = list(
                        Paper.objects.filter(is_approved=True)
                        .exclude(id=citing_paper_id)
                        .values_list("id", "title")
                    )
                raw_lower = entry["raw"].lower()
                best_score, best_id = 0.0, None
                for pid, ptitle in all_papers_cache:
                    score = SequenceMatcher(None, ptitle.lower(), raw_lower).ratio()
                    if score > best_score:
                        best_score, best_id = score, pid
                if best_score >= _FUZZY_THRESHOLD and best_id:
                    try:
                        paper = Paper.objects.get(id=best_id)
                    except Paper.DoesNotExist:
                        pass

            ref_entry = {
                "raw": entry["raw"],
                "doi": entry.get("doi"),
                "title": entry.get("title"),
                "internal_paper_id": None,
            }

            if paper and paper.id != citing_paper_id:
                ref_entry["internal_paper_id"] = paper.id
                ref_entry["title"] = ref_entry["title"] or paper.title
                matched_by_id[paper.id] = paper

            references_list.append(ref_entry)

        # Persist all parsed references (including unmatched) to the paper
        Paper.objects.filter(id=citing_paper_id).update(references_list=references_list)

        # Create Citation records for internal matches
        created = 0
        for cited_paper in matched_by_id.values():
            _, was_created = Citation.objects.get_or_create(
                citing_paper=citing_paper,
                cited_paper=cited_paper,
            )
            if was_created:
                created += 1

        logger.info(
            "CitationExtractor: %d refs saved, %d internal Citation records created for paper %s.",
            len(references_list), created, citing_paper_id,
        )
        return created

    # ------------------------------------------------------------------
    # Step 1 — Isolate the references block
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_references_text(text: str) -> str:
        """Return the raw text starting from the first references header."""
        earliest_start: Optional[int] = None
        for pattern in _REF_START_PATTERNS:
            m = pattern.search(text)
            if m and (earliest_start is None or m.start() < earliest_start):
                earliest_start = m.start()

        if earliest_start is None:
            return ""

        # Skip past the header line itself
        newline_pos = text.find("\n", earliest_start)
        if newline_pos == -1:
            return ""
        return text[newline_pos:].strip()

    # ------------------------------------------------------------------
    # Step 2 — Parse individual reference entries
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_entries(ref_text: str) -> List[Dict]:
        """
        Split reference block into individual entries.
        Extract DOI and title hint from each.
        """
        # Try each numbered splitter; use the one yielding the most entries
        best: List[str] = []
        for pattern in _ENTRY_SPLITTERS:
            parts = [p.strip() for p in pattern.split(ref_text) if p.strip()]
            if len(parts) > len(best):
                best = parts

        # APA author-date fallback: group lines by author-start pattern
        if len(best) <= 1:
            best = _split_apa(ref_text)

        # Last resort: treat whole block as one entry
        if len(best) <= 1:
            best = [ref_text.strip()]

        results: List[Dict] = []
        for entry in best:
            # Collapse internal whitespace / newlines within an entry
            entry_clean = " ".join(entry.split())
            if len(entry_clean) < 20:
                continue  # too short to be a real reference

            # ── DOI extraction (three-pass priority) ──────────────────
            doi: Optional[str] = None

            # Pass 1: from doi.org URL — most reliable, avoids markdown junk
            m = _DOI_URL_RE.search(entry_clean)
            if m:
                doi = m.group(1).rstrip(".,;)>]")

            # Pass 2: labelled "doi: 10.xxx"
            if not doi:
                m = _DOI_LABEL_RE.search(entry_clean)
                if m:
                    doi = m.group(1).rstrip(".,;)>]")

            # Pass 3: bare 10.xxx anywhere
            if not doi:
                m = _DOI_BARE_RE.search(entry_clean)
                if m:
                    doi = m.group(1).rstrip(".,;)>]")

            # ── Title extraction ───────────────────────────────────────
            title: Optional[str] = None
            quoted_m = _TITLE_QUOTED_RE.search(entry_clean)
            if quoted_m:
                title = quoted_m.group(1).strip()
            else:
                caps_matches = _TITLE_CAPS_RE.findall(entry_clean)
                if caps_matches:
                    title = max(caps_matches, key=len).strip()

            results.append({"raw": entry_clean, "doi": doi, "title": title})

        return results

    # ------------------------------------------------------------------
    # Step 3 — Match entries to DB papers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_to_papers(entries: List[Dict], citing_paper_id: int):
        """
        Three-pass matching against approved papers in the DB.
        Returns a deduplicated list of matched Paper objects.
        """
        from apps.papers.models import Paper

        matched_ids: set = set()
        matched_papers = []

        # Lazy-load all approved papers once for fuzzy matching
        all_papers: Optional[List] = None

        for entry in entries:
            paper = None

            # Pass 1 — exact DOI
            if entry.get("doi"):
                paper = Paper.objects.filter(doi__iexact=entry["doi"]).first()

            # Pass 2 — exact title substring (first 80 chars to tolerate truncation)
            if not paper and entry.get("title"):
                title_fragment = entry["title"][:80]
                paper = Paper.objects.filter(
                    title__icontains=title_fragment, is_approved=True
                ).first()

            # Pass 3 — fuzzy title match over all approved papers
            if not paper:
                if all_papers is None:
                    all_papers = list(
                        Paper.objects.filter(is_approved=True)
                        .exclude(id=citing_paper_id)
                        .values_list("id", "title")
                    )
                raw_lower = entry["raw"].lower()
                best_score, best_id = 0.0, None
                for pid, ptitle in all_papers:
                    score = SequenceMatcher(None, ptitle.lower(), raw_lower).ratio()
                    if score > best_score:
                        best_score, best_id = score, pid
                if best_score >= _FUZZY_THRESHOLD and best_id:
                    try:
                        paper = Paper.objects.get(id=best_id)
                    except Paper.DoesNotExist:
                        pass

            if paper and paper.id != citing_paper_id and paper.id not in matched_ids:
                matched_ids.add(paper.id)
                matched_papers.append(paper)

        return matched_papers
