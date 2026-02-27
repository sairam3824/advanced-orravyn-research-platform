from django.db import models
from django.utils import timezone
from apps.accounts.models import User


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Conversation {self.id}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message from {self.sender.username}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('follow', 'New Follower'),
        ('paper', 'New Paper'),
        ('comment', 'New Comment'),
        ('rating', 'New Rating'),
        ('message', 'New Message'),
        ('mention', 'Mentioned'),
        ('project', 'Project Update'),
        ('task', 'Task Assigned'),
        ('annotation', 'New Annotation'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} for {self.user.username}"
