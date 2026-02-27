from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import Q, Count
from apps.papers.models import Paper, Category
from apps.accounts.models import SearchHistory, SavedSearch
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
import re

class SearchView(ListView):
    model = Paper
    template_name = 'search/results.html'
    context_object_name = 'papers'
    paginate_by = 12
    
    def get_queryset(self):
        query = self.request.GET.get('q', '')
        category = self.request.GET.get('category', '')
        author = self.request.GET.get('author', '')
        year_from = self.request.GET.get('year_from', '')
        year_to = self.request.GET.get('year_to', '')
        citation_min = self.request.GET.get('citation_min', '')
        citation_max = self.request.GET.get('citation_max', '')
        boolean_mode = self.request.GET.get('boolean', 'off')
        
        queryset = Paper.objects.filter(is_approved=True).annotate(
            citation_count_db=Count('cited_by')
        )

        if query:
            if self.request.user.is_authenticated:
                SearchHistory.objects.create(user=self.request.user, query=query)

            # Boolean search support
            if boolean_mode == 'on':
                queryset = self._apply_boolean_search(queryset, query)
            else:
                queryset = queryset.filter(
                    Q(title__icontains=query) |
                    Q(abstract__icontains=query) |
                    Q(authors__icontains=query)
                )

        if category:
            queryset = queryset.filter(categories__id=category)

        if author:
            queryset = queryset.filter(authors__icontains=author)

        if year_from:
            queryset = queryset.filter(publication_date__year__gte=year_from)

        if year_to:
            queryset = queryset.filter(publication_date__year__lte=year_to)

        if citation_min:
            queryset = queryset.filter(citation_count_db__gte=citation_min)

        if citation_max:
            queryset = queryset.filter(citation_count_db__lte=citation_max)
        
        return queryset.distinct().order_by('-created_at')
    
    def _apply_boolean_search(self, queryset, query):
        """Apply boolean search operators (AND, OR, NOT)"""
        # Simple boolean parser
        query = query.strip()
        
        # Handle NOT operator
        if ' NOT ' in query.upper():
            parts = re.split(r'\s+NOT\s+', query, flags=re.IGNORECASE)
            main_query = parts[0]
            exclude_terms = parts[1:] if len(parts) > 1 else []
            
            # Apply main query
            q_filter = Q(title__icontains=main_query) | Q(abstract__icontains=main_query) | Q(authors__icontains=main_query)
            queryset = queryset.filter(q_filter)
            
            # Exclude terms
            for term in exclude_terms:
                term = term.strip()
                queryset = queryset.exclude(
                    Q(title__icontains=term) | Q(abstract__icontains=term) | Q(authors__icontains=term)
                )
            return queryset
        
        # Handle OR operator
        if ' OR ' in query.upper():
            terms = re.split(r'\s+OR\s+', query, flags=re.IGNORECASE)
            q_filter = Q()
            for term in terms:
                term = term.strip()
                q_filter |= Q(title__icontains=term) | Q(abstract__icontains=term) | Q(authors__icontains=term)
            return queryset.filter(q_filter)
        
        # Handle AND operator (default behavior)
        if ' AND ' in query.upper():
            terms = re.split(r'\s+AND\s+', query, flags=re.IGNORECASE)
            for term in terms:
                term = term.strip()
                queryset = queryset.filter(
                    Q(title__icontains=term) | Q(abstract__icontains=term) | Q(authors__icontains=term)
                )
            return queryset
        
        # Default: simple search
        return queryset.filter(
            Q(title__icontains=query) | Q(abstract__icontains=query) | Q(authors__icontains=query)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['categories'] = Category.objects.all()
        context['selected_category'] = self.request.GET.get('category', '')
        context['author'] = self.request.GET.get('author', '')
        context['year_from'] = self.request.GET.get('year_from', '')
        context['year_to'] = self.request.GET.get('year_to', '')
        context['citation_min'] = self.request.GET.get('citation_min', '')
        context['citation_max'] = self.request.GET.get('citation_max', '')
        context['boolean_mode'] = self.request.GET.get('boolean', 'off')
        
        # Add saved searches for authenticated users
        if self.request.user.is_authenticated:
            context['saved_searches'] = SavedSearch.objects.filter(user=self.request.user)[:5]
        
        return context

class AdvancedSearchView(TemplateView):
    template_name = 'search/advanced.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

class SearchHistoryView(LoginRequiredMixin, ListView):
    model = SearchHistory
    template_name = 'search/history.html'
    context_object_name = 'searches'
    paginate_by = 20
    
    def get_queryset(self):
        return SearchHistory.objects.filter(user=self.request.user).order_by('-timestamp')

def search_suggestions(request):
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'suggestions': []})
    
    papers = Paper.objects.filter(
        title__icontains=query,
        is_approved=True
    ).values_list('title', flat=True)[:10]
    
    suggestions = list(papers)
    return JsonResponse({'suggestions': suggestions})

class PaperSearchView(SearchView):
    pass


def live_search(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    author = request.GET.get('author', '')
    year_from = request.GET.get('year_from', '')
    year_to = request.GET.get('year_to', '')

    queryset = Paper.objects.filter(is_approved=True)

    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) |
            Q(abstract__icontains=query) |
            Q(authors__icontains=query)
        )

    if category:
        queryset = queryset.filter(categories__id=category)

    if author:
        queryset = queryset.filter(authors__icontains=author)

    if year_from:
        queryset = queryset.filter(publication_date__year__gte=year_from)

    if year_to:
        queryset = queryset.filter(publication_date__year__lte=year_to)

    queryset = queryset.distinct().order_by('-created_at')[:20]

    papers = []
    for paper in queryset:
        papers.append({
            'id': paper.pk,
            'title': paper.title,
            'abstract': paper.abstract[:200] + '...' if len(paper.abstract) > 200 else paper.abstract,
            'authors': paper.authors,
            'year': paper.publication_date.year if paper.publication_date else '',
            'view_count': paper.view_count,
            'download_count': paper.download_count,
            'categories': [c.name for c in paper.categories.all()],
        })

    return JsonResponse({'papers': papers, 'count': len(papers)})



@login_required
def save_search(request):
    """Save current search query and filters"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        query = request.POST.get('query', '')
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        
        filters = {
            'category': request.POST.get('category', ''),
            'author': request.POST.get('author', ''),
            'year_from': request.POST.get('year_from', ''),
            'year_to': request.POST.get('year_to', ''),
            'citation_min': request.POST.get('citation_min', ''),
            'citation_max': request.POST.get('citation_max', ''),
            'boolean': request.POST.get('boolean', 'off'),
        }
        
        SavedSearch.objects.create(
            user=request.user,
            name=name,
            query=query,
            filters=filters
        )
        
        return JsonResponse({'success': True, 'message': 'Search saved successfully!'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_saved_search(request, pk):
    """Delete a saved search"""
    try:
        saved_search = SavedSearch.objects.get(pk=pk, user=request.user)
        saved_search.delete()
        messages.success(request, 'Saved search deleted successfully!')
    except SavedSearch.DoesNotExist:
        messages.error(request, 'Saved search not found.')
    
    return redirect('search:saved_searches')


class SavedSearchListView(LoginRequiredMixin, ListView):
    model = SavedSearch
    template_name = 'search/saved_searches.html'
    context_object_name = 'saved_searches'
    paginate_by = 20
    
    def get_queryset(self):
        return SavedSearch.objects.filter(user=self.request.user).order_by('-created_at')
