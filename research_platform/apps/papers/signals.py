# apps/papers/signals.py
import logging
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from .models import Paper, ReadingProgress, PaperView, Rating, Bookmark
from .background import executor

logger = logging.getLogger(__name__)


def _log_future_error(future, task_name: str):
    """Attach a done-callback so background task failures are always logged."""
    def _callback(f):
        exc = f.exception()
        if exc:
            logger.error("Background task '%s' failed: %s", task_name, exc)
    future.add_done_callback(_callback)


def process_summary(paper_id, pdf_file):
    from ml_models.summary import summarize_text_from_pdf
    from apps.ml_engine.section_summarizer import SectionAwareSummarizer
    from apps.ml_engine.pdf_text_extractor import extract_pdf_text_from_path
    from .models import Paper
    try:
        # Get filesystem path from FieldFile; works for local storage backends.
        # Falls back to webhook summarizer if .path raises (e.g. cloud storage).
        pdf_text = ""
        try:
            pdf_text = extract_pdf_text_from_path(pdf_file.path)
        except Exception as path_err:
            logger.warning("Could not read PDF by path for Paper %s: %s", paper_id, path_err)

        if pdf_text and len(pdf_text.split()) > 100:
            summarizer = SectionAwareSummarizer()
            result = summarizer.summarize_paper(pdf_text)
            Paper.objects.filter(id=paper_id).update(
                summary=result["final_summary"],
                section_summaries=result["section_summaries"] or None,
            )
        else:
            # Fallback: send raw PDF bytes to webhook summarizer
            summary = summarize_text_from_pdf(pdf_file)
            Paper.objects.filter(id=paper_id).update(summary=summary)
    except Exception as e:
        logger.error("Failed to generate summary for Paper %s: %s", paper_id, e)
        # Last-resort fallback
        try:
            summary = summarize_text_from_pdf(pdf_file)
            Paper.objects.filter(id=paper_id).update(summary=summary)
        except Exception as e2:
            # GAP-4: mark the paper so the template shows a permanent failure
            # message instead of a spinner that never resolves.
            logger.error("Fallback summary also failed for Paper %s: %s", paper_id, e2)
            Paper.objects.filter(id=paper_id).update(summary="__summary_failed__")


def process_citations(paper_id, pdf_file):
    """Extract reference list from PDF and auto-create Citation records."""
    from apps.ml_engine.citation_extractor import CitationExtractor
    from apps.ml_engine.pdf_text_extractor import extract_pdf_text_from_path
    try:
        pdf_text = extract_pdf_text_from_path(pdf_file.path)
        if pdf_text:
            CitationExtractor().extract_and_link(paper_id, pdf_text)
    except Exception as e:
        logger.error("Failed to extract citations for Paper %s: %s", paper_id, e)


def process_vector_indexing(paper_id):
    from apps.ml_engine.vector_store import index_paper
    try:
        index_paper(paper_id)
    except Exception as e:
        logger.error("Failed to index Paper %s in vector store: %s", paper_id, e)


@receiver(post_save, sender=Paper)
def generate_summary(sender, instance, created, **kwargs):
    if created and instance.pdf_path:
        _log_future_error(
            executor.submit(process_summary, instance.id, instance.pdf_path),
            f"process_summary(paper={instance.id})"
        )
        _log_future_error(
            executor.submit(process_citations, instance.id, instance.pdf_path),
            f"process_citations(paper={instance.id})"
        )


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
        _log_future_error(
            executor.submit(process_vector_indexing, instance.id),
            f"process_vector_indexing(paper={instance.id})"
        )
        _log_future_error(
            executor.submit(process_ml_embedding, instance.id),
            f"process_ml_embedding(paper={instance.id})"
        )


@receiver(post_save, sender=Rating)
def update_recommendations_on_rating(sender, instance, **kwargs):
    """Refresh recommendations when user rates a paper 4 or higher."""
    if instance.rating >= 4:
        _log_future_error(
            executor.submit(refresh_recommendations, instance.user_id),
            f"refresh_recommendations(user={instance.user_id})"
        )


@receiver(post_save, sender=Bookmark)
def update_recommendations_on_bookmark(sender, instance, created, **kwargs):
    """Refresh recommendations when user bookmarks a paper."""
    if created:
        _log_future_error(
            executor.submit(refresh_recommendations, instance.user_id),
            f"refresh_recommendations(user={instance.user_id})"
        )


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


def _remove_from_vector_store(paper_id: int) -> None:
    from apps.ml_engine.vector_store import remove_paper
    try:
        remove_paper(paper_id)
    except Exception as exc:
        logger.error("Failed to remove Paper %s from vector store: %s", paper_id, exc)


@receiver(post_delete, sender=Paper)
def cleanup_paper_on_delete(sender, instance, **kwargs):
    """Remove paper chunks from ChromaDB when a paper is deleted.

    Without this, deleted papers remain in the vector store indefinitely
    and pollute RAG retrieval results with stale content.
    """
    _log_future_error(
        executor.submit(_remove_from_vector_store, instance.id),
        f"_remove_from_vector_store(paper={instance.id})"
    )
