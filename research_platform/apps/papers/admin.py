from django.contrib import admin
from .models import (
    Paper, Category, Bookmark, Rating, Citation, ReadingProgress,
    PaperVersion, RelatedPaper, PaperAnnotation, ReadingList, ReadingListPaper,
    PaperCollection, ResearchProject, ProjectTask,
    PaperLike, PaperShare, PaperComment, PeerReview, ResearchBlogPost, BlogComment
)

@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ['title', 'uploaded_by', 'is_approved', 'view_count', 'download_count', 'created_at']
    list_filter = ['is_approved', 'created_at', 'categories']
    search_fields = ['title', 'authors', 'abstract']
    actions = ['approve_papers', 'reject_papers']
    
    def approve_papers(self, request, queryset):
        queryset.update(is_approved=True)
    approve_papers.short_description = "Approve selected papers"
    
    def reject_papers(self, request, queryset):
        queryset.update(is_approved=False)
    reject_papers.short_description = "Reject selected papers"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'paper', 'folder', 'created_at']
    list_filter = ['folder', 'created_at']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'paper', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']

@admin.register(Citation)
class CitationAdmin(admin.ModelAdmin):
    list_display = ['citing_paper', 'cited_paper']
    search_fields = ['citing_paper__title', 'cited_paper__title']

@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'paper', 'progress_percentage', 'completed', 'updated_at']
    list_filter = ['completed', 'updated_at']
    search_fields = ['user__username', 'paper__title']

@admin.register(PaperVersion)
class PaperVersionAdmin(admin.ModelAdmin):
    list_display = ['paper', 'version_number', 'uploaded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['paper__title']

@admin.register(RelatedPaper)
class RelatedPaperAdmin(admin.ModelAdmin):
    list_display = ['paper', 'related_to', 'relation_type', 'similarity_score']
    list_filter = ['relation_type']
    search_fields = ['paper__title', 'related_to__title']

@admin.register(PaperAnnotation)
class PaperAnnotationAdmin(admin.ModelAdmin):
    list_display = ['paper', 'user', 'page_number', 'is_public', 'created_at']
    list_filter = ['is_public', 'created_at']
    search_fields = ['paper__title', 'user__username', 'annotation_text']

@admin.register(ReadingList)
class ReadingListAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_public', 'created_at']
    list_filter = ['is_public', 'created_at']
    search_fields = ['name', 'owner__username']
    filter_horizontal = ['shared_with']

@admin.register(ReadingListPaper)
class ReadingListPaperAdmin(admin.ModelAdmin):
    list_display = ['reading_list', 'paper', 'added_at']
    list_filter = ['added_at']
    search_fields = ['reading_list__name', 'paper__title']

@admin.register(PaperCollection)
class PaperCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'group__name']
    filter_horizontal = ['papers']

@admin.register(ResearchProject)
class ResearchProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'group__name']
    filter_horizontal = ['papers', 'members']

@admin.register(ProjectTask)
class ProjectTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'assigned_to', 'status', 'due_date']
    list_filter = ['status', 'due_date']
    search_fields = ['title', 'project__name']



@admin.register(PaperLike)
class PaperLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'paper', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'paper__title']


@admin.register(PaperShare)
class PaperShareAdmin(admin.ModelAdmin):
    list_display = ['user', 'paper', 'platform', 'created_at']
    list_filter = ['platform', 'created_at']
    search_fields = ['user__username', 'paper__title']


@admin.register(PaperComment)
class PaperCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'paper', 'created_at', 'is_edited']
    list_filter = ['is_edited', 'created_at']
    search_fields = ['user__username', 'paper__title', 'content']


@admin.register(PeerReview)
class PeerReviewAdmin(admin.ModelAdmin):
    list_display = ['paper', 'reviewer', 'status', 'recommendation', 'overall_score', 'created_at']
    list_filter = ['status', 'recommendation', 'is_anonymous', 'created_at']
    search_fields = ['paper__title', 'reviewer__username']
    readonly_fields = ['created_at', 'overall_score']


@admin.register(ResearchBlogPost)
class ResearchBlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'status', 'is_approved', 'view_count', 'published_at']
    list_filter = ['status', 'is_approved', 'published_at', 'created_at']
    search_fields = ['title', 'author__username', 'content']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['related_papers']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.user_type in ['admin', 'moderator']:
            return qs
        return qs.filter(author=request.user)


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'blog_post', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'blog_post__title', 'content']
