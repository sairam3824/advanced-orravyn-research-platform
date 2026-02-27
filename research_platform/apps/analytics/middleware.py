from django.utils import timezone


class ActivityStreakMiddleware:
    """Update the user's daily streak on any platform visit (once per day, via session)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated and hasattr(request, 'session'):
            today_str = timezone.now().date().isoformat()
            if request.session.get('last_streak_update') != today_str:
                self._update_streak(request.user, today_str)
                request.session['last_streak_update'] = today_str

        return response

    def _update_streak(self, user, today_str):
        from apps.analytics.models import UserReadingStatistics
        today = timezone.now().date()

        stats, created = UserReadingStatistics.objects.get_or_create(user=user)
        if created:
            stats.reading_streak_days = 1
            stats.last_read_date = today
            stats.save(update_fields=['reading_streak_days', 'last_read_date'])
            return

        if stats.last_read_date == today:
            return  # Already counted today

        if stats.last_read_date:
            delta = (today - stats.last_read_date).days
            if delta == 1:
                stats.reading_streak_days += 1
            else:
                stats.reading_streak_days = 1
        else:
            stats.reading_streak_days = 1

        stats.last_read_date = today
        stats.save(update_fields=['reading_streak_days', 'last_read_date'])
