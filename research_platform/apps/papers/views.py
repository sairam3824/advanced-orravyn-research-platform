from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Q, Avg, Count, F
from django.core.paginator import Paginator
from .models import Paper, Category, Bookmark, Rating, Citation, CategoryRequest, PaperView, ReadingProgress
from .forms import PaperUploadForm, PaperEditForm, RatingForm, CategoryRequestForm
from apps.accounts.permissions import IsPublisherOrAbove, IsModeratorOrAdmin

class PaperListView(ListView):
    model = Paper
    template_name = 'papers/list.html'
    context_object_name = 'papers'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Paper.objects.filter(is_approved=True).select_related('uploaded_by').prefetch_related('categories')
        
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(abstract__icontains=search_query) |
                Q(authors__icontains=search_query)
            )
        
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by == 'popular':
            queryset = queryset.order_by('-view_count')
        elif sort_by == 'rating':
            queryset = queryset.annotate(avg_rating=Avg('ratings__rating')).order_by('-avg_rating')
        elif sort_by == 'citations':
            queryset = queryset.annotate(citation_count=Count('cited_by')).order_by('-citation_count')
        else:
            queryset = queryset.order_by(sort_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['sort_by'] = self.request.GET.get('sort', '-created_at')
        
        # Add bookmark information for authenticated users
        if self.request.user.is_authenticated:
            bookmarked_paper_ids = Bookmark.objects.filter(
                user=self.request.user
            ).values_list('paper_id', flat=True)
            context['bookmarked_paper_ids'] = list(bookmarked_paper_ids)
        else:
            context['bookmarked_paper_ids'] = []
        
        return context

class PaperDetailView(DetailView):
    model = Paper
    template_name = 'papers/detail.html'
    context_object_name = 'paper'
    
    def get_queryset(self):
        if self.request.user.is_authenticated:
            if self.request.user.user_type in ['moderator', 'admin']:
                return Paper.objects.all()
            elif self.request.user.user_type == 'publisher':
                return Paper.objects.filter(
                    Q(uploaded_by=self.request.user) | Q(is_approved=True)
                )
        return Paper.objects.filter(is_approved=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paper = self.object
        
        if self.request.user.is_authenticated:
            _, is_new_view = PaperView.objects.get_or_create(user=self.request.user, paper=paper)
            if is_new_view:
                Paper.objects.filter(id=paper.id).update(view_count=F('view_count') + 1)
                ReadingProgress.objects.get_or_create(user=self.request.user, paper=paper)
                # Directly update papers read count (signal handles completed/time)
                from apps.analytics.models import UserReadingStatistics
                stats, _ = UserReadingStatistics.objects.get_or_create(user=self.request.user)
                stats.total_papers_read = PaperView.objects.filter(user=self.request.user).count()
                stats.save(update_fields=['total_papers_read'])

        context['ratings'] = Rating.objects.filter(paper=paper).select_related('user')
        context['citations'] = Citation.objects.filter(cited_paper=paper).select_related('citing_paper')
        context['cited_papers'] = Citation.objects.filter(citing_paper=paper).select_related('cited_paper')

        if self.request.user.is_authenticated:
            context['user_bookmark'] = Bookmark.objects.filter(user=self.request.user, paper=paper).first()
            context['user_rating'] = Rating.objects.filter(user=self.request.user, paper=paper).first()
            context['rating_form'] = RatingForm()
            context['reading_progress'] = ReadingProgress.objects.filter(user=self.request.user, paper=paper).first()
            context['user_liked'] = PaperLike.objects.filter(user=self.request.user, paper=paper).exists()
        
        return context



class PaperEditView(LoginRequiredMixin, UpdateView):
    model = Paper
    form_class = PaperEditForm
    template_name = 'papers/edit.html'
    
    def get_queryset(self):
        if self.request.user.user_type in ['moderator', 'admin']:
            return Paper.objects.all()
        return Paper.objects.filter(uploaded_by=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('papers:detail', kwargs={'pk': self.object.pk})

class PaperDeleteView(LoginRequiredMixin, DeleteView):
    model = Paper
    template_name = 'papers/delete.html'
    success_url = reverse_lazy('papers:my_papers')
    
    def get_queryset(self):
        if self.request.user.user_type in ['moderator', 'admin']:
            return Paper.objects.all()
        return Paper.objects.filter(uploaded_by=self.request.user)

class MyPapersView(LoginRequiredMixin, ListView):
    model = Paper
    template_name = 'papers/my_papers.html'
    context_object_name = 'papers'
    paginate_by = 10
    
    def get_queryset(self):
        return Paper.objects.filter(uploaded_by=self.request.user).order_by('-created_at')

class BookmarkListView(LoginRequiredMixin, ListView):
    model = Bookmark
    template_name = 'papers/bookmarks.html'
    context_object_name = 'bookmarks'
    paginate_by = 12
    
    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user).select_related('paper').order_by('-created_at')

class CategoryListView(ListView):
    model = Category
    template_name = 'papers/categories.html'
    context_object_name = 'categories'

def category_search(request):
    """JSON endpoint for live category search"""
    query = request.GET.get('q', '').strip()
    
    if query:
        categories = Category.objects.filter(
            name__icontains=query
        ).annotate(
            paper_count=Count('paper')
        ).order_by('name')[:20]
    else:
        categories = Category.objects.annotate(
            paper_count=Count('paper')
        ).order_by('name')
    
    results = [{
        'id': cat.id,
        'name': cat.name,
        'paper_count': cat.paper_count,
        'url': reverse('papers:category_detail', args=[cat.id])
    } for cat in categories]
    
    return JsonResponse({'categories': results})

class CategoryDetailView(DetailView):
    model = Category
    template_name = 'papers/category_detail.html'
    context_object_name = 'category'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['papers'] = Paper.objects.filter(categories=self.object, is_approved=True).order_by('-created_at')
        return context

class PendingApprovalView(LoginRequiredMixin, ListView):
    model = Paper
    template_name = 'papers/pending_approval.html'
    context_object_name = 'papers'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ['moderator', 'admin']:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('papers:list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = Paper.objects.filter(is_approved=False).select_related('uploaded_by').prefetch_related('categories').order_by('-created_at')
        return queryset

@login_required
def bookmark_paper(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, paper=paper)
    
    if created:
        messages.success(request, 'Paper bookmarked successfully!')
    else:
        bookmark.delete()
        messages.success(request, 'Bookmark removed!')
    
    return redirect('papers:detail', pk=pk)

@login_required
def rate_paper(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    
    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating, created = Rating.objects.get_or_create(
                user=request.user,
                paper=paper,
                defaults={
                    'rating': form.cleaned_data['rating'],
                    'review_text': form.cleaned_data['review_text']
                }
            )
            if not created:
                rating.rating = form.cleaned_data['rating']
                rating.review_text = form.cleaned_data['review_text']
                rating.save()
            
            messages.success(request, 'Rating submitted successfully!')
    
    return redirect('papers:detail', pk=pk)

@login_required
def approve_paper(request, pk):
    if request.user.user_type not in ['moderator', 'admin']:
        messages.error(request, 'You do not have permission to approve papers.')
        return redirect('papers:list')
    
    paper = get_object_or_404(Paper, pk=pk)
    paper.is_approved = True
    paper.save()
    messages.success(request, f'Paper "{paper.title}" approved successfully!')
    return redirect('papers:pending_approval')

@login_required
def reject_paper(request, pk):
    if request.user.user_type not in ['moderator', 'admin']:
        messages.error(request, 'You do not have permission to reject papers.')
        return redirect('papers:list')
    
    paper = get_object_or_404(Paper, pk=pk)
    paper.delete()
    messages.success(request, 'Paper rejected and deleted successfully!')
    return redirect('papers:pending_approval')

@login_required
def get_recommendations(request):
    try:
        from apps.ml_engine.models import UserRecommendation
        recommendations = UserRecommendation.objects.filter(
            user=request.user
        ).select_related('paper')[:10]
    except ImportError:
        recommendations = []
    
    if request.META.get('HTTP_ACCEPT') == 'application/json':
        data = []
        for rec in recommendations:
            data.append({
                'paper_id': rec.paper.id,
                'title': rec.paper.title,
                'score': rec.score,
                'reason': rec.reason
            })
        return JsonResponse({'recommendations': data})
    
    return render(request, 'papers/recommendations.html', {
        'recommendations': recommendations
    })

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.http import JsonResponse

class PaperListCreateView(generics.ListCreateAPIView):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Paper.objects.filter(is_approved=True)
    
    def list(self, request, *args, **kwargs):
        papers = self.get_queryset()
        data = []
        for paper in papers:
            data.append({
                'id': paper.id,
                'title': paper.title,
                'abstract': paper.abstract,
                'authors': paper.authors,
                'publication_date': paper.publication_date,
                'uploaded_by': paper.uploaded_by.username,
                'view_count': paper.view_count,
                'download_count': paper.download_count,
            })
        return Response(data)
    
    def create(self, request, *args, **kwargs):
        return Response({'message': 'Paper creation via API not implemented yet'}, 
                       status=status.HTTP_501_NOT_IMPLEMENTED)

class BookmarkListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user)
    
    def list(self, request, *args, **kwargs):
        bookmarks = self.get_queryset()
        data = []
        for bookmark in bookmarks:
            data.append({
                'id': bookmark.id,
                'paper_title': bookmark.paper.title,
                'paper_id': bookmark.paper.id,
                'created_at': bookmark.created_at,
                'folder': bookmark.folder,
            })
        return Response(data)
    
    def create(self, request, *args, **kwargs):
        return Response({'message': 'Bookmark creation via API not implemented yet'}, 
                       status=status.HTTP_501_NOT_IMPLEMENTED)

class RatingListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Rating.objects.filter(user=self.request.user).select_related('paper')
    
    def list(self, request, *args, **kwargs):
        ratings = self.get_queryset()
        data = []
        for rating in ratings:
            data.append({
                'id': rating.id,
                'paper_title': rating.paper.title,
                'paper_id': rating.paper.id,
                'rating': rating.rating,
                'review_text': rating.review_text,
                'created_at': rating.created_at,
            })
        return Response(data)
    
    def create(self, request, *args, **kwargs):
        return Response({'message': 'Rating creation via API not implemented yet'}, 
                       status=status.HTTP_501_NOT_IMPLEMENTED)

@login_required
def view_paper_pdf(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    
    if not paper.is_approved:
        if request.user.user_type not in ['moderator', 'admin']:
            messages.error(request, 'You do not have permission to view this paper.')
            return redirect('papers:list')
    
    if paper.pdf_path and paper.pdf_path.name:
        try:
            pdf_file = paper.pdf_path.open('rb')
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{paper.title}.pdf"'
            pdf_file.close()
            return response
        except FileNotFoundError:
            messages.error(request, 'PDF file not found on server.')
            return redirect('papers:detail', pk=pk)
        except Exception as e:
            messages.error(request, f'Error loading PDF: {str(e)}')
            return redirect('papers:detail', pk=pk)
    else:
        messages.error(request, 'No PDF file available for this paper.')
        return redirect('papers:detail', pk=pk)

@login_required
def download_paper(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    
    if not paper.is_approved:
        if request.user.user_type not in ['moderator', 'admin']:
            messages.error(request, 'You do not have permission to download this paper.')
            return redirect('papers:list')
    
    if paper.is_approved:
        Paper.objects.filter(id=paper.id).update(download_count=F('download_count') + 1)
    
    if paper.pdf_path and paper.pdf_path.name:
        try:
            pdf_file = paper.pdf_path.open('rb')
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{paper.title}.pdf"'
            pdf_file.close()
            return response
        except FileNotFoundError:
            messages.error(request, 'PDF file not found on server.')
            return redirect('papers:detail', pk=pk)
        except Exception as e:
            messages.error(request, f'Error downloading PDF: {str(e)}')
            return redirect('papers:detail', pk=pk)
    else:
        messages.error(request, 'No PDF file available for this paper.')
        return redirect('papers:detail', pk=pk)




class PaperUploadView(LoginRequiredMixin, CreateView):
    model = Paper
    form_class = PaperUploadForm
    template_name = "papers/upload.html"
    success_url = reverse_lazy("papers:my_papers")

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ["publisher", "moderator", "admin"]:
            messages.error(request, "You do not have permission to upload papers.")
            return redirect("papers:list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        paper = form.save(commit=False)
        paper.uploaded_by = self.request.user

        paper.is_approved = self.request.user.user_type in ["moderator", "admin"]

        paper.save()
        form.save_m2m()

        approval_msg = "" if paper.is_approved else " It will be visible after moderator approval."
        messages.success(self.request, f"Paper uploaded successfully!{approval_msg}")
        
        return redirect(self.success_url)
    
    def form_invalid(self, form):
        messages.error(self.request, "There was an error uploading your paper. Please check the form and try again.")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


from django.contrib.auth.mixins import UserPassesTestMixin

class AdminPaperListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Paper
    template_name = 'papers/admin_paper_list.html'
    context_object_name = 'papers'
    paginate_by = 20

    def test_func(self):
        return self.request.user.user_type == 'admin'

    def get_queryset(self):
        queryset = Paper.objects.all().select_related('uploaded_by')
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(abstract__icontains=search_query) |
                Q(authors__icontains=search_query)
            )
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class PaperSummaryView(LoginRequiredMixin, DetailView):
    model = Paper
    template_name = "papers/summary.html"
    context_object_name = "paper"

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.user_type in ["moderator", "admin"]:
            return Paper.objects.all()
        elif user.is_authenticated and user.user_type == "publisher":
            return Paper.objects.filter(uploaded_by=user) | Paper.objects.filter(is_approved=True)
        return Paper.objects.filter(is_approved=True)


# ── Category Request Views ──────────────────────────────────────────────────

class CategoryRequestCreateView(LoginRequiredMixin, CreateView):
    model = CategoryRequest
    form_class = CategoryRequestForm
    template_name = 'papers/category_request_form.html'
    success_url = reverse_lazy('papers:categories')

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ['publisher', 'moderator', 'admin']:
            messages.error(request, 'You do not have permission to request categories.')
            return redirect('papers:list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.requested_by = self.request.user
        messages.success(
            self.request,
            'Your category request has been submitted and is pending review by a moderator.'
        )
        return super().form_valid(form)


class CategoryRequestListView(LoginRequiredMixin, ListView):
    model = CategoryRequest
    template_name = 'papers/category_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ['moderator', 'admin']:
            messages.error(request, 'You do not have permission to review category requests.')
            return redirect('papers:list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        status_filter = self.request.GET.get('status', 'pending')
        return CategoryRequest.objects.filter(
            status=status_filter
        ).select_related('requested_by', 'reviewed_by').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', 'pending')
        context['pending_count'] = CategoryRequest.objects.filter(status='pending').count()
        return context


@login_required
def approve_category_request(request, pk):
    if request.user.user_type not in ['moderator', 'admin']:
        messages.error(request, 'You do not have permission to approve category requests.')
        return redirect('papers:list')

    from django.utils import timezone as tz
    cat_request = get_object_or_404(CategoryRequest, pk=pk, status='pending')

    # Create the category if it doesn't already exist
    category, created = Category.objects.get_or_create(
        name=cat_request.name,
        defaults={'description': cat_request.description}
    )

    cat_request.status = CategoryRequest.STATUS_APPROVED
    cat_request.reviewed_by = request.user
    cat_request.reviewed_at = tz.now()
    cat_request.save()

    if created:
        messages.success(request, f'Category "{category.name}" created and approved successfully!')
    else:
        messages.warning(
            request,
            f'Category "{category.name}" already exists. Request marked as approved.'
        )
    return redirect('papers:category_requests')


@login_required
def reject_category_request(request, pk):
    if request.user.user_type not in ['moderator', 'admin']:
        messages.error(request, 'You do not have permission to reject category requests.')
        return redirect('papers:list')

    from django.utils import timezone as tz
    cat_request = get_object_or_404(CategoryRequest, pk=pk, status='pending')
    cat_request.status = CategoryRequest.STATUS_REJECTED
    cat_request.reviewed_by = request.user
    cat_request.reviewed_at = tz.now()
    cat_request.save()

    messages.success(request, f'Category request "{cat_request.name}" has been rejected.')
    return redirect('papers:category_requests')



# ── Paper Advanced Features ──────────────────────────────────────────────────

from .models import (
    PaperVersion, RelatedPaper, PaperAnnotation, ReadingList, 
    ReadingListPaper, PaperCollection, ResearchProject, ProjectTask
)
from django.views.generic import CreateView
import json


@login_required
def export_citation(request, pk):
    """Export paper citation in various formats"""
    paper = get_object_or_404(Paper, pk=pk)
    format_type = request.GET.get('format', 'bibtex')
    
    if format_type == 'bibtex':
        citation = f"""@article{{{paper.id},
  title={{{paper.title}}},
  author={{{paper.authors}}},
  year={{{paper.publication_date.year if paper.publication_date else 'n.d.'}}},
  doi={{{paper.doi or 'N/A'}}}
}}"""
        content_type = 'application/x-bibtex'
        filename = f'{paper.id}.bib'
    
    elif format_type == 'ris':
        citation = f"""TY  - JOUR
TI  - {paper.title}
AU  - {paper.authors}
PY  - {paper.publication_date.year if paper.publication_date else 'n.d.'}
DO  - {paper.doi or 'N/A'}
ER  -"""
        content_type = 'application/x-research-info-systems'
        filename = f'{paper.id}.ris'
    
    elif format_type == 'endnote':
        citation = f"""%0 Journal Article
%T {paper.title}
%A {paper.authors}
%D {paper.publication_date.year if paper.publication_date else 'n.d.'}
%R {paper.doi or 'N/A'}"""
        content_type = 'application/x-endnote-refer'
        filename = f'{paper.id}.enw'
    
    else:
        return HttpResponse('Invalid format', status=400)
    
    response = HttpResponse(citation, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def update_reading_progress(request, pk):
    """Update reading progress for a paper"""
    if request.method == 'POST':
        paper = get_object_or_404(Paper, pk=pk)
        
        progress, created = ReadingProgress.objects.get_or_create(
            user=request.user,
            paper=paper
        )
        
        try:
            progress.progress_percentage = max(0.0, min(100.0, float(request.POST.get('progress', 0))))
            progress.last_page = max(1, int(request.POST.get('page', 1)))
            progress.completed = request.POST.get('completed', 'false') == 'true'
            progress.reading_time_minutes += max(0, int(request.POST.get('time_spent', 0)))
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid input values'}, status=400)
        progress.save()

        return JsonResponse({'success': True, 'progress': progress.progress_percentage, 'completed': progress.completed})
    
    return JsonResponse({'success': False})


class PaperVersionListView(LoginRequiredMixin, ListView):
    model = PaperVersion
    template_name = 'papers/versions.html'
    context_object_name = 'versions'
    
    def get_queryset(self):
        paper_id = self.kwargs.get('paper_id')
        return PaperVersion.objects.filter(paper_id=paper_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['paper'] = get_object_or_404(Paper, pk=self.kwargs.get('paper_id'))
        return context


@login_required
def upload_paper_version(request, pk):
    """Upload a new version of a paper"""
    paper = get_object_or_404(Paper, pk=pk, uploaded_by=request.user)
    
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf_file')
        changes = request.POST.get('changes_description', '')
        
        if not pdf_file or not changes:
            messages.error(request, 'PDF file and changes description are required.')
            return redirect('papers:detail', pk=pk)
        
        # Get next version number
        last_version = PaperVersion.objects.filter(paper=paper).order_by('-version_number').first()
        next_version = (last_version.version_number + 1) if last_version else 1
        
        PaperVersion.objects.create(
            paper=paper,
            version_number=next_version,
            pdf_path=pdf_file,
            changes_description=changes,
            uploaded_by=request.user
        )
        
        messages.success(request, f'Version {next_version} uploaded successfully!')
        return redirect('papers:versions', paper_id=pk)
    
    return render(request, 'papers/upload_version.html', {'paper': paper})


@login_required
def add_annotation(request, pk):
    """Add annotation to a paper"""
    if request.method == 'POST':
        paper = get_object_or_404(Paper, pk=pk)

        try:
            page_number = int(request.POST.get('page', 1))
            position_data = json.loads(request.POST.get('position', '{}'))
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'success': False, 'error': 'Invalid page or position data'}, status=400)

        annotation = PaperAnnotation.objects.create(
            paper=paper,
            user=request.user,
            page_number=page_number,
            annotation_text=request.POST.get('annotation', ''),
            highlight_text=request.POST.get('highlight', ''),
            position_data=position_data,
            is_public=request.POST.get('is_public', 'false') == 'true'
        )

        return JsonResponse({
            'success': True,
            'annotation_id': annotation.id,
            'created_at': annotation.created_at.strftime('%Y-%m-%d %H:%M')
        })

    return JsonResponse({'success': False})


@login_required
def get_annotations(request, pk):
    """Get all annotations for a paper"""
    paper = get_object_or_404(Paper, pk=pk)
    
    # Get user's own annotations + public annotations from others
    annotations = PaperAnnotation.objects.filter(
        Q(paper=paper, user=request.user) | Q(paper=paper, is_public=True)
    ).select_related('user')
    
    data = []
    for ann in annotations:
        data.append({
            'id': ann.id,
            'page': ann.page_number,
            'text': ann.annotation_text,
            'highlight': ann.highlight_text,
            'position': ann.position_data,
            'user': ann.user.username,
            'is_own': ann.user == request.user,
            'created_at': ann.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'annotations': data})


class ReadingListListView(LoginRequiredMixin, ListView):
    model = ReadingList
    template_name = 'papers/reading_lists.html'
    context_object_name = 'reading_lists'
    
    def get_queryset(self):
        view_type = self.request.GET.get('view', 'my')
        
        if view_type == 'public':
            # Show all public lists
            return ReadingList.objects.filter(
                is_public=True
            ).select_related('owner').order_by('-updated_at')
        else:
            # Show user's own lists (both public and private)
            return ReadingList.objects.filter(
                owner=self.request.user
            ).order_by('-updated_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view_type'] = self.request.GET.get('view', 'my')
        return context


class ReadingListDetailView(LoginRequiredMixin, DetailView):
    model = ReadingList
    template_name = 'papers/reading_list_detail.html'
    context_object_name = 'reading_list'
    
    def get_queryset(self):
        return ReadingList.objects.filter(
            Q(owner=self.request.user) | Q(shared_with=self.request.user)
        )


@login_required
def create_reading_list(request):
    """Create a new reading list"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '')
        is_public = request.POST.get('is_public', 'false') == 'true'
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        
        reading_list = ReadingList.objects.create(
            name=name,
            description=description,
            owner=request.user,
            is_public=is_public
        )
        
        return JsonResponse({
            'success': True,
            'list_id': reading_list.id,
            'name': reading_list.name
        })
    
    return JsonResponse({'success': False})


@login_required
def get_user_reading_lists(request):
    """Get user's reading lists as JSON"""
    lists = ReadingList.objects.filter(owner=request.user).order_by('-created_at')
    
    data = [{
        'id': lst.id,
        'name': lst.name,
        'is_public': lst.is_public,
        'paper_count': lst.papers.count()
    } for lst in lists]
    
    return JsonResponse({'lists': data})


@login_required
def add_to_reading_list(request, list_id, paper_id):
    """Add a paper to a reading list"""
    reading_list = get_object_or_404(ReadingList, id=list_id, owner=request.user)
    paper = get_object_or_404(Paper, id=paper_id)
    
    item, created = ReadingListPaper.objects.get_or_create(
        reading_list=reading_list,
        paper=paper
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'message': f'Added to {reading_list.name}' if created else 'Already in list'
        })
    
    messages.success(request, f'Added to {reading_list.name}')
    return redirect('papers:detail', pk=paper_id)


@login_required
def get_related_papers(request, pk):
    """Get related papers for a given paper"""
    paper = get_object_or_404(Paper, pk=pk)
    
    related = RelatedPaper.objects.filter(paper=paper).select_related('related_to')[:10]
    
    data = []
    for rel in related:
        data.append({
            'id': rel.related_to.id,
            'title': rel.related_to.title,
            'authors': rel.related_to.authors,
            'year': rel.related_to.publication_date.year if rel.related_to.publication_date else None,
            'relation_type': rel.get_relation_type_display(),
            'similarity_score': rel.similarity_score
        })
    
    return JsonResponse({'related_papers': data})


class ResearchProjectListView(LoginRequiredMixin, ListView):
    model = ResearchProject
    template_name = 'papers/research_projects.html'
    context_object_name = 'projects'
    
    def get_queryset(self):
        return ResearchProject.objects.filter(
            Q(created_by=self.request.user) | Q(members=self.request.user)
        ).distinct()


class ResearchProjectDetailView(LoginRequiredMixin, DetailView):
    model = ResearchProject
    template_name = 'papers/research_project_detail.html'
    context_object_name = 'project'
    
    def get_queryset(self):
        return ResearchProject.objects.filter(
            Q(created_by=self.request.user) | Q(members=self.request.user)
        )



# ── Social Features ──────────────────────────────────────────────────

from .models import PaperLike, PaperShare, PaperComment, PeerReview, ResearchBlogPost, BlogComment, PaperTag, PaperTagging, PaperComparison
from django.utils.text import slugify


@login_required
def like_paper(request, pk):
    """Like/unlike a paper"""
    paper = get_object_or_404(Paper, pk=pk)
    
    like, created = PaperLike.objects.get_or_create(user=request.user, paper=paper)
    
    if not created:
        like.delete()
        action = 'unliked'
        liked = False
    else:
        action = 'liked'
        liked = True
        
        # Create notification for paper author
        if paper.uploaded_by != request.user:
            from apps.messaging.utils import create_notification
            create_notification(
                user=paper.uploaded_by,
                notification_type='paper',
                title='Paper Liked',
                message=f'{request.user.username} liked your paper "{paper.title}"',
                link=f'/papers/{paper.id}/'
            )
    
    total_likes = PaperLike.objects.filter(paper=paper).count()
    
    return JsonResponse({
        'success': True,
        'action': action,
        'liked': liked,
        'total_likes': total_likes
    })


@login_required
def share_paper(request, pk):
    """Track paper sharing"""
    if request.method == 'POST':
        paper = get_object_or_404(Paper, pk=pk)
        platform = request.POST.get('platform', 'link')
        
        PaperShare.objects.create(
            user=request.user,
            paper=paper,
            platform=platform
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Paper shared on {platform}'
        })
    
    return JsonResponse({'success': False})


@login_required
def add_comment(request, pk):
    """Add comment to a paper"""
    if request.method == 'POST':
        paper = get_object_or_404(Paper, pk=pk)
        content = request.POST.get('content', '').strip()
        parent_id = request.POST.get('parent_id')
        
        if not content:
            return JsonResponse({'success': False, 'error': 'Comment cannot be empty'})
        
        parent = None
        if parent_id:
            parent = get_object_or_404(PaperComment, id=parent_id)
        
        comment = PaperComment.objects.create(
            paper=paper,
            user=request.user,
            parent=parent,
            content=content
        )
        
        # Notify paper author
        if paper.uploaded_by != request.user:
            from apps.messaging.utils import create_notification
            create_notification(
                user=paper.uploaded_by,
                notification_type='comment',
                title='New Comment',
                message=f'{request.user.username} commented on your paper',
                link=f'/papers/{paper.id}/#comment-{comment.id}'
            )
        
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'user': request.user.username,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'success': False})


@login_required
def get_comments(request, pk):
    """Get all comments for a paper"""
    paper = get_object_or_404(Paper, pk=pk)
    comments = PaperComment.objects.filter(paper=paper, parent=None).select_related('user')
    
    def serialize_comment(comment):
        return {
            'id': comment.id,
            'user': comment.user.username,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_edited': comment.is_edited,
            'replies': [serialize_comment(reply) for reply in comment.replies.all()]
        }
    
    data = [serialize_comment(c) for c in comments]
    
    return JsonResponse({'comments': data})


class PeerReviewCreateView(LoginRequiredMixin, CreateView):
    model = PeerReview
    template_name = 'papers/peer_review_form.html'
    fields = [
        'originality_score', 'methodology_score', 'clarity_score', 'significance_score',
        'strengths', 'weaknesses', 'detailed_comments', 'confidential_comments',
        'recommendation', 'is_anonymous'
    ]
    
    def dispatch(self, request, *args, **kwargs):
        self.paper = get_object_or_404(Paper, pk=kwargs.get('paper_id'))
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        form.instance.paper = self.paper
        form.instance.reviewer = self.request.user
        form.instance.status = 'in_review'
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('papers:detail', kwargs={'pk': self.paper.pk})


class PeerReviewListView(LoginRequiredMixin, ListView):
    model = PeerReview
    template_name = 'papers/peer_reviews.html'
    context_object_name = 'reviews'
    
    def get_queryset(self):
        paper_id = self.kwargs.get('paper_id')
        paper = get_object_or_404(Paper, pk=paper_id)
        
        # Only show reviews to paper author and reviewers
        if self.request.user == paper.uploaded_by or self.request.user.user_type in ['moderator', 'admin']:
            return PeerReview.objects.filter(paper=paper)
        else:
            return PeerReview.objects.filter(paper=paper, reviewer=self.request.user)


@login_required
def submit_peer_review(request, review_id):
    """Submit completed peer review"""
    review = get_object_or_404(PeerReview, id=review_id, reviewer=request.user)
    
    review.status = 'completed'
    review.completed_at = timezone.now()
    review.save()
    
    # Notify paper author
    from apps.messaging.utils import create_notification
    create_notification(
        user=review.paper.uploaded_by,
        notification_type='paper',
        title='Peer Review Completed',
        message=f'A peer review for your paper "{review.paper.title}" has been completed',
        link=f'/papers/{review.paper.id}/reviews/'
    )
    
    messages.success(request, 'Peer review submitted successfully!')
    return redirect('papers:detail', pk=review.paper.id)


# ── Research Blog ──────────────────────────────────────────────────

class BlogPostListView(ListView):
    model = ResearchBlogPost
    template_name = 'papers/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        return ResearchBlogPost.objects.filter(status='published').order_by('-published_at')


class BlogPostDetailView(DetailView):
    model = ResearchBlogPost
    template_name = 'papers/blog_detail.html'
    context_object_name = 'post'
    slug_field = 'slug'
    
    def get_queryset(self):
        return ResearchBlogPost.objects.filter(status='published')
    
    def get_object(self):
        obj = super().get_object()
        ResearchBlogPost.objects.filter(pk=obj.pk).update(view_count=F('view_count') + 1)
        return obj


class BlogPostCreateView(LoginRequiredMixin, CreateView):
    model = ResearchBlogPost
    template_name = 'papers/blog_form.html'
    fields = ['title', 'content', 'excerpt', 'featured_image', 'tags']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['papers'] = Paper.objects.filter(is_approved=True).order_by('-created_at')[:100]
        return context
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.slug = slugify(form.instance.title)
        
        # Set status to pending approval (unless user is admin/moderator)
        if self.request.user.user_type in ['admin', 'moderator']:
            form.instance.status = 'published'
            form.instance.is_approved = True
            form.instance.approved_by = self.request.user
            form.instance.published_at = timezone.now()
        else:
            form.instance.status = 'pending'
            form.instance.is_approved = False
        
        # Save the instance first
        response = super().form_valid(form)
        
        # Handle related papers (comma-separated IDs)
        related_papers_ids = self.request.POST.get('related_papers', '')
        if related_papers_ids:
            paper_ids = [int(pid.strip()) for pid in related_papers_ids.split(',') if pid.strip().isdigit()]
            if paper_ids:
                self.object.related_papers.set(paper_ids)
        
        # Notify followers only if published
        if form.instance.status == 'published':
            from apps.messaging.utils import notify_followers
            notify_followers(
                user=self.request.user,
                notification_type='paper',
                title='New Blog Post',
                message=f'{self.request.user.username} published a new blog post: {form.instance.title}',
                link=f'/papers/blog/{form.instance.slug}/'
            )
        else:
            messages.success(self.request, 'Your blog post has been submitted for approval.')
        
        return response
    
    def get_success_url(self):
        if self.object.status == 'published':
            return reverse_lazy('papers:blog_detail', kwargs={'slug': self.object.slug})
        else:
            return reverse_lazy('papers:blog_list')


@login_required
def add_blog_comment(request, slug):
    """Add comment to a blog post"""
    if request.method == 'POST':
        post = get_object_or_404(ResearchBlogPost, slug=slug, status='published')
        content = request.POST.get('content', '').strip()
        parent_id = request.POST.get('parent_id')
        
        if not content:
            return JsonResponse({'success': False, 'error': 'Comment cannot be empty'})
        
        parent = None
        if parent_id:
            parent = get_object_or_404(BlogComment, id=parent_id)
        
        comment = BlogComment.objects.create(
            blog_post=post,
            user=request.user,
            parent=parent,
            content=content
        )
        
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'user': request.user.username,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'success': False})


# ── Blog Approval (Moderator/Admin) ────────────────────────────────

class PendingBlogPostsView(LoginRequiredMixin, ListView):
    """View for moderators/admins to see pending blog posts"""
    model = ResearchBlogPost
    template_name = 'papers/blog_pending.html'
    context_object_name = 'posts'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ['admin', 'moderator']:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('papers:blog_list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return ResearchBlogPost.objects.filter(status='pending').order_by('-created_at')


@login_required
def approve_blog_post(request, pk):
    """Approve a blog post"""
    if request.user.user_type not in ['admin', 'moderator']:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('papers:blog_list')
    
    try:
        post = ResearchBlogPost.objects.get(pk=pk)
        post.status = 'published'
        post.is_approved = True
        post.approved_by = request.user
        post.published_at = timezone.now()
        post.save()
        
        # Notify author
        from apps.messaging.models import Notification
        Notification.objects.create(
            user=post.author,
            notification_type='paper',
            title='Blog Post Approved',
            message=f'Your blog post "{post.title}" has been approved and published!',
            link=f'/papers/blog/{post.slug}/'
        )
        
        # Notify followers
        from apps.messaging.utils import notify_followers
        notify_followers(
            user=post.author,
            notification_type='paper',
            title='New Blog Post',
            message=f'{post.author.username} published a new blog post: {post.title}',
            link=f'/papers/blog/{post.slug}/'
        )
        
        messages.success(request, f'Blog post "{post.title}" has been approved and published.')
    except ResearchBlogPost.DoesNotExist:
        messages.error(request, 'Blog post not found.')
    
    return redirect('papers:pending_blog_posts')


@login_required
def reject_blog_post(request, pk):
    """Reject a blog post"""
    if request.user.user_type not in ['admin', 'moderator']:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('papers:blog_list')
    
    if request.method == 'POST':
        try:
            post = ResearchBlogPost.objects.get(pk=pk)
            reason = request.POST.get('reason', '').strip()
            
            post.status = 'rejected'
            post.is_approved = False
            post.rejection_reason = reason
            post.save()
            
            # Notify author
            from apps.messaging.models import Notification
            Notification.objects.create(
                user=post.author,
                notification_type='paper',
                title='Blog Post Rejected',
                message=f'Your blog post "{post.title}" was not approved. Reason: {reason}',
                link=f'/papers/blog/my-posts/'
            )
            
            messages.success(request, f'Blog post "{post.title}" has been rejected.')
        except ResearchBlogPost.DoesNotExist:
            messages.error(request, 'Blog post not found.')
    
    return redirect('papers:pending_blog_posts')


class MyBlogPostsView(LoginRequiredMixin, ListView):
    """View user's own blog posts"""
    model = ResearchBlogPost
    template_name = 'papers/my_blog_posts.html'
    context_object_name = 'posts'
    paginate_by = 20
    
    def get_queryset(self):
        return ResearchBlogPost.objects.filter(author=self.request.user).order_by('-created_at')



# ── Archive Functionality ────────────────────────────────────────────

@login_required
def archive_paper(request, pk):
    """Archive/unarchive a paper"""
    if request.method == 'POST':
        try:
            paper = Paper.objects.get(pk=pk, uploaded_by=request.user)
            paper.is_archived = not paper.is_archived
            paper.archived_at = timezone.now() if paper.is_archived else None
            paper.save()
            
            action = 'archived' if paper.is_archived else 'unarchived'
            messages.success(request, f'Paper "{paper.title}" has been {action}.')
        except Paper.DoesNotExist:
            messages.error(request, 'Paper not found or you do not have permission.')
    
    return redirect('papers:my_papers')


class ArchivedPapersView(LoginRequiredMixin, ListView):
    """View user's archived papers"""
    model = Paper
    template_name = 'papers/archived_papers.html'
    context_object_name = 'papers'
    paginate_by = 20
    
    def get_queryset(self):
        return Paper.objects.filter(uploaded_by=self.request.user, is_archived=True).order_by('-archived_at')


# ── Tags and Labels ──────────────────────────────────────────────────

class TagListView(LoginRequiredMixin, ListView):
    """List all tags"""
    model = PaperTag
    template_name = 'papers/tags_list.html'
    context_object_name = 'tags'
    paginate_by = 50
    
    def get_queryset(self):
        return PaperTag.objects.annotate(
            paper_count=Count('tagged_papers')
        ).order_by('-paper_count')


@login_required
def create_tag(request):
    """Create a new tag"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '#2563eb')
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Tag name is required'})
        
        tag, created = PaperTag.objects.get_or_create(
            name=name,
            defaults={'color': color, 'created_by': request.user}
        )
        
        if created:
            return JsonResponse({
                'success': True,
                'tag': {'id': tag.id, 'name': tag.name, 'color': tag.color}
            })
        else:
            return JsonResponse({'success': False, 'error': 'Tag already exists'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def tag_paper(request, paper_id, tag_id):
    """Add a tag to a paper"""
    if request.method == 'POST':
        try:
            paper = Paper.objects.get(pk=paper_id)
            tag = PaperTag.objects.get(pk=tag_id)
            
            tagging, created = PaperTagging.objects.get_or_create(
                paper=paper,
                tag=tag,
                defaults={'tagged_by': request.user}
            )
            
            if created:
                return JsonResponse({'success': True, 'message': 'Tag added'})
            else:
                tagging.delete()
                return JsonResponse({'success': True, 'message': 'Tag removed'})
        
        except (Paper.DoesNotExist, PaperTag.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Paper or tag not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# ── Paper Comparison ──────────────────────────────────────────────────

class PaperComparisonListView(LoginRequiredMixin, ListView):
    """List user's paper comparisons"""
    model = PaperComparison
    template_name = 'papers/comparison_list.html'
    context_object_name = 'comparisons'
    paginate_by = 20
    
    def get_queryset(self):
        return PaperComparison.objects.filter(user=self.request.user).prefetch_related('papers')


@login_required
def create_comparison(request):
    """Create a new paper comparison"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        paper_ids = request.POST.getlist('papers')
        
        if not name:
            messages.error(request, 'Comparison name is required.')
            return redirect('papers:list')
        
        if len(paper_ids) < 2:
            messages.error(request, 'Please select at least 2 papers to compare.')
            return redirect('papers:list')
        
        comparison = PaperComparison.objects.create(
            user=request.user,
            name=name
        )
        comparison.papers.set(paper_ids)
        
        messages.success(request, f'Comparison "{name}" created successfully.')
        return redirect('papers:comparison_detail', pk=comparison.pk)
    
    return redirect('papers:list')


class PaperComparisonDetailView(LoginRequiredMixin, DetailView):
    """View and compare papers side by side"""
    model = PaperComparison
    template_name = 'papers/comparison_detail.html'
    context_object_name = 'comparison'
    
    def get_queryset(self):
        return PaperComparison.objects.filter(user=self.request.user).prefetch_related('papers')


@login_required
def delete_comparison(request, pk):
    """Delete a paper comparison"""
    try:
        comparison = PaperComparison.objects.get(pk=pk, user=request.user)
        comparison.delete()
        messages.success(request, 'Comparison deleted successfully.')
    except PaperComparison.DoesNotExist:
        messages.error(request, 'Comparison not found.')
    
    return redirect('papers:comparison_list')


# ── Citation Graph ──────────────────────────────────────────────────

class CitationGraphView(DetailView):
    """View citation graph for a paper"""
    model = Paper
    template_name = 'papers/citation_graph.html'
    context_object_name = 'paper'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paper = self.object
        
        # Build citation graph data
        nodes = [{'id': paper.id, 'title': paper.title, 'type': 'main'}]
        edges = []
        
        # Papers this paper cites
        for citation in paper.citations.all()[:20]:
            cited = citation.cited_paper
            nodes.append({'id': cited.id, 'title': cited.title, 'type': 'cited'})
            edges.append({'source': paper.id, 'target': cited.id, 'type': 'cites'})
        
        # Papers that cite this paper
        for citation in paper.cited_by.all()[:20]:
            citing = citation.citing_paper
            nodes.append({'id': citing.id, 'title': citing.title, 'type': 'citing'})
            edges.append({'source': citing.id, 'target': paper.id, 'type': 'cites'})
        
        context['graph_data'] = {
            'nodes': nodes,
            'edges': edges
        }
        
        return context
