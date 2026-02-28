# apps/papers/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Paper, ReadingProgress, PaperView
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


@receiver(post_save, sender=Paper)
def generate_summary(sender, instance, created, **kwargs):
    if created and instance.pdf_path:
        executor.submit(process_summary, instance.id, instance.pdf_path)


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
