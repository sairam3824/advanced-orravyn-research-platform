from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import (
    PaperImpactMetrics, UserReadingStatistics, TrendingTopic,
    ResearchFieldAnalytics, CollaborationNetwork
)
from apps.papers.models import Paper, Category
from apps.accounts.models import User, UserFollow


class PersonalDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/personal_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Reading statistics
        reading_stats, _ = UserReadingStatistics.objects.get_or_create(user=user)
        
        # Papers uploaded
        uploaded_papers = Paper.objects.filter(uploaded_by=user)
        
        # Impact metrics for user's papers
        total_views = sum(p.view_count for p in uploaded_papers)
        total_downloads = sum(p.download_count for p in uploaded_papers)
        total_citations = sum(p.citation_count for p in uploaded_papers)
        
        # Recent activity
        from apps.papers.models import ReadingProgress, Bookmark
        recent_reading = ReadingProgress.objects.filter(user=user).order_by('-updated_at')[:5]
        recent_bookmarks = Bookmark.objects.filter(user=user).order_by('-created_at')[:5]
        
        # Collaboration network
        collaborators = CollaborationNetwork.objects.filter(user=user).order_by('-strength_score')[:10]
        
        # Trending in user's interests
        if reading_stats.favorite_categories:
            trending = TrendingTopic.objects.filter(
                category__name__in=reading_stats.favorite_categories
            )[:5]
        else:
            trending = TrendingTopic.objects.all()[:5]
        
        context.update({
            'reading_stats': reading_stats,
            'uploaded_papers_count': uploaded_papers.count(),
            'total_views': total_views,
            'total_downloads': total_downloads,
            'total_citations': total_citations,
            'recent_reading': recent_reading,
            'recent_bookmarks': recent_bookmarks,
            'collaborators': collaborators,
            'trending_topics': trending,
        })
        
        return context


class PaperImpactView(LoginRequiredMixin, DetailView):
    model = Paper
    template_name = 'analytics/paper_impact.html'
    context_object_name = 'paper'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paper = self.object
        
        # Get or create impact metrics
        metrics, created = PaperImpactMetrics.objects.get_or_create(paper=paper)
        
        if created or (timezone.now() - metrics.updated_at).seconds > 3600:
            # Update metrics
            metrics.total_views = paper.view_count
            metrics.total_downloads = paper.download_count
            metrics.total_citations = paper.citation_count
            metrics.total_bookmarks = paper.bookmarked_by.count()
            
            from apps.papers.models import PaperShare, PaperLike
            metrics.total_shares = PaperShare.objects.filter(paper=paper).count()
            metrics.total_likes = PaperLike.objects.filter(paper=paper).count()
            
            ratings = paper.ratings.all()
            if ratings:
                metrics.average_rating = sum(r.rating for r in ratings) / len(ratings)
            
            metrics.calculate_impact_score()
        
        # Views over time (last 30 days)
        from apps.papers.models import PaperView
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_views = PaperView.objects.filter(
            paper=paper,
            viewed_at__gte=thirty_days_ago
        ).annotate(day=TruncDate('viewed_at')).values('day').annotate(count=Count('id'))
        
        context.update({
            'metrics': metrics,
            'daily_views': list(daily_views),
        })
        
        return context


class TrendingTopicsView(ListView):
    model = TrendingTopic
    template_name = 'analytics/trending_topics.html'
    context_object_name = 'topics'
    paginate_by = 20
    
    def get_queryset(self):
        # Get current week's trending topics
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        return TrendingTopic.objects.filter(week_start=week_start)


class ResearchFieldAnalyticsView(ListView):
    model = ResearchFieldAnalytics
    template_name = 'analytics/field_analytics.html'
    context_object_name = 'analytics'
    paginate_by = 20
    
    def get_queryset(self):
        # Get current month's analytics
        today = timezone.now().date()
        current_month = today.replace(day=1)
        return ResearchFieldAnalytics.objects.filter(month=current_month)


class CollaborationNetworkView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/collaboration_network.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get collaboration network
        collaborations = CollaborationNetwork.objects.filter(user=user).select_related('collaborator').prefetch_related('shared_papers')
        
        # Calculate stats
        total_collaborators = collaborations.count()
        total_collaborations = sum(c.collaboration_count for c in collaborations)
        shared_papers_count = sum(c.shared_papers.count() for c in collaborations)
        
        # Get social sharing stats (different from collaboration sharing)
        from apps.papers.models import PaperShare
        total_social_shares = PaperShare.objects.filter(user=user).count()
        
        # Build network data for visualization
        nodes = [{'id': user.id, 'name': user.username, 'type': 'self'}]
        edges = []
        
        for collab in collaborations:
            nodes.append({
                'id': collab.collaborator.id,
                'name': collab.collaborator.username,
                'type': 'collaborator'
            })
            edges.append({
                'source': user.id,
                'target': collab.collaborator.id,
                'weight': collab.strength_score
            })
        
        context.update({
            'collaborations': collaborations,
            'total_collaborators': total_collaborators,
            'total_collaborations': total_collaborations,
            'shared_papers_count': shared_papers_count,
            'total_social_shares': total_social_shares,
            'network_data': {
                'nodes': nodes,
                'edges': edges
            }
        })
        
        return context


@login_required
def reading_statistics_api(request):
    """API endpoint for reading statistics"""
    stats, _ = UserReadingStatistics.objects.get_or_create(user=request.user)
    
    return JsonResponse({
        'total_papers_read': stats.total_papers_read,
        'total_reading_time': stats.total_reading_time_minutes,
        'papers_completed': stats.papers_completed,
        'reading_streak': stats.reading_streak_days,
        'favorite_categories': stats.favorite_categories,
    })


@login_required
def update_trending_topics(request):
    """Background task to update trending topics"""
    if request.user.user_type not in ['admin', 'moderator']:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    seven_days_ago = today - timedelta(days=7)
    
    # Get papers from last week
    recent_papers = Paper.objects.filter(
        created_at__gte=seven_days_ago,
        is_approved=True
    )
    
    # Analyze categories
    category_stats = recent_papers.values('categories__name').annotate(
        paper_count=Count('id'),
        view_count=Sum('view_count')
    )
    
    for stat in category_stats:
        if stat['categories__name']:
            trend_score = (stat['paper_count'] * 10) + (stat['view_count'] * 0.1)
            
            TrendingTopic.objects.update_or_create(
                name=stat['categories__name'],
                week_start=week_start,
                defaults={
                    'paper_count': stat['paper_count'],
                    'view_count': stat['view_count'],
                    'trend_score': trend_score
                }
            )
    
    return JsonResponse({'success': True, 'message': 'Trending topics updated'})
