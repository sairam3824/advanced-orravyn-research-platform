from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render, redirect
from apps.papers.models import Paper, Category
from apps.accounts.models import User
from django.db.models import Count

def home_view(request):
    recent_papers = Paper.objects.filter(is_approved=True).order_by('-created_at')[:2]
    popular_categories = Category.objects.annotate(
        paper_count=Count('paper')
    ).order_by('-paper_count')[:2]

    return render(request, 'home.html', {
        'recent_papers': recent_papers,
        'popular_categories': popular_categories,
        'total_papers': Paper.objects.filter(is_approved=True).count(),
        'total_users': User.objects.count(),
        'total_categories': Category.objects.count(),
    })

def info_redirect(request):
    return redirect('about')

def privacy_view(request):
    return render(request, 'pages/privacy.html')

def terms_view(request):
    return render(request, 'pages/terms.html')

def liability_view(request):
    return render(request, 'pages/liability.html')

def disclaimer_view(request):
    return render(request, 'pages/disclaimer.html')

def about_view(request):
    return render(request, 'pages/about.html')

def team_view(request):
    return render(request, 'pages/team.html')

def opensource_view(request):
    return render(request, 'pages/opensource.html')

def contact_view(request):
    return render(request, 'pages/contact.html')

def faq_view(request):
    return render(request, 'pages/faq.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('info/', info_redirect, name='info'),
    path('privacy/', privacy_view, name='privacy'),
    path('terms/', terms_view, name='terms'),
    path('liability/', liability_view, name='liability'),
    path('disclaimer/', disclaimer_view, name='disclaimer'),
    path('about/', about_view, name='about'),
    path('team/', team_view, name='team'),
    path('open-source/', opensource_view, name='opensource'),
    path('contact/', contact_view, name='contact'),
    path('faq/', faq_view, name='faq'),
    path('api/', include('apps.api.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('papers/', include('apps.papers.urls')),
    path('groups/', include('apps.groups.urls')),
    path('chat/', include('apps.chat.urls')),
    path('search/', include('apps.search.urls')),
    path('messaging/', include('apps.messaging.urls')),
    path('analytics/', include('apps.analytics.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom 404 handler
def custom_404_view(request, exception=None):
    return render(request, '404.html', status=404)

handler404 = custom_404_view

# Catch-all so the custom 404 works even in DEBUG mode
from django.urls import re_path
urlpatterns += [re_path(r'^.*$', custom_404_view)]
