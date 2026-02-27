from django.db import models
from django.utils import timezone
from apps.accounts.models import User

class Group(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(default=timezone.now)
    is_private = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'groups'
    
    def __str__(self):
        return self.name

class GroupMember(models.Model):
    ROLES = [
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('member', 'Member'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=20, choices=ROLES, default='member')
    joined_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'group_members'
        unique_together = ['group', 'user']

class GroupPaper(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='papers')
    paper = models.ForeignKey('papers.Paper', on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    added_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'group_papers'
        unique_together = ['group', 'paper']
