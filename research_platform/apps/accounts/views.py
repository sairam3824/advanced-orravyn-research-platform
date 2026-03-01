from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView
from django.views.generic.edit import UpdateView
from django.contrib import messages
from django.urls import reverse_lazy
from .models import User, UserProfile
from .forms import UserRegistrationForm, UserProfileForm, LoginForm
from apps.papers.models import Paper, Bookmark, Rating
from apps.groups.models import Group, GroupMember

class LoginView(FormView):
    template_name = 'accounts/login.html'
    form_class = LoginForm
    success_url = reverse_lazy('accounts:dashboard')
    
    def form_valid(self, form):
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = authenticate(self.request, username=email, password=password)
        if user:
            login(self.request, user)
            messages.success(self.request, 'Successfully logged in!')
            return super().form_valid(form)
        else:
            messages.error(self.request, 'Invalid credentials')
            return self.form_invalid(form)
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return super().get(request, *args, **kwargs)

class RegisterView(FormView):
    template_name = 'accounts/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        user = form.save()
        UserProfile.objects.create(
            user=user,
            first_name=form.cleaned_data.get('first_name', ''),
            last_name=form.cleaned_data.get('last_name', ''),
            institution=form.cleaned_data.get('institution', ''),
            research_interests=form.cleaned_data.get('research_interests', ''),
        )
        messages.success(self.request, 'Account created successfully! Please login.')
        return super().form_valid(form)

class LogoutView(TemplateView):
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'Successfully logged out!')
        return redirect('home')

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        context.update({
            'profile': profile,
            'uploaded_papers': Paper.objects.filter(uploaded_by=user).count(),
            'bookmarks_count': Bookmark.objects.filter(user=user).count(),
            'ratings_count': Rating.objects.filter(user=user).count(),
            'groups_count': GroupMember.objects.filter(user=user).count(),
        })
        return context

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        recent_papers = Paper.objects.filter(uploaded_by=user).order_by('-created_at')[:2]
        recent_bookmarks = Bookmark.objects.filter(user=user).select_related('paper').order_by('-created_at')[:2]
        recent_ratings = Rating.objects.filter(user=user).select_related('paper').order_by('-created_at')[:5]

        # Actual totals for stat cards (not slice lengths)
        papers_count = Paper.objects.filter(uploaded_by=user).count()
        bookmarks_count = Bookmark.objects.filter(user=user).count()
        ratings_count = Rating.objects.filter(user=user).count()

        try:
            from apps.ml_engine.models import UserRecommendation
            from apps.ml_engine.tasks import generate_recommendations
            from apps.papers.background import executor

            recs_qs = UserRecommendation.objects.filter(user=user).select_related('paper').order_by('-score')

            # Auto-generate in background if user has no recommendations yet
            if not recs_qs.exists():
                executor.submit(generate_recommendations, user.id)

            recommendations = list(recs_qs[:10])
        except ImportError:
            recommendations = []

        context.update({
            'recent_papers': recent_papers,
            'recent_bookmarks': recent_bookmarks,
            'recent_ratings': recent_ratings,
            'recommendations': recommendations,
            'papers_count': papers_count,
            'bookmarks_count': bookmarks_count,
            'ratings_count': ratings_count,
            'user_type': user.user_type,
        })
        return context


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)

class AdminDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/admin_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ['admin']:
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        pending_papers = Paper.objects.filter(is_approved=False).order_by('-created_at')
        
        recent_papers = Paper.objects.all().order_by('-created_at')[:10]
        total_users = User.objects.count()
        total_papers = Paper.objects.count()
        approved_papers = Paper.objects.filter(is_approved=True).count()
        
        context.update({
            'pending_papers': pending_papers,
            'recent_papers': recent_papers,
            'total_users': total_users,
            'total_papers': total_papers,
            'approved_papers': approved_papers,
            'pending_count': pending_papers.count(),
        })
        return context



from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from .models import UserFollow
from django.db.models import Count, Q, Sum


class PublishersListView(LoginRequiredMixin, ListView):
    """View to list all publishers with their profiles and papers"""
    model = User
    template_name = 'accounts/publishers_list.html'
    context_object_name = 'publishers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.filter(user_type='publisher').select_related('profile').annotate(
            papers_count=Count('uploaded_papers', filter=Q(uploaded_papers__is_approved=True)),
            followers_count=Count('followers')
        ).order_by('-papers_count')
        
        # Search filter
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(profile__first_name__icontains=search) |
                Q(profile__last_name__icontains=search) |
                Q(profile__institution__icontains=search) |
                Q(profile__research_interests__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        
        # Add following status for authenticated users
        if self.request.user.is_authenticated:
            following_ids = UserFollow.objects.filter(
                follower=self.request.user
            ).values_list('following_id', flat=True)
            context['following_ids'] = list(following_ids)
        else:
            context['following_ids'] = []
        
        return context


class PublisherDetailView(DetailView):
    """Detailed view of a publisher's profile"""
    model = User
    template_name = 'accounts/publisher_detail.html'
    context_object_name = 'publisher'
    
    def get_queryset(self):
        return User.objects.filter(user_type='publisher').select_related('profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publisher = self.object
        
        # Get publisher's papers
        papers = Paper.objects.filter(
            uploaded_by=publisher,
            is_approved=True
        ).order_by('-created_at')[:10]
        
        # Get statistics
        total_papers = Paper.objects.filter(uploaded_by=publisher, is_approved=True).count()
        total_views = Paper.objects.filter(uploaded_by=publisher, is_approved=True).aggregate(
            total=Sum('view_count')
        )['total'] or 0
        total_downloads = Paper.objects.filter(uploaded_by=publisher, is_approved=True).aggregate(
            total=Sum('download_count')
        )['total'] or 0
        
        # Check if current user follows this publisher
        is_following = False
        if self.request.user.is_authenticated:
            is_following = UserFollow.objects.filter(
                follower=self.request.user,
                following=publisher
            ).exists()
        
        followers_count = UserFollow.objects.filter(following=publisher).count()
        following_count = UserFollow.objects.filter(follower=publisher).count()
        
        context.update({
            'papers': papers,
            'total_papers': total_papers,
            'total_views': total_views,
            'total_downloads': total_downloads,
            'is_following': is_following,
            'followers_count': followers_count,
            'following_count': following_count,
        })
        
        return context


@login_required
def follow_user(request, user_id):
    """Follow/unfollow a user"""
    if request.method == 'POST':
        try:
            user_to_follow = User.objects.get(id=user_id)
            
            if user_to_follow == request.user:
                return JsonResponse({'success': False, 'error': 'You cannot follow yourself'})
            
            follow, created = UserFollow.objects.get_or_create(
                follower=request.user,
                following=user_to_follow
            )
            
            profile = getattr(user_to_follow, 'profile', None)
            display_name = profile.full_name if profile else user_to_follow.username
            if created:
                return JsonResponse({
                    'success': True,
                    'action': 'followed',
                    'message': f'You are now following {display_name}'
                })
            else:
                follow.delete()
                return JsonResponse({
                    'success': True,
                    'action': 'unfollowed',
                    'message': f'You unfollowed {display_name}'
                })
        
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def check_username(request):
    """AJAX endpoint — validates format rules then checks availability."""
    import re
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({'available': False, 'error': 'empty'})
    if not re.fullmatch(r'[A-Za-z0-9]+', username):
        return JsonResponse({
            'available': False,
            'error': 'no_special',
            'message': 'Only letters and numbers allowed — no special characters.',
        })
    if not re.search(r'\d', username):
        return JsonResponse({
            'available': False,
            'error': 'no_digit',
            'message': 'Username must include at least one number.',
        })
    taken = User.objects.filter(username__iexact=username).exists()
    return JsonResponse({'available': not taken})


def publishers_search(request):
    """JSON endpoint for live publisher search"""
    search = request.GET.get('search', '').strip()
    
    queryset = User.objects.filter(user_type='publisher').select_related('profile').annotate(
        papers_count=Count('uploaded_papers', filter=Q(uploaded_papers__is_approved=True)),
        followers_count=Count('followers')
    ).order_by('-papers_count')
    
    if search:
        queryset = queryset.filter(
            Q(profile__first_name__icontains=search) |
            Q(profile__last_name__icontains=search) |
            Q(profile__institution__icontains=search) |
            Q(profile__research_interests__icontains=search)
        )
    
    publishers = []
    for pub in queryset[:20]:  # Limit to 20 results
        profile = getattr(pub, 'profile', None)
        if profile is None:
            continue
        research_interests = profile.research_interests or ''
        publishers.append({
            'id': pub.id,
            'full_name': profile.full_name,
            'institution': profile.institution or '',
            'orcid': profile.orcid or '',
            'research_interests': research_interests[:100] + '...' if len(research_interests) > 100 else research_interests,
            'papers_count': pub.papers_count,
            'followers_count': pub.followers_count,
            'h_index': profile.h_index,
            'is_verified': profile.is_credentials_verified,
            'avatar': profile.avatar.url if profile.avatar else None,
        })
    
    return JsonResponse({'publishers': publishers, 'count': len(publishers)})


class UserPublicProfileView(DetailView):
    """Public profile view for any user"""
    model = User
    template_name = 'accounts/public_profile.html'
    context_object_name = 'profile_user'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.object
        
        # Get user's papers if they're a publisher
        if profile_user.user_type == 'publisher':
            papers = Paper.objects.filter(
                uploaded_by=profile_user,
                is_approved=True
            ).order_by('-created_at')[:10]
            context['papers'] = papers
            context['total_papers'] = Paper.objects.filter(
                uploaded_by=profile_user,
                is_approved=True
            ).count()
        
        # Check if current user follows this user
        is_following = False
        if self.request.user.is_authenticated and self.request.user != profile_user:
            is_following = UserFollow.objects.filter(
                follower=self.request.user,
                following=profile_user
            ).exists()
        
        followers_count = UserFollow.objects.filter(following=profile_user).count()
        following_count = UserFollow.objects.filter(follower=profile_user).count()
        
        context.update({
            'is_following': is_following,
            'followers_count': followers_count,
            'following_count': following_count,
        })
        
        return context
