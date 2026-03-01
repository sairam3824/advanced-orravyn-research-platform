from django.contrib import admin
from .models import UserRecommendation, PaperEmbedding, RecommendationModel


@admin.register(UserRecommendation)
class UserRecommendationAdmin(admin.ModelAdmin):
    list_display = ['user', 'paper', 'score', 'reason', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'paper__title']
    ordering = ['-score']
    readonly_fields = ['created_at']


@admin.register(PaperEmbedding)
class PaperEmbeddingAdmin(admin.ModelAdmin):
    list_display = ['paper', 'model_version', 'created_at']
    list_filter = ['model_version']
    search_fields = ['paper__title']
    readonly_fields = ['created_at']


@admin.register(RecommendationModel)
class RecommendationModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'is_active', 'created_at']
    list_filter = ['is_active']
