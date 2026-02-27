from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Personal Dashboard
    path('dashboard/', views.PersonalDashboardView.as_view(), name='personal_dashboard'),
    
    # Paper Impact
    path('paper/<int:pk>/impact/', views.PaperImpactView.as_view(), name='paper_impact'),
    
    # Trending Topics
    path('trending/', views.TrendingTopicsView.as_view(), name='trending_topics'),
    path('trending/update/', views.update_trending_topics, name='update_trending'),
    
    # Research Field Analytics
    path('fields/', views.ResearchFieldAnalyticsView.as_view(), name='field_analytics'),
    
    # Collaboration Network
    path('network/', views.CollaborationNetworkView.as_view(), name='collaboration_network'),
    
    # API Endpoints
    path('api/reading-stats/', views.reading_statistics_api, name='reading_stats_api'),
]
