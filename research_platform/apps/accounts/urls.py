from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # Publishers
    path('publishers/', views.PublishersListView.as_view(), name='publishers_list'),
    path('publishers/search/', views.publishers_search, name='publishers_search'),
    path('publishers/<int:pk>/', views.PublisherDetailView.as_view(), name='publisher_detail'),
    
    # User profiles
    path('user/<int:pk>/', views.UserPublicProfileView.as_view(), name='user_profile'),
    
    # Follow/Unfollow
    path('follow/<int:user_id>/', views.follow_user, name='follow_user'),

    # AJAX helpers
    path('check-username/', views.check_username, name='check_username'),
]
