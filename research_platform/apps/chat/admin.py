from django.contrib import admin
from .models import ChatRoom, ChatMessage

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['paper', 'created_by', 'is_active', 'message_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['paper__title', 'created_by__username']
    readonly_fields = ['created_at']
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['room', 'user', 'is_bot_message', 'timestamp']
    list_filter = ['is_bot_message', 'timestamp']
    search_fields = ['room__paper__title', 'user__username', 'message']
    readonly_fields = ['timestamp']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('room', 'user')
