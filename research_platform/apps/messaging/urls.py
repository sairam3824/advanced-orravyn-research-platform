from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Conversations
    path('conversations/', views.ConversationListView.as_view(), name='conversations'),
    path('conversations/<int:pk>/', views.ConversationDetailView.as_view(), name='conversation_detail'),
    path('start/<int:user_id>/', views.start_conversation, name='start_conversation'),
    path('send/<int:conversation_id>/', views.send_message, name='send_message'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_read'),
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
]
