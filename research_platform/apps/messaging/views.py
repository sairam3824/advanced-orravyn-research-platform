from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.db.models import Q, Max
from django.contrib import messages as django_messages
from .models import Conversation, Message, Notification
from apps.accounts.models import User


class ConversationListView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = 'messaging/conversations.html'
    context_object_name = 'conversations'
    
    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user
        ).annotate(
            last_message_time=Max('messages__created_at')
        ).order_by('-last_message_time')


class ConversationDetailView(LoginRequiredMixin, DetailView):
    model = Conversation
    template_name = 'messaging/conversation_detail.html'
    context_object_name = 'conversation'
    
    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Mark messages as read
        Message.objects.filter(
            conversation=self.object
        ).exclude(sender=self.request.user).update(is_read=True)
        return context


@login_required
def start_conversation(request, user_id):
    """Start a new conversation with a user"""
    other_user = get_object_or_404(User, id=user_id)
    
    if other_user == request.user:
        django_messages.error(request, 'You cannot message yourself.')
        return redirect('messaging:conversations')
    
    # Check if conversation already exists
    existing = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()
    
    if existing:
        return redirect('messaging:conversation_detail', pk=existing.pk)
    
    # Create new conversation
    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)
    
    return redirect('messaging:conversation_detail', pk=conversation.pk)


@login_required
def send_message(request, conversation_id):
    """Send a message in a conversation"""
    if request.method == 'POST':
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user
        )
        
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'success': False, 'error': 'Message cannot be empty'})
        
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content
        )
        
        # Create notification for other participants
        for participant in conversation.participants.exclude(id=request.user.id):
            Notification.objects.create(
                user=participant,
                notification_type='message',
                title='New Message',
                message=f'{request.user.username} sent you a message',
                link=f'/messaging/conversations/{conversation.id}/'
            )
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'sender': request.user.username,
            'content': message.content,
            'created_at': message.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'messaging/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    notification.is_read = True
    notification.save()
    
    if notification.link:
        return redirect(notification.link)
    return redirect('messaging:notifications')


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
def get_unread_count(request):
    """Get count of unread notifications and messages"""
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    unread_messages = Message.objects.filter(
        conversation__participants=request.user
    ).exclude(sender=request.user).filter(is_read=False).count()
    
    return JsonResponse({
        'notifications': unread_notifications,
        'messages': unread_messages,
        'total': unread_notifications + unread_messages
    })
