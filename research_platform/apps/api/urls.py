from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import UserRegistrationAPIView, login_api_view, UserProfileAPIView
from apps.papers.views import (
    PaperListCreateView, PaperDetailView, approve_paper,
    BookmarkListCreateView, RatingListCreateView, get_recommendations
)
from apps.search.views import PaperSearchView, search_suggestions

urlpatterns = [
    # Authentication API
    path('auth/register/', UserRegistrationAPIView.as_view(), name='api-register'),
    path('auth/login/', login_api_view, name='api-login'),
    path('auth/profile/', UserProfileAPIView.as_view(), name='api-profile'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    path('papers/', PaperListCreateView.as_view(), name='api-paper-list'),
    path('papers/<int:pk>/', PaperDetailView.as_view(), name='api-paper-detail'),
    path('papers/<int:pk>/approve/', approve_paper, name='api-approve-paper'),
    
    path('bookmarks/', BookmarkListCreateView.as_view(), name='api-bookmark-list'),
    path('ratings/', RatingListCreateView.as_view(), name='api-rating-list'),
    
    path('search/', PaperSearchView.as_view(), name='api-paper-search'),
    path('search/suggestions/', search_suggestions, name='api-search-suggestions'),
    
    path('recommendations/', get_recommendations, name='api-recommendations'),
]
