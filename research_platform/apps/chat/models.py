from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.papers.models import Paper
from apps.groups.models import Group 

class ChatRoom(models.Model):
    paper = models.ForeignKey('papers.Paper', on_delete=models.CASCADE, related_name='chat_rooms', null=True, blank=True)
    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='chat_rooms', null=True, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'chat_rooms'
    
    def __str__(self):
        if self.paper:
            return f"Chat for paper: {self.paper.title}"
        elif self.group:
            return f"Chat for group: {self.group.name}"
        return "Chat Room"

class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_bot_message = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['timestamp']
    
    def __str__(self):
        username = self.user.username if self.user else "Bot"
        return f"{username}: {self.message[:50]}"