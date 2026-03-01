# apps/papers/signals.py
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Paper, ReadingProgress, PaperView, Rating, Bookmark
from .background import executor

logger = logging.getLogger(__name__)


def process_summary(paper_id, pdf_file):
    from ml_models.bart_summarizer_lambda import summarize_text_from_pdf
    from .models import Paper
    try:
        summary = summarize_text_from_pdf(pdf_file)
        Paper.objects.filter(id=paper_id).update(summary=summary)
    except Exception as e:
        logger.error("Failed to generate summary for Paper %s: %s", paper_id, e)


def process_vector_indexing(paper_id):
    from apps.ml_engine.vector_store import index_paper
    try:
        index_paper(paper_id)
    except Exception as e:
        logger.error("Failed to index Paper %s in vector store: %s", paper_id, e)


@receiver(post_save, sender=Paper)
def generate_summary(sender, instance, created, **kwargs):
    if created and instance.pdf_path:
        executor.submit(process_summary, instance.id, instance.pdf_path)


@receiver(pre_save, sender=Paper)
def capture_approval_state(sender, instance, **kwargs):
    """Store previous is_approved value so post_save can detect the transition."""
    if instance.pk:
        try:
            instance._was_approved = Paper.objects.get(pk=instance.pk).is_approved
        except Paper.DoesNotExist:
            instance._was_approved = False
    else:
        instance._was_approved = False


def process_ml_embedding(paper_id):
    from apps.ml_engine.tasks import process_paper_upload
    try:
        process_paper_upload(paper_id)
    except Exception as e:
        logger.error("Failed to build ML embedding for Paper %s: %s", paper_id, e)


def refresh_recommendations(user_id):
    from apps.ml_engine.tasks import generate_recommendations
    try:
        generate_recommendations(user_id)
    except Exception as e:
        logger.error("Failed to refresh recommendations for user %s: %s", user_id, e)


@receiver(post_save, sender=Paper)
def index_paper_on_approval(sender, instance, created, **kwargs):
    """Index paper into ChromaDB and build ML embeddings when it transitions to approved."""
    was_approved = getattr(instance, "_was_approved", False)
    just_approved = instance.is_approved and (created or not was_approved)
    if just_approved:
        executor.submit(process_vector_indexing, instance.id)
        executor.submit(process_ml_embedding, instance.id)


@receiver(post_save, sender=Rating)
def update_recommendations_on_rating(sender, instance, **kwargs):
    """Refresh recommendations when user rates a paper 4 or higher."""
    if instance.rating >= 4:
        executor.submit(refresh_recommendations, instance.user_id)


@receiver(post_save, sender=Bookmark)
def update_recommendations_on_bookmark(sender, instance, created, **kwargs):
    """Refresh recommendations when user bookmarks a paper."""
    if created:
        executor.submit(refresh_recommendations, instance.user_id)


@receiver(post_save, sender=ReadingProgress)
def sync_reading_statistics(sender, instance, **kwargs):
    """Recalculate UserReadingStatistics whenever a ReadingProgress record is saved."""
    from apps.analytics.models import UserReadingStatistics
    from django.db.models import Sum

    stats, _ = UserReadingStatistics.objects.get_or_create(user=instance.user)

    user_progress = ReadingProgress.objects.filter(user=instance.user)
    stats.total_papers_read = PaperView.objects.filter(user=instance.user).count()
    stats.papers_completed = user_progress.filter(completed=True).count()
    stats.total_reading_time_minutes = user_progress.aggregate(
        total=Sum('reading_time_minutes'))['total'] or 0

    # Rebuild favorite categories from papers the user has read
    category_counts = {}
    for progress in user_progress.prefetch_related('paper__categories'):
        for cat in progress.paper.categories.all():
            category_counts[cat.name] = category_counts.get(cat.name, 0) + 1
    if category_counts:
        stats.favorite_categories = sorted(category_counts, key=category_counts.get, reverse=True)[:5]

    stats.save()
