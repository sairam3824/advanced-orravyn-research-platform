from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.papers.models import Paper


class PaperImpactMetrics(models.Model):
    paper = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='impact_metrics')
    total_views = models.IntegerField(default=0)
    total_downloads = models.IntegerField(default=0)
    total_citations = models.IntegerField(default=0)
    total_bookmarks = models.IntegerField(default=0)
    total_shares = models.IntegerField(default=0)
    total_likes = models.IntegerField(default=0)
    average_rating = models.FloatField(default=0.0)
    impact_score = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paper_impact_metrics'
    
    def calculate_impact_score(self):
        """Calculate overall impact score based on various metrics"""
        score = (
            (self.total_views * 0.1) +
            (self.total_downloads * 0.3) +
            (self.total_citations * 2.0) +
            (self.total_bookmarks * 0.5) +
            (self.total_shares * 0.7) +
            (self.total_likes * 0.2) +
            (self.average_rating * 10)
        )
        self.impact_score = round(score, 2)
        self.save()
        return self.impact_score


class UserReadingStatistics(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reading_stats')
    total_papers_read = models.IntegerField(default=0)
    total_reading_time_minutes = models.IntegerField(default=0)
    papers_completed = models.IntegerField(default=0)
    average_reading_speed = models.FloatField(default=0.0)  # pages per minute
    favorite_categories = models.JSONField(default=list)
    reading_streak_days = models.IntegerField(default=0)
    last_read_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_reading_statistics'


class TrendingTopic(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey('papers.Category', on_delete=models.SET_NULL, null=True, blank=True)
    paper_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    trend_score = models.FloatField(default=0.0)
    week_start = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'trending_topics'
        ordering = ['-trend_score', '-created_at']
        unique_together = ['name', 'week_start']
    
    def __str__(self):
        return f"{self.name} (Score: {self.trend_score})"


class ResearchFieldAnalytics(models.Model):
    field_name = models.CharField(max_length=200)
    total_papers = models.IntegerField(default=0)
    total_researchers = models.IntegerField(default=0)
    total_citations = models.IntegerField(default=0)
    growth_rate = models.FloatField(default=0.0)  # percentage
    top_keywords = models.JSONField(default=list)
    month = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'research_field_analytics'
        ordering = ['-month']
        unique_together = ['field_name', 'month']


class CollaborationNetwork(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collaboration_network')
    collaborator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collaborations')
    collaboration_count = models.IntegerField(default=0)
    shared_papers = models.ManyToManyField(Paper, blank=True)
    strength_score = models.FloatField(default=0.0)
    last_collaboration = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'collaboration_networks'
        unique_together = ['user', 'collaborator']
