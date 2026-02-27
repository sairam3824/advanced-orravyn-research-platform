from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, ListView
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db import models
from .models import ChatRoom, ChatMessage
from apps.papers.models import Paper
from apps.groups.models import Group
from apps.chat.utils import is_offensive
import json

class ChatRoomView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/room.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paper_id = kwargs['paper_id']
        
        paper = get_object_or_404(Paper, pk=paper_id, is_approved=True)
        
        chat_room, created = ChatRoom.objects.get_or_create(
            paper=paper,
            defaults={'created_by': self.request.user}
        )
        
        last_three = ChatMessage.objects.filter(room=chat_room) \
                                        .select_related('user') \
                                        .order_by('-timestamp')[:50]
        messages = list(reversed(last_three))

        context['paper'] = paper
        context['chat_room'] = chat_room
        context['messages'] = messages
        
        return context
    
    def post(self, request, paper_id):
        paper = get_object_or_404(Paper, pk=paper_id, is_approved=True)
        chat_room, created = ChatRoom.objects.get_or_create(
            paper=paper,
            defaults={'created_by': request.user}
        )
        
        message_text = request.POST.get('message', '').strip()
        if message_text:
            if is_offensive(message_text):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': 'Message flagged as offensive'})
                messages.error(request, "Your message was blocked as offensive.")
                return redirect('chat:paper_chat', paper_id=paper_id)
            chat_message = ChatMessage.objects.create(
                room=chat_room,
                user=request.user,
                message=message_text
            )
            
            if message_text.startswith('@bot'):
                bot_response = self.generate_bot_response(message_text, paper)
                ChatMessage.objects.create(
                    room=chat_room,
                    user=None,  # Bot messages have no user
                    message=bot_response,
                    is_bot_message=True
                )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Message sent'})
        
        return redirect('chat:paper_chat', paper_id=paper_id)
    
    def generate_bot_response(self, message, paper):
        message_lower = message.lower()
        
        if 'abstract' in message_lower:
            return f"The abstract of this paper is: {paper.abstract[:200]}..."
        elif 'author' in message_lower:
            return f"The authors of this paper are: {paper.authors}"
        elif 'date' in message_lower or 'year' in message_lower:
            return f"This paper was published on: {paper.publication_date}"
        elif 'category' in message_lower or 'topic' in message_lower:
            categories = ", ".join([cat.name for cat in paper.categories.all()])
            return f"This paper belongs to the following categories: {categories}"
        else:
            return "I'm a research assistant bot. You can ask me about the paper's abstract, authors, publication date, or categories."

@login_required
def send_message_ajax(request, room_id):
    if request.method == 'POST':
        try:
            chat_room = get_object_or_404(ChatRoom, pk=room_id)
            message_text = request.POST.get('message', '').strip()
            
            if message_text:
                if is_offensive(message_text):
                    return JsonResponse({'status': 'error', 'message': 'Message flagged as offensive'})
                chat_message = ChatMessage.objects.create(
                    room=chat_room,
                    user=request.user,
                    message=message_text
                )
                
                response_data = {
                    'status': 'success',
                    'message_id': chat_message.id,
                    'username': request.user.username,
                    'message': message_text,
                    'timestamp': chat_message.timestamp.strftime('%b %d, %H:%M')
                }
                
                if message_text.startswith('@bot'):
                    bot_response = generate_simple_bot_response(message_text, chat_room.paper)
                    bot_message = ChatMessage.objects.create(
                        room=chat_room,
                        user=None,
                        message=bot_response,
                        is_bot_message=True
                    )
                    response_data['bot_response'] = {
                        'message_id': bot_message.id,
                        'message': bot_response,
                        'timestamp': bot_message.timestamp.strftime('%b %d, %H:%M')
                    }
                
                return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

def generate_simple_bot_response(message, paper):
    message_lower = message.lower()
    
    if 'abstract' in message_lower:
        return f"The abstract: {paper.abstract[:150]}..."
    elif 'author' in message_lower:
        return f"Authors: {paper.authors}"
    elif 'date' in message_lower:
        return f"Published: {paper.publication_date}"
    else:
        return "I can help you with information about this paper's abstract, authors, or publication date."

class ChatDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room_id = kwargs['room_id']
        chat_room = get_object_or_404(ChatRoom, pk=room_id)
        
        context['chat_room'] = chat_room
        context['paper'] = chat_room.paper
        context['messages'] = ChatMessage.objects.filter(room=chat_room).select_related('user').order_by('timestamp')
        
        return context

class MyChatRoomsView(LoginRequiredMixin, ListView):
    model = ChatRoom
    template_name = 'chat/my_chats.html'
    context_object_name = 'chat_rooms'
    paginate_by = 12
    
    def get_queryset(self):
        return ChatRoom.objects.filter(
            models.Q(created_by=self.request.user) |
            models.Q(messages__user=self.request.user)
        ).distinct().order_by('-created_at')

class GroupChatRoomView(ChatRoomView):
    template_name = 'chat/group_room.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group_id = kwargs['group_id']
        
        group = get_object_or_404(Group, pk=group_id)
        chat_room, created = ChatRoom.objects.get_or_create(
            group=group,
            defaults={'created_by': self.request.user}
        )
        
        last_three = ChatMessage.objects.filter(room=chat_room) \
                                        .select_related('user') \
                                        .order_by('-timestamp')[:50]
        messages = list(reversed(last_three))

        context['group'] = group
        context['chat_room'] = chat_room
        context['messages'] = messages
        return context

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        chat_room, created = ChatRoom.objects.get_or_create(
            group=group,
            defaults={'created_by': request.user}
        )
        
        message_text = request.POST.get('message', '').strip()
        if message_text:
            if is_offensive(message_text):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Message flagged as offensive'})
                messages.error(request, "Your message was blocked as offensive.")
                return redirect('chat:group_chat', group_id=group_id)
            ChatMessage.objects.create(
                room=chat_room,
                user=request.user,
                message=message_text
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Message sent'})
    
        return redirect('chat:group_chat', group_id=group_id)

@login_required
def yggdrasil_chatbot_view(request):
    return render(request, 'chat/yggdrasil_chatbot.html')

def errorView(request):
    return render(request, "500.html", status=500)
