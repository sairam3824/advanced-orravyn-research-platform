from django.contrib import admin
from .models import (
    PaperImpactMetrics, UserReadingStatistics, TrendingTopic,
    ResearchFieldAnalytics, CollaborationNetwork
)


@admin.register(PaperImpactMetrics)
class PaperImpactMetricsAdmin(admin.ModelAdmin):
    list_display = ['paper', 'impact_score', 'total_views', 'total_downloads', 'total_citations', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['paper__title']
    readonly_fields = ['updated_at']


@admin.register(UserReadingStatistics)
class UserReadingStatisticsAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_papers_read', 'papers_completed', 'reading_streak_days', 'updated_at']
    list_filter = ['updated_at', 'reading_streak_days']
    search_fields = ['user__username']
    readonly_fields = ['updated_at']


@admin.register(TrendingTopic)
class TrendingTopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'trend_score', 'paper_count', 'view_count', 'week_start']
    list_filter = ['week_start', 'category']
    search_fields = ['name']
    ordering = ['-trend_score']


@admin.register(ResearchFieldAnalytics)
class ResearchFieldAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['field_name', 'total_papers', 'total_researchers', 'growth_rate', 'month']
    list_filter = ['month']
    search_fields = ['field_name']
    ordering = ['-month']


@admin.register(CollaborationNetwork)
class CollaborationNetworkAdmin(admin.ModelAdmin):
    list_display = ['user', 'collaborator', 'collaboration_count', 'strength_score', 'last_collaboration']
    list_filter = ['last_collaboration']
    search_fields = ['user__username', 'collaborator__username']
    filter_horizontal = ['shared_papers']
