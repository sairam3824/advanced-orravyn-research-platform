"""
Section-Aware classifier for research papers.

Detects standard IMRaD-style section headers via regex and splits
the paper text into per-section blocks. Falls back to evenly-split
chunks if no headers are found.
"""
import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Sections whose content should be stripped entirely (noise for summarization).
# GAP-1 fix: References, Acknowledgements, Appendix contaminated the last section.
# Covers Arabic numbers (5.), Roman numerals (VII.), and bare headings.
_NUM = r"(?:\d+\.?\s*|[IVXLCDM]+\.\s*)?"
_SKIP_PATTERNS: List[re.Pattern] = [
    re.compile(rf"^\s*{_NUM}references?\s*$",                 re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*{_NUM}bibliography\s*$",                 re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*{_NUM}acknowledgements?\s*$",            re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*{_NUM}appendix\s*[A-Z]?\s*$",           re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*{_NUM}supplementary\s+material\s*$",     re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*{_NUM}funding\s*$",                      re.IGNORECASE | re.MULTILINE),
    re.compile(rf"^\s*{_NUM}conflict[s]?\s+of\s+interest\s*$", re.IGNORECASE | re.MULTILINE),
]

# Ordered list of canonical section names and their regex patterns.
# Order matters: first match wins for a given header line.
_SECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Abstract",      re.compile(r"^\s*abstract\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Introduction",  re.compile(r"^\s*\d*\.?\s*introduction\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Related Work",  re.compile(r"^\s*\d*\.?\s*related\s+work\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Background",    re.compile(r"^\s*\d*\.?\s*background\s*$", re.IGNORECASE | re.MULTILINE)),
    # Compound methodology variants (e.g. "Filter Design Methodology", "System Design")
    ("Methodology",   re.compile(r"^\s*\d*\.?\s*(?:\w+\s+)*(?:design\s+)?methodolog(?:y|ies)\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Methodology",   re.compile(r"^\s*\d*\.?\s*(?:system|circuit|proposed)\s+design\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Methods",       re.compile(r"^\s*\d*\.?\s*methods?\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Experiments",   re.compile(r"^\s*\d*\.?\s*experiments?\s*$", re.IGNORECASE | re.MULTILINE)),
    # Compound results/evaluation variants (e.g. "Performance Evaluation", "Simulation Results")
    ("Results",       re.compile(r"^\s*\d*\.?\s*(?:\w+\s+)*(?:evaluation|results?|analysis)\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Results",       re.compile(r"^\s*\d*\.?\s*results?\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Discussion",    re.compile(r"^\s*\d*\.?\s*discussion\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Conclusion",    re.compile(r"^\s*\d*\.?\s*conclusions?\s*$", re.IGNORECASE | re.MULTILINE)),
]


class SectionClassifier:
    """Splits raw paper text into labelled sections."""

    def classify_sections(self, text: str) -> Dict[str, str]:
        """
        Detect section boundaries and return a mapping of section_name → section_text.

        Skip sections (References, Acknowledgements, Appendix, etc.) are detected
        and stripped before slicing so they don't contaminate adjacent sections.

        Duplicate section names (e.g. two Results sections) are merged by
        appending their text rather than dropping the second occurrence.

        If no standard headers are found, falls back to equal-split chunks
        labelled 'Part 1', 'Part 2', …

        Returns:
            dict[str, str]: {section_name: section_text, ...}
        """
        if not text or not text.strip():
            return {}

        # --- Build the skip-boundary offsets (GAP-1) ---
        skip_offsets: List[int] = []
        for pattern in _SKIP_PATTERNS:
            for match in pattern.finditer(text):
                skip_offsets.append(match.start())

        # Collect (char_offset, section_name) for every content-section header
        hits: List[Tuple[int, str]] = []
        for name, pattern in _SECTION_PATTERNS:
            for match in pattern.finditer(text):
                hits.append((match.start(), name))

        if not hits:
            # Still honour skip boundaries in fallback text
            clean_text = self._strip_from_offsets(text, skip_offsets)
            return self._fallback_split(clean_text)

        # Sort by position
        hits.sort(key=lambda x: x[0])

        # GAP-2 fix: merge duplicate section names instead of dropping them.
        # Build ordered list of (offset, name) allowing repeated names.
        ordered_hits: List[Tuple[int, str]] = hits

        # Slice text between consecutive section starts
        raw_sections: Dict[str, str] = {}
        for idx, (offset, name) in enumerate(ordered_hits):
            end = ordered_hits[idx + 1][0] if idx + 1 < len(ordered_hits) else len(text)

            # Truncate at the first skip-section boundary within this range
            for sk in skip_offsets:
                if offset < sk < end:
                    end = min(end, sk)

            section_text = text[offset:end].strip()
            # Strip the header line itself
            first_newline = section_text.find("\n")
            if first_newline != -1:
                section_text = section_text[first_newline:].strip()

            if not section_text:
                continue

            # Merge if this canonical name already has content (GAP-2)
            if name in raw_sections:
                raw_sections[name] = raw_sections[name] + "\n\n" + section_text
            else:
                raw_sections[name] = section_text

        return raw_sections if raw_sections else self._fallback_split(text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_from_offsets(text: str, offsets: List[int]) -> str:
        """Truncate text at the earliest skip-section offset, if any."""
        if not offsets:
            return text
        cut = min(offsets)
        return text[:cut].strip()

    @staticmethod
    def _fallback_split(text: str, n_parts: int = 4) -> Dict[str, str]:
        """Evenly split text into n_parts when no headers are detected."""
        words = text.split()
        if not words:
            return {}
        chunk_size = max(len(words) // n_parts, 1)
        sections: Dict[str, str] = {}
        for i in range(n_parts):
            start = i * chunk_size
            end = start + chunk_size if i < n_parts - 1 else len(words)
            chunk = " ".join(words[start:end]).strip()
            if chunk:
                sections[f"Part {i + 1}"] = chunk
        return sections
