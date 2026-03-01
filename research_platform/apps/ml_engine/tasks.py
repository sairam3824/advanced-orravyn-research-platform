import logging
from .recommendation_engine import ImprovedRecommendationEngine

logger = logging.getLogger(__name__)


def process_paper_upload(paper_id):
    """Rebuild ML embeddings for all approved papers after a new paper is approved."""
    try:
        engine = ImprovedRecommendationEngine()
        engine.build_embeddings()
        logger.info(f"Rebuilt embeddings after paper {paper_id} was approved")
        return {"status": "success", "paper_id": paper_id}
    except Exception as e:
        logger.error(f"Error building embeddings for paper {paper_id}: {str(e)}")
        return {"status": "error", "error": str(e)}


def generate_recommendations(user_id):
    """Generate and persist recommendations for a user.
    Auto-builds embeddings first if none exist yet.
    """
    try:
        from apps.accounts.models import User
        from apps.ml_engine.models import PaperEmbedding
        user = User.objects.get(id=user_id)
        engine = ImprovedRecommendationEngine()

        # Bootstrap embeddings on first run if the table is empty
        if not PaperEmbedding.objects.exists():
            logger.info("No embeddings found — running initial build before generating recommendations")
            engine.build_embeddings()

        ranked = engine.hybrid_recommend(user)
        engine.save_recommendations(user, ranked)
        logger.info(f"Generated {len(ranked)} recommendations for user {user_id}")
        return {"status": "success", "count": len(ranked)}
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {str(e)}")
        return {"status": "error", "error": str(e)}


def rebuild_all_embeddings():
    """Rebuild embeddings for all approved papers. Run after bulk paper imports."""
    try:
        engine = ImprovedRecommendationEngine()
        engine.build_embeddings()
        logger.info("Successfully rebuilt all paper embeddings")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error rebuilding all embeddings: {str(e)}")
        return {"status": "error", "error": str(e)}
