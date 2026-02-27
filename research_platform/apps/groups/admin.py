from django.contrib import admin
from .models import Group, GroupMember, GroupPaper

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'is_private', 'member_count', 'created_at']
    list_filter = ['is_private', 'created_at']
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_at']
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ['group', 'user', 'role', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['group__name', 'user__username', 'user__email']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group', 'user')

@admin.register(GroupPaper)
class GroupPaperAdmin(admin.ModelAdmin):
    list_display = ['group', 'paper', 'added_by', 'added_at']
    list_filter = ['added_at']
    search_fields = ['group__name', 'paper__title', 'added_by__username']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group', 'paper', 'added_by')
