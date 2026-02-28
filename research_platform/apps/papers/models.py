from django.db import models
from django.db.models import Avg
from django.utils import timezone
from apps.accounts.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name

class Paper(models.Model):
    title = models.CharField(max_length=500)
    abstract = models.TextField()
    authors = models.TextField()
    publication_date = models.DateField()
    doi = models.CharField(max_length=100, blank=True,null=True, unique=True)
    pdf_path = models.FileField(upload_to='papers/pdfs/', blank=True, null=True, max_length=500)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_papers')
    categories = models.ManyToManyField(Category, through='PaperCategory')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=False)
    download_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    summary = models.TextField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'papers'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def average_rating(self):
        return self.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
    
    @property
    def citation_count(self):
        return self.cited_by.count()

class PaperCategory(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'paper_categories'
        unique_together = ['paper', 'category']

class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(default=timezone.now)
    folder = models.CharField(max_length=100, default='default')
    
    class Meta:
        db_table = 'bookmarks'
        unique_together = ['user', 'paper']

class Citation(models.Model):
    citing_paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='citations')
    cited_paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='cited_by')
    
    class Meta:
        db_table = 'citations'
        unique_together = ['citing_paper', 'cited_paper']

class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings')
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='ratings')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'ratings'
        unique_together = ['user', 'paper']

class ReadingProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE)
    progress_percentage = models.FloatField(default=0.0)
    last_page = models.IntegerField(default=1)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    reading_time_minutes = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'reading_progress'
        unique_together = ['user', 'paper']


class PaperVersion(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    pdf_path = models.FileField(upload_to='papers/versions/', max_length=500)
    changes_description = models.TextField()
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'paper_versions'
        unique_together = ['paper', 'version_number']
        ordering = ['-version_number']
    
    def __str__(self):
        return f"{self.paper.title} - v{self.version_number}"


class RelatedPaper(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='related_papers')
    related_to = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='related_from')
    similarity_score = models.FloatField(default=0.0)
    relation_type = models.CharField(max_length=50, choices=[
        ('similar', 'Similar Topic'),
        ('cited', 'Cited By'),
        ('cites', 'Cites'),
        ('same_author', 'Same Author'),
    ])
    
    class Meta:
        db_table = 'related_papers'
        unique_together = ['paper', 'related_to']


class PaperAnnotation(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='annotations')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    page_number = models.IntegerField()
    annotation_text = models.TextField()
    highlight_text = models.TextField(blank=True)
    position_data = models.JSONField(default=dict)  # Store coordinates, color, etc.
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paper_annotations'
        ordering = ['page_number', 'created_at']


class ReadingList(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reading_lists')
    papers = models.ManyToManyField(Paper, through='ReadingListPaper')
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(User, related_name='shared_reading_lists', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reading_lists'
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name


class ReadingListPaper(models.Model):
    reading_list = models.ForeignKey(ReadingList, on_delete=models.CASCADE)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE)
    added_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'reading_list_papers'
        unique_together = ['reading_list', 'paper']
        ordering = ['-added_at']


class PaperCollection(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='paper_collections')
    papers = models.ManyToManyField(Paper, related_name='collections')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paper_collections'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} ({self.group.name})"


class ResearchProject(models.Model):
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField()
    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='research_projects')
    papers = models.ManyToManyField(Paper, related_name='research_projects', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    members = models.ManyToManyField(User, related_name='research_projects_member', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'research_projects'
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name


class ProjectTask(models.Model):
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    project = models.ForeignKey(ResearchProject, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'project_tasks'
        ordering = ['due_date', 'created_at']
    
    def __str__(self):
        return self.title

class PaperView(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'paper_views'
        unique_together = ['user', 'paper']


class CategoryRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(help_text='Brief description of what this category covers.')
    reason = models.TextField(help_text='Why should this category be added to the platform?')
    requested_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='category_requests'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_category_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'category_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.status}) — {self.requested_by.username}"



# ── Social Features ──────────────────────────────────────────────────

class PaperLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paper_likes')
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'paper_likes'
        unique_together = ['user', 'paper']
        ordering = ['-created_at']


class PaperShare(models.Model):
    PLATFORM_CHOICES = [
        ('twitter', 'Twitter'),
        ('linkedin', 'LinkedIn'),
        ('facebook', 'Facebook'),
        ('email', 'Email'),
        ('link', 'Copy Link'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paper_shares')
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='shares')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'paper_shares'
        ordering = ['-created_at']


class PaperComment(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paper_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField()
    is_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paper_comments'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.paper.title[:50]}"


class PeerReview(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('completed', 'Completed'),
    ]
    
    RECOMMENDATION_CHOICES = [
        ('accept', 'Accept'),
        ('minor_revision', 'Minor Revision'),
        ('major_revision', 'Major Revision'),
        ('reject', 'Reject'),
    ]
    
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='peer_reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, null=True, blank=True)
    
    # Review criteria
    originality_score = models.IntegerField(null=True, blank=True)  # 1-5
    methodology_score = models.IntegerField(null=True, blank=True)  # 1-5
    clarity_score = models.IntegerField(null=True, blank=True)  # 1-5
    significance_score = models.IntegerField(null=True, blank=True)  # 1-5
    
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    detailed_comments = models.TextField(blank=True)
    confidential_comments = models.TextField(blank=True)  # Only for editors
    
    is_anonymous = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'peer_reviews'
        unique_together = ['paper', 'reviewer']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.paper.title[:50]}"
    
    @property
    def overall_score(self):
        scores = [
            self.originality_score,
            self.methodology_score,
            self.clarity_score,
            self.significance_score
        ]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0


class ResearchBlogPost(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
    ]
    
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    content = models.TextField()
    excerpt = models.TextField(max_length=500, blank=True)
    featured_image = models.ImageField(upload_to='blog/', blank=True, null=True)
    related_papers = models.ManyToManyField(Paper, blank=True, related_name='blog_posts')
    tags = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_blog_posts')
    rejection_reason = models.TextField(blank=True)
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'research_blog_posts'
        ordering = ['-published_at', '-created_at']
    
    def __str__(self):
        return self.title


class BlogComment(models.Model):
    blog_post = models.ForeignKey(ResearchBlogPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'blog_comments'
        ordering = ['created_at']



# ── Tags and Labels ──────────────────────────────────────────────────

class PaperTag(models.Model):
    """Tags for organizing and categorizing papers"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#2563eb')  # Hex color
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tags')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'paper_tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PaperTagging(models.Model):
    """Many-to-many relationship between papers and tags"""
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='paper_tags')
    tag = models.ForeignKey(PaperTag, on_delete=models.CASCADE, related_name='tagged_papers')
    tagged_by = models.ForeignKey(User, on_delete=models.CASCADE)
    tagged_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'paper_tagging'
        unique_together = ['paper', 'tag']
    
    def __str__(self):
        return f"{self.paper.title} - {self.tag.name}"


# ── Paper Comparison ──────────────────────────────────────────────────

class PaperComparison(models.Model):
    """Store paper comparisons for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paper_comparisons')
    name = models.CharField(max_length=200)
    papers = models.ManyToManyField(Paper, related_name='comparisons')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paper_comparisons'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
