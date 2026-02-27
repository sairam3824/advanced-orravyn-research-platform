from django.urls import path
from . import views

app_name = 'groups'

urlpatterns = [
    path('', views.GroupListView.as_view(), name='list'),
    path('search/', views.group_search, name='search'),
    path('create/', views.GroupCreateView.as_view(), name='create'),
    path('<int:pk>/', views.GroupDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.GroupEditView.as_view(), name='edit'),
    path('<int:pk>/join/', views.join_group, name='join'),
    path('<int:pk>/leave/', views.leave_group, name='leave'),
    path('<int:pk>/add-paper/', views.add_paper_to_group, name='add_paper'),
    path('my-groups/', views.MyGroupsView.as_view(), name='my_groups'),
    
    path('<int:pk>/members/', views.GroupMembersView.as_view(), name='members'),
    path('<int:pk>/invite/', views.invite_member, name='invite_member'),
    path('<int:pk>/remove/<int:user_id>/', views.remove_member, name='remove_member'),
    path('<int:pk>/update-role/<int:user_id>/', views.update_member_role, name='update_role'),
    path('<int:pk>/delete/', views.delete_group, name='delete'),
]
