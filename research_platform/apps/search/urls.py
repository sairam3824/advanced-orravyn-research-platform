from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    path('', views.SearchView.as_view(), name='search'),
    path('advanced/', views.AdvancedSearchView.as_view(), name='advanced'),
    path('suggestions/', views.search_suggestions, name='suggestions'),
    path('history/', views.SearchHistoryView.as_view(), name='history'),
    path('live/', views.live_search, name='live'),
    
    # Saved searches
    path('saved/', views.SavedSearchListView.as_view(), name='saved_searches'),
    path('save/', views.save_search, name='save_search'),
    path('saved/<int:pk>/delete/', views.delete_saved_search, name='delete_saved_search'),
]
