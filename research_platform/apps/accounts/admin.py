from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile, SearchHistory, SavedSearch, UserFollow, ResearchInterestTag, UserResearchInterest

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'user_type', 'is_active', 'created_at']
    list_filter = ['user_type', 'is_active', 'created_at']
    search_fields = ['username', 'email']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('user_type',)}),
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'first_name', 'last_name', 'institution', 'is_credentials_verified', 'h_index']
    list_filter = ['is_credentials_verified']
    search_fields = ['user__username', 'first_name', 'last_name', 'institution', 'orcid']
    readonly_fields = ['user']

@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'query', 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['user__username', 'query']
    readonly_fields = ['user', 'query', 'timestamp']

@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'query', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'user__username', 'query']
    readonly_fields = ['created_at']

@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'created_at']
    list_filter = ['created_at']
    search_fields = ['follower__username', 'following__username']
    readonly_fields = ['created_at']

@admin.register(ResearchInterestTag)
class ResearchInterestTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']

@admin.register(UserResearchInterest)
class UserResearchInterestAdmin(admin.ModelAdmin):
    list_display = ['user', 'tag']
    list_filter = ['tag']
    search_fields = ['user__username', 'tag__name']
