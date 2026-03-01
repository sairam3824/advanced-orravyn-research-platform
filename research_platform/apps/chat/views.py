import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import functions as db_functions
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView

from apps.chat.utils import is_offensive
from apps.groups.models import Group, GroupMember
from apps.papers.models import Paper

from .models import ChatMessage, ChatRoom

logger = logging.getLogger(__name__)

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
            logger.error("send_message_ajax error: %s", e)
            return JsonResponse({'status': 'error', 'message': 'Could not send message. Please try again.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

def generate_simple_bot_response(message, paper):
    if paper is None:
        return "I can only answer questions about papers. No paper is associated with this chat room."

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

class GroupChatRoomView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/group_room.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group_id = kwargs['group_id']

        group = get_object_or_404(Group, pk=group_id)
        get_object_or_404(GroupMember, group=group, user=self.request.user)
        
        chat_room, created = ChatRoom.objects.get_or_create(
            group=group,
            defaults={'created_by': self.request.user}
        )
        
        last_messages = ChatMessage.objects.filter(room=chat_room) \
                                        .select_related('user') \
                                        .order_by('-timestamp')[:50]
        messages = list(reversed(last_messages))

        context['group'] = group
        context['chat_room'] = chat_room
        context['messages'] = messages
        return context

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        get_object_or_404(GroupMember, group=group, user=request.user)
        
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


@login_required
def yggdrasil_rag_api(request):
    """POST — send a message, get a RAG response. Persists to DB."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        from apps.ml_engine.rag_pipeline import query_rag
        from .models import YggdrasilConversation, YggdrasilMessage

        data = json.loads(request.body)
        query = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        if not query:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # Get or create conversation
        if conversation_id:
            try:
                conversation = YggdrasilConversation.objects.get(
                    pk=conversation_id, user=request.user
                )
            except YggdrasilConversation.DoesNotExist:
                conversation = YggdrasilConversation.objects.create(user=request.user)
        else:
            conversation = YggdrasilConversation.objects.create(user=request.user)

        # Auto-title from first message
        if conversation.title == 'New conversation' or not conversation.title:
            conversation.title = query[:50] + ('...' if len(query) > 50 else '')
            conversation.save(update_fields=['title'])

        # Save user message
        YggdrasilMessage.objects.create(
            conversation=conversation,
            role=YggdrasilMessage.ROLE_USER,
            content=query,
        )

        # Run RAG
        result = query_rag(query)

        # Save bot response
        YggdrasilMessage.objects.create(
            conversation=conversation,
            role=YggdrasilMessage.ROLE_BOT,
            content=result['response'],
            sources=result['sources'],
        )

        # Touch updated_at so conversation bubbles to top of list
        YggdrasilConversation.objects.filter(pk=conversation.pk).update(
            updated_at=db_functions.Now()
        )

        return JsonResponse({
            'response': result['response'],
            'sources': result['sources'],
            'conversation_id': conversation.pk,
            'conversation_title': conversation.title,
        })
    except Exception as exc:
        logger.error("Yggdrasil RAG API error: %s", exc)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@login_required
def yggdrasil_conversations_api(request):
    """GET list of conversations. DELETE a specific one."""
    from .models import YggdrasilConversation

    if request.method == 'GET':
        convs = YggdrasilConversation.objects.filter(user=request.user).values(
            'id', 'title', 'created_at', 'updated_at'
        )
        data = []
        for c in convs:
            data.append({
                'id': c['id'],
                'title': c['title'],
                'updated_at': c['updated_at'].isoformat(),
            })
        return JsonResponse({'conversations': data})

    if request.method == 'DELETE':
        try:
            body = json.loads(request.body)
            conv_id = body.get('id')
            YggdrasilConversation.objects.filter(pk=conv_id, user=request.user).delete()
            return JsonResponse({'status': 'deleted'})
        except Exception as exc:
            logger.error("yggdrasil_conversations_api DELETE error: %s", exc)
            return JsonResponse({'error': 'Could not delete conversation.'}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def yggdrasil_conversation_messages_api(request, conversation_id):
    """GET all messages for a conversation."""
    from .models import YggdrasilConversation, YggdrasilMessage

    try:
        conversation = YggdrasilConversation.objects.get(
            pk=conversation_id, user=request.user
        )
    except YggdrasilConversation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    msgs = conversation.messages.values('role', 'content', 'sources', 'timestamp')
    data = [
        {
            'role': m['role'],
            'content': m['content'],
            'sources': m['sources'],
            'timestamp': m['timestamp'].isoformat(),
        }
        for m in msgs
    ]
    return JsonResponse({
        'messages': data,
        'title': conversation.title,
    })

def errorView(request):
    return render(request, "500.html", status=500)
