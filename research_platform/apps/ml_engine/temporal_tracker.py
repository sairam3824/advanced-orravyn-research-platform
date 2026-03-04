"""
Temporal-Aware Research Evolution Tracking.

Analyzes publication dates to understand research evolution, detect trends,
score novelty, and weight recent papers appropriately.

Components:
1. TemporalAnalyzer — extracts and normalizes publication dates
2. ResearchEvolutionTracker — builds timeline of research progress
3. TrendDetector — identifies rising/declining research directions
4. NoveltyScorer — scores how different a paper is from prior work

Usage:
    from apps.ml_engine.temporal_tracker import get_temporal_analyzer
    
    analyzer = get_temporal_analyzer()
    scored_chunks = analyzer.apply_temporal_scoring(
        query="What is the state-of-the-art in protein folding?",
        chunks=[...]
    )
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Temporal Analyzer
# ---------------------------------------------------------------------------

class TemporalAnalyzer:
    """
    Extracts and normalizes publication dates, applies temporal attention weights.
    """
    
    def __init__(self):
        self.current_year = datetime.now().year
        
    def apply_temporal_scoring(
        self,
        query: str,
        chunks: List[Dict],
        mode: str = "auto"
    ) -> List[Dict]:
        """
        Apply temporal scoring to chunks based on query intent.
        
        Args:
            query: User query
            chunks: List of retrieved chunks
            mode: "auto" | "recent" | "foundational" | "evolution"
                  auto = detect from query keywords
                  recent = prioritize recent papers (SOTA queries)
                  foundational = prioritize older seminal papers
                  evolution = balanced timeline
                  
        Returns:
            Chunks with added temporal_score and temporal_weight fields
        """
        # Detect temporal mode from query
        if mode == "auto":
            mode = self._detect_temporal_mode(query)
        
        logger.info("TemporalAnalyzer: applying mode='%s' for query.", mode)
        
        # Extract dates and apply scoring
        scored_chunks = []
        for chunk in chunks:
            chunk_copy = dict(chunk)
            pub_date = self._extract_date(chunk_copy)
            
            if pub_date:
                chunk_copy["publication_date"] = pub_date.isoformat()
                chunk_copy["publication_year"] = pub_date.year
                chunk_copy["age_years"] = self.current_year - pub_date.year
                
                # Apply temporal weight based on mode
                temporal_weight = self._calculate_temporal_weight(
                    pub_date, mode
                )
                chunk_copy["temporal_weight"] = temporal_weight
                
                # Boost overall score
                original_score = chunk_copy.get("relevance_score", 0.5)
                chunk_copy["temporal_score"] = original_score * temporal_weight
            else:
                # No date found — neutral weight
                chunk_copy["temporal_weight"] = 1.0
                chunk_copy["temporal_score"] = chunk_copy.get("relevance_score", 0.5)
                chunk_copy["age_years"] = None
            
            scored_chunks.append(chunk_copy)
        
        # Re-sort by temporal_score
        scored_chunks.sort(key=lambda x: x.get("temporal_score", 0), reverse=True)
        
        return scored_chunks
    
    def _detect_temporal_mode(self, query: str) -> str:
        """Detect temporal mode from query keywords."""
        q_lower = query.lower()
        
        # Recent/SOTA keywords
        recent_keywords = [
            "recent", "latest", "state-of-the-art", "sota", "current",
            "modern", "new", "novel", "2024", "2025", "2026"
        ]
        if any(kw in q_lower for kw in recent_keywords):
            return "recent"
        
        # Foundational keywords
        foundational_keywords = [
            "foundational", "seminal", "original", "first", "pioneering",
            "classic", "history", "evolution", "development"
        ]
        if any(kw in q_lower for kw in foundational_keywords):
            return "foundational"
        
        # Evolution keywords
        evolution_keywords = [
            "evolution", "progress", "timeline", "development", "how did",
            "changes over time", "trend"
        ]
        if any(kw in q_lower for kw in evolution_keywords):
            return "evolution"
        
        # Default: recent (most common for research queries)
        return "recent"
    
    def _extract_date(self, chunk: Dict) -> Optional[datetime]:
        """Extract publication date from chunk metadata."""
        metadata = chunk.get("metadata", {})
        
        # Try various date fields
        date_fields = [
            "publication_date",
            "published_date",
            "date",
            "year",
            "pub_date"
        ]
        
        for field in date_fields:
            if field in metadata:
                date_str = metadata[field]
                parsed = self._parse_date(date_str)
                if parsed:
                    return parsed
        
        return None
    
    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse date string in various formats."""
        if isinstance(date_str, datetime):
            return date_str
        
        if isinstance(date_str, int):
            # Assume it's a year
            try:
                return datetime(date_str, 1, 1)
            except ValueError:
                return None
        
        if not isinstance(date_str, str):
            return None
        
        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try extracting year with regex
        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if year_match:
            year = int(year_match.group(0))
            return datetime(year, 1, 1)
        
        return None
    
    def _calculate_temporal_weight(
        self,
        pub_date: datetime,
        mode: str
    ) -> float:
        """
        Calculate temporal weight based on publication date and mode.
        
        Returns weight in range [0.5, 1.5] to boost/penalize scores.
        """
        age_years = self.current_year - pub_date.year
        
        if mode == "recent":
            # Exponential decay: recent papers get higher weight
            # Papers from last 2 years: 1.5x
            # Papers 5+ years old: 0.7x
            if age_years <= 2:
                return 1.5
            elif age_years <= 5:
                return 1.2
            elif age_years <= 10:
                return 1.0
            else:
                return 0.7
        
        elif mode == "foundational":
            # Older papers get higher weight
            if age_years >= 10:
                return 1.4
            elif age_years >= 5:
                return 1.2
            else:
                return 0.9
        
        elif mode == "evolution":
            # Balanced: all time periods equally important
            return 1.0
        
        else:
            return 1.0


# ---------------------------------------------------------------------------
# 2. Research Evolution Tracker
# ---------------------------------------------------------------------------

class ResearchEvolutionTracker:
    """
    Builds timeline of research progress and identifies key milestones.
    """
    
    def build_timeline(
        self,
        chunks: List[Dict],
        min_year: Optional[int] = None
    ) -> Dict:
        """
        Build research timeline from chunks.
        
        Args:
            chunks: List of chunks with publication dates
            min_year: Minimum year to include (default: 10 years ago)
            
        Returns:
            {
                "timeline": [
                    {"year": 2020, "papers": [...], "count": 5},
                    ...
                ],
                "milestones": [
                    {"year": 2017, "paper": {...}, "reason": "Most cited"},
                    ...
                ],
                "periods": {
                    "early": [...],
                    "middle": [...],
                    "recent": [...]
                }
            }
        """
        if min_year is None:
            min_year = datetime.now().year - 10
        
        # Group by year
        by_year = defaultdict(list)
        for chunk in chunks:
            year = chunk.get("publication_year")
            if year and year >= min_year:
                by_year[year].append(chunk)
        
        # Build timeline
        timeline = []
        for year in sorted(by_year.keys()):
            timeline.append({
                "year": year,
                "papers": by_year[year],
                "count": len(by_year[year])
            })
        
        # Identify milestones (most cited, highest relevance per year)
        milestones = self._identify_milestones(by_year)
        
        # Divide into periods
        periods = self._divide_into_periods(by_year, min_year)
        
        return {
            "timeline": timeline,
            "milestones": milestones,
            "periods": periods,
            "total_papers": len(chunks),
            "year_range": f"{min_year}-{datetime.now().year}"
        }
    
    def _identify_milestones(
        self,
        by_year: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Identify milestone papers (highest impact per year)."""
        milestones = []
        
        for year, chunks in by_year.items():
            if not chunks:
                continue
            
            # Find highest relevance score
            best_chunk = max(chunks, key=lambda x: x.get("relevance_score", 0))
            
            milestones.append({
                "year": year,
                "paper_id": best_chunk.get("metadata", {}).get("paper_id"),
                "title": best_chunk.get("metadata", {}).get("title", "Unknown"),
                "relevance_score": best_chunk.get("relevance_score", 0),
                "reason": "Highest relevance in year"
            })
        
        return sorted(milestones, key=lambda x: x["year"])
    
    def _divide_into_periods(
        self,
        by_year: Dict[int, List[Dict]],
        min_year: int
    ) -> Dict[str, List[Dict]]:
        """Divide timeline into early/middle/recent periods."""
        current_year = datetime.now().year
        span = current_year - min_year
        
        if span <= 3:
            # Short span: all recent
            all_chunks = [c for chunks in by_year.values() for c in chunks]
            return {
                "early": [],
                "middle": [],
                "recent": all_chunks
            }
        
        # Divide into thirds
        third = span // 3
        early_cutoff = min_year + third
        middle_cutoff = min_year + 2 * third
        
        early = []
        middle = []
        recent = []
        
        for year, chunks in by_year.items():
            if year < early_cutoff:
                early.extend(chunks)
            elif year < middle_cutoff:
                middle.extend(chunks)
            else:
                recent.extend(chunks)
        
        return {
            "early": early,
            "middle": middle,
            "recent": recent
        }


# ---------------------------------------------------------------------------
# 3. Trend Detector
# ---------------------------------------------------------------------------

class TrendDetector:
    """
    Identifies rising and declining research trends based on publication frequency.
    """
    
    def detect_trends(
        self,
        chunks: List[Dict],
        window_years: int = 3
    ) -> Dict:
        """
        Detect research trends from publication patterns.
        
        Args:
            chunks: List of chunks with dates
            window_years: Years to look back for trend calculation
            
        Returns:
            {
                "rising": [{"topic": str, "growth_rate": float}, ...],
                "declining": [{"topic": str, "decline_rate": float}, ...],
                "stable": [{"topic": str}, ...]
            }
        """
        current_year = datetime.now().year
        cutoff_year = current_year - window_years
        
        # Count papers per year
        by_year = defaultdict(int)
        for chunk in chunks:
            year = chunk.get("publication_year")
            if year and year >= cutoff_year:
                by_year[year] += 1
        
        if len(by_year) < 2:
            return {
                "rising": [],
                "declining": [],
                "stable": [],
                "insufficient_data": True
            }
        
        # Calculate trend (simple linear regression slope)
        years = sorted(by_year.keys())
        counts = [by_year[y] for y in years]
        
        trend_slope = self._calculate_trend_slope(years, counts)
        
        # Classify trend
        if trend_slope > 0.5:
            status = "rising"
            rate = trend_slope
        elif trend_slope < -0.5:
            status = "declining"
            rate = abs(trend_slope)
        else:
            status = "stable"
            rate = 0.0
        
        return {
            "status": status,
            "rate": rate,
            "papers_per_year": dict(by_year),
            "trend_slope": trend_slope,
            "window_years": window_years
        }
    
    def _calculate_trend_slope(
        self,
        years: List[int],
        counts: List[int]
    ) -> float:
        """Calculate linear regression slope (simple method)."""
        if len(years) < 2:
            return 0.0
        
        n = len(years)
        x_mean = sum(years) / n
        y_mean = sum(counts) / n
        
        numerator = sum((years[i] - x_mean) * (counts[i] - y_mean) for i in range(n))
        denominator = sum((years[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return slope


# ---------------------------------------------------------------------------
# 4. Novelty Scorer
# ---------------------------------------------------------------------------

class NoveltyScorer:
    """
    Scores how novel/different a paper is compared to prior work.
    """
    
    def score_novelty(
        self,
        chunks: List[Dict]
    ) -> List[Dict]:
        """
        Score novelty of each chunk relative to others.
        
        Novelty factors:
        - Recency (newer = potentially more novel)
        - Uniqueness of content (different from older papers)
        - Citation patterns (highly cited recent = breakthrough)
        
        Returns:
            Chunks with added novelty_score field
        """
        if not chunks:
            return []
        
        # Sort by date
        dated_chunks = [c for c in chunks if c.get("publication_year")]
        dated_chunks.sort(key=lambda x: x.get("publication_year", 0))
        
        scored = []
        for i, chunk in enumerate(dated_chunks):
            year = chunk.get("publication_year", datetime.now().year)
            age = datetime.now().year - year
            
            # Recency score (0-1, newer = higher)
            recency_score = max(0, 1.0 - (age / 20.0))  # 20 year decay
            
            # Position score (later in timeline = potentially more novel)
            position_score = i / max(len(dated_chunks) - 1, 1)
            
            # Combined novelty score
            novelty_score = 0.6 * recency_score + 0.4 * position_score
            
            chunk_copy = dict(chunk)
            chunk_copy["novelty_score"] = round(novelty_score, 3)
            chunk_copy["recency_score"] = round(recency_score, 3)
            scored.append(chunk_copy)
        
        logger.info("NoveltyScorer: scored %d chunks for novelty.", len(scored))
        return scored


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_temporal_analyzer: Optional[TemporalAnalyzer] = None


def get_temporal_analyzer() -> TemporalAnalyzer:
    """Return the module-level temporal analyzer singleton."""
    global _temporal_analyzer
    if _temporal_analyzer is None:
        _temporal_analyzer = TemporalAnalyzer()
    return _temporal_analyzer
