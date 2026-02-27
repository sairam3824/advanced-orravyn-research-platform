from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    USER_TYPES = [
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('publisher', 'Publisher'),
        ('reader', 'Reader'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='reader')
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    institution = models.CharField(max_length=200, blank=True)
    research_interests = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # New fields for enhanced profile
    orcid = models.CharField(max_length=19, blank=True, help_text='ORCID iD (e.g., 0000-0002-1825-0097)')
    h_index = models.IntegerField(default=0, help_text='H-index score')
    is_credentials_verified = models.BooleanField(default=False)
    credentials_document = models.FileField(upload_to='credentials/', blank=True, null=True)
    website = models.URLField(blank=True)
    google_scholar = models.URLField(blank=True)
    research_gate = models.URLField(blank=True)
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class SearchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'search_history'
        ordering = ['-timestamp']


class SavedSearch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')
    name = models.CharField(max_length=200)
    query = models.TextField()
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'saved_searches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"


class UserFollow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'user_follows'
        unique_together = ['follower', 'following']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"


class ResearchInterestTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'research_interest_tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class UserResearchInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interest_tags')
    tag = models.ForeignKey(ResearchInterestTag, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'user_research_interests'
        unique_together = ['user', 'tag']
