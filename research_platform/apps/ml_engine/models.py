from django.db import models
from apps.accounts.models import User
from apps.papers.models import Paper


class UserRecommendation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE)
    score = models.FloatField(default=0.0)
    reason = models.TextField(default="Recommended by hybrid model")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'paper')
        ordering = ['-score']


class RecommendationModel(models.Model):
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    model_path = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PaperEmbedding(models.Model):
    paper = models.OneToOneField(Paper, on_delete=models.CASCADE)
    embedding = models.JSONField(default=list)  # JSON array for vector
    model_version = models.CharField(max_length=50, default='tfidf-v1')
    created_at = models.DateTimeField(auto_now_add=True)
