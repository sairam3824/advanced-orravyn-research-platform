# apps/groups/signals.py
"""
Signals for Group-Guided Cold-Start Resolution (GG-CSR).

  GroupMember created  → immediately generate GG-CSR recommendations for
                         the new member (they are cold-start by definition
                         when first joining a group).

  GroupPaper created   → a new paper was shared into a group; refresh
                         recommendations for every cold-start member of
                         that group so they discover it right away.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.papers.background import executor
from .models import GroupMember, GroupPaper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _cold_start_user_ids(user_ids) -> list:
    """
    Return the subset of user_ids that are cold-start (no ratings, no bookmarks).

    Uses 2 bulk queries regardless of group size — avoids the N+1 pattern
    that calling _is_cold_start(user) per member would produce.
    """
    from apps.papers.models import Rating, Bookmark

    has_rating = set(
        Rating.objects.filter(user_id__in=user_ids)
        .values_list("user_id", flat=True)
        .distinct()
    )
    has_bookmark = set(
        Bookmark.objects.filter(user_id__in=user_ids)
        .values_list("user_id", flat=True)
        .distinct()
    )
    warm_ids = has_rating | has_bookmark
    return [uid for uid in user_ids if uid not in warm_ids]


def _refresh_recommendations(user_id: int) -> None:
    from apps.ml_engine.tasks import generate_recommendations
    try:
        generate_recommendations(user_id)
    except Exception as exc:
        logger.error("GG-CSR: failed to refresh recommendations for user %s: %s", user_id, exc)


# ---------------------------------------------------------------------------
# Signal: new member joins a group
# ---------------------------------------------------------------------------

@receiver(post_save, sender=GroupMember)
def on_group_member_join(sender, instance, created, **kwargs):
    """
    Trigger GG-CSR for a user the moment they join a research group.

    A new member has no personal history on the platform (cold-start),
    so we immediately bootstrap their recommendations from the group's
    collective paper activity.
    """
    if not created:
        return  # role changes etc. — skip

    user = instance.user
    logger.info(
        "GG-CSR: user %s joined group '%s' — scheduling recommendation refresh.",
        user.id, instance.group.name,
    )
    executor.submit(_refresh_recommendations, user.id)


# ---------------------------------------------------------------------------
# Signal: a paper is added to a group
# ---------------------------------------------------------------------------

@receiver(post_save, sender=GroupPaper)
def on_group_paper_added(sender, instance, created, **kwargs):
    """
    When a paper is shared into a group, refresh recommendations for every
    cold-start member of that group.

    Warm users (those with personal ratings/bookmarks) are not refreshed
    here — their recommendations update via the existing Rating/Bookmark
    signals in papers/signals.py.  We only target cold members because
    GG-CSR is their only signal source and a new group paper directly
    expands that signal.
    """
    if not created:
        return

    group = instance.group
    all_member_ids = list(
        GroupMember.objects.filter(group=group).values_list("user_id", flat=True)
    )
    cold_user_ids = _cold_start_user_ids(all_member_ids)

    if cold_user_ids:
        logger.info(
            "GG-CSR: paper '%s' added to group '%s' — refreshing %d cold-start member(s).",
            instance.paper_id, group.name, len(cold_user_ids),
        )
        for uid in cold_user_ids:
            executor.submit(_refresh_recommendations, uid)
