import logging
from .recommendation_engine import ImprovedRecommendationEngine

logger = logging.getLogger(__name__)

def process_paper_upload(paper_id):
    """Generate embeddings for a newly uploaded paper."""
    try:
        from apps.papers.models import Paper
        engine = ImprovedRecommendationEngine()
        paper = Paper.objects.get(id=paper_id)
        engine.build_embeddings()
        logger.info(f"Successfully processed paper {paper_id}")
        return {"status": "success", "paper_id": paper_id}
    except Exception as e:
        logger.error(f"Error processing paper {paper_id}: {str(e)}")
        return {"status": "error", "error": str(e)}

def generate_recommendations(user_id):
    """Generate and persist recommendations for a user."""
    try:
        from apps.accounts.models import User
        user = User.objects.get(id=user_id)
        engine = ImprovedRecommendationEngine()
        ranked = engine.hybrid_recommend(user)
        engine.save_recommendations(user, ranked)
        logger.info(f"Generated {len(ranked)} recommendations for user {user_id}")
        return {"status": "success", "count": len(ranked)}
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {str(e)}")
        return {"status": "error", "error": str(e)}
