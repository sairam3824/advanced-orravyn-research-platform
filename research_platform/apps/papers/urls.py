from django.urls import path
from . import views

app_name = 'papers'

urlpatterns = [
    path('', views.PaperListView.as_view(), name='list'),
    path('upload/', views.PaperUploadView.as_view(), name='upload'),
    path('<int:pk>/', views.PaperDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.PaperEditView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.PaperDeleteView.as_view(), name='delete'),
    path('<int:pk>/bookmark/', views.bookmark_paper, name='bookmark'),
    path('<int:pk>/rate/', views.rate_paper, name='rate'),
    path('<int:pk>/view-pdf/', views.view_paper_pdf, name='view_pdf'),
    path('<int:pk>/download/', views.download_paper, name='download'),
    path('bookmarks/', views.BookmarkListView.as_view(), name='bookmarks'),
    path('my-papers/', views.MyPapersView.as_view(), name='my_papers'),
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('categories/search/', views.category_search, name='category_search'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('categories/request/', views.CategoryRequestCreateView.as_view(), name='request_category'),
    path('categories/requests/', views.CategoryRequestListView.as_view(), name='category_requests'),
    path('categories/requests/<int:pk>/approve/', views.approve_category_request, name='approve_category_request'),
    path('categories/requests/<int:pk>/reject/', views.reject_category_request, name='reject_category_request'),
    path('pending-approval/', views.PendingApprovalView.as_view(), name='pending_approval'),
    path('<int:pk>/approve/', views.approve_paper, name='approve'),
    path('<int:pk>/reject/', views.reject_paper, name='reject'),
    path('recommendations/', views.get_recommendations, name='recommendations'),
    path('admin-manage/', views.AdminPaperListView.as_view(), name='admin_paper_manage'),
    path('<int:pk>/summary/', views.PaperSummaryView.as_view(), name='summary'),
    
    # Advanced Features
    path('<int:pk>/export/<str:format>/', views.export_citation, name='export_citation'),
    path('<int:pk>/progress/', views.update_reading_progress, name='update_progress'),
    path('<int:pk>/versions/', views.PaperVersionListView.as_view(), name='versions'),
    path('<int:pk>/upload-version/', views.upload_paper_version, name='upload_version'),
    path('<int:pk>/annotations/', views.get_annotations, name='get_annotations'),
    path('<int:pk>/annotate/', views.add_annotation, name='add_annotation'),
    path('<int:pk>/related/', views.get_related_papers, name='related_papers'),
    
    # Reading Lists
    path('reading-lists/', views.ReadingListListView.as_view(), name='reading_lists'),
    path('reading-lists/api/', views.get_user_reading_lists, name='get_user_reading_lists'),
    path('reading-lists/create/', views.create_reading_list, name='create_reading_list'),
    path('reading-lists/<int:pk>/', views.ReadingListDetailView.as_view(), name='reading_list_detail'),
    path('reading-lists/<int:list_id>/add/<int:paper_id>/', views.add_to_reading_list, name='add_to_reading_list'),
    
    # Research Projects
    path('projects/', views.ResearchProjectListView.as_view(), name='research_projects'),
    path('projects/<int:pk>/', views.ResearchProjectDetailView.as_view(), name='research_project_detail'),
    
    # Social Features
    path('<int:pk>/like/', views.like_paper, name='like_paper'),
    path('<int:pk>/share/', views.share_paper, name='share_paper'),
    path('<int:pk>/comments/', views.get_comments, name='get_comments'),
    path('<int:pk>/comment/', views.add_comment, name='add_comment'),
    
    # Peer Review
    path('<int:paper_id>/review/', views.PeerReviewCreateView.as_view(), name='create_review'),
    path('<int:paper_id>/reviews/', views.PeerReviewListView.as_view(), name='peer_reviews'),
    path('review/<int:review_id>/submit/', views.submit_peer_review, name='submit_review'),
    
    # Research Blog
    path('blog/', views.BlogPostListView.as_view(), name='blog_list'),
    path('blog/new/', views.BlogPostCreateView.as_view(), name='blog_create'),
    path('blog/my-posts/', views.MyBlogPostsView.as_view(), name='my_blog_posts'),
    path('blog/pending/', views.PendingBlogPostsView.as_view(), name='pending_blog_posts'),
    path('blog/<int:pk>/approve/', views.approve_blog_post, name='approve_blog_post'),
    path('blog/<int:pk>/reject/', views.reject_blog_post, name='reject_blog_post'),
    path('blog/<slug:slug>/', views.BlogPostDetailView.as_view(), name='blog_detail'),
    path('blog/<slug:slug>/comment/', views.add_blog_comment, name='add_blog_comment'),
    
    # Archive
    path('<int:pk>/archive/', views.archive_paper, name='archive_paper'),
    path('archived/', views.ArchivedPapersView.as_view(), name='archived_papers'),
    
    # Tags
    path('tags/', views.TagListView.as_view(), name='tags_list'),
    path('tags/create/', views.create_tag, name='create_tag'),
    path('<int:paper_id>/tag/<int:tag_id>/', views.tag_paper, name='tag_paper'),
    
    # Paper Comparison
    path('comparisons/', views.PaperComparisonListView.as_view(), name='comparison_list'),
    path('comparisons/create/', views.create_comparison, name='create_comparison'),
    path('comparisons/<int:pk>/', views.PaperComparisonDetailView.as_view(), name='comparison_detail'),
    path('comparisons/<int:pk>/delete/', views.delete_comparison, name='delete_comparison'),
    
    # Citation Graph
    path('<int:pk>/citations/graph/', views.CitationGraphView.as_view(), name='citation_graph'),
    
]
