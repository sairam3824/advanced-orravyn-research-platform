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


class YggdrasilConversation(models.Model):
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='ygg_conversations'
    )
    title = models.CharField(max_length=80, default='New conversation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'yggdrasil_conversations'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username}: {self.title}"


class YggdrasilMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_BOT = 'bot'
    ROLE_CHOICES = [(ROLE_USER, 'User'), (ROLE_BOT, 'Bot')]

    conversation = models.ForeignKey(
        YggdrasilConversation, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    faithfulness_score = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'yggdrasil_messages'
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"


class ResearchSession(models.Model):
    """
    Persists multi-turn research sessions for the MemoryAgent.

    Each session stores a JSON list of {"role": "user"|"assistant", "content": str}
    turn-pairs so the ResearchOrchestrator can inject prior context into
    the PlannerAgent and SynthesizerAgent prompts.
    """
    user       = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE,
        related_name='research_sessions', null=True, blank=True,
    )
    session_id  = models.CharField(max_length=64, unique=True, db_index=True)
    turns       = models.JSONField(default=list, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'research_sessions'
        ordering = ['-updated_at']

    def __str__(self):
        n = len(self.turns or []) // 2
        return f"Session {self.session_id[:8]}… ({n} turns)"



class AgentDecisionLog(models.Model):
    """
    Logs agent decisions for explainability and debugging.
    
    Tracks which agents made which decisions during query processing,
    enabling transparency and counterfactual analysis.
    """
    query_id = models.CharField(max_length=64, db_index=True)
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_decisions'
    )
    
    # Decision details
    agent_name = models.CharField(max_length=100)
    decision_type = models.CharField(max_length=100)  # e.g., "retrieve", "filter", "synthesize"
    reasoning = models.TextField()
    confidence = models.FloatField()
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Performance
    latency_ms = models.FloatField(null=True, blank=True)
    
    class Meta:
        db_table = 'agent_decision_logs'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['query_id', 'timestamp']),
            models.Index(fields=['session_id', 'timestamp']),
            models.Index(fields=['agent_name']),
        ]
    
    def __str__(self):
        return f"{self.agent_name}: {self.decision_type} (confidence={self.confidence:.2f})"
