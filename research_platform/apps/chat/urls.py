from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('paper/<int:paper_id>/', views.ChatRoomView.as_view(), name='paper_chat'),
    path('room/<int:room_id>/', views.ChatDetailView.as_view(), name='room_detail'),
    path('ajax/send/<int:room_id>/', views.send_message_ajax, name='send_message_ajax'),
    path('my-chats/', views.MyChatRoomsView.as_view(), name='my_chats'),
    path('group/<int:group_id>/', views.GroupChatRoomView.as_view(), name='group_chat'),
    path('500/', views.errorView, name='500'),
    path('yggdrasil_chatbot/', views.yggdrasil_chatbot_view, name='yggdrasil_chatbot'),
]
