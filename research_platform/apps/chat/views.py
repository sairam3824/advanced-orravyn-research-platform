import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Q, functions as db_functions
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView

# Yggdrasil rate limit: max 10 requests per user per minute
_YGG_RATE_LIMIT = 10
_YGG_RATE_WINDOW = 60  # seconds

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
        
        last_three = list(
            ChatMessage.objects.filter(room=chat_room)
            .select_related('user')
            .order_by('-timestamp')[:50]
        )
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
            return f"The abstract of this paper is: {(paper.abstract or '')[:200]}..."
        elif 'author' in message_lower:
            return f"The authors of this paper are: {paper.authors or 'Not specified'}"
        elif 'date' in message_lower or 'year' in message_lower:
            return f"This paper was published on: {paper.publication_date or 'Not available'}"
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
        return f"The abstract: {(paper.abstract or '')[:150]}..."
    elif 'author' in message_lower:
        return f"Authors: {paper.authors or 'Not specified'}"
    elif 'date' in message_lower:
        return f"Published: {paper.publication_date or 'Not available'}"
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
        # Use a subquery-based filter instead of a JOIN to avoid ordering
        # instability when a user has many messages in the same room.
        from django.db.models import Subquery, OuterRef
        rooms_with_messages = ChatMessage.objects.filter(
            room=OuterRef('pk'), user=self.request.user
        ).values('room')[:1]
        return ChatRoom.objects.filter(
            Q(created_by=self.request.user) | Q(pk__in=Subquery(rooms_with_messages))
        ).order_by('-created_at')

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
        
        last_messages = list(
            ChatMessage.objects.filter(room=chat_room)
            .select_related('user')
            .order_by('-timestamp')[:50]
        )
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


def _clean_response(text: str) -> str:
    """
    Strip markdown asterisks from LLM output so they never appear in the UI.
    Bold (**text**) and italic (*text*) markers are removed; any stray * is dropped.
    """
    import re
    # Remove bold markers: **text** → text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)
    # Remove italic markers: *text* → text
    text = re.sub(r'\*([^*\n]+?)\*', r'\1', text)
    # Drop any remaining stray asterisks
    text = text.replace('*', '')
    return text


@login_required
def yggdrasil_rag_api(request):
    """POST — send a message, run all 8 research agents, return structured response."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # ── Per-user rate limiting ────────────────────────────────────────────────
    rate_key = f"ygg_rate:{request.user.id}"
    request_count = cache.get(rate_key, 0)
    if request_count >= _YGG_RATE_LIMIT:
        return JsonResponse(
            {'error': f'Rate limit exceeded. Max {_YGG_RATE_LIMIT} requests per minute.'},
            status=429
        )
    cache.set(rate_key, request_count + 1, timeout=_YGG_RATE_WINDOW)
    # ─────────────────────────────────────────────────────────────────────────

    try:
        from apps.ml_engine.research_agents import get_research_orchestrator
        from .models import YggdrasilConversation, YggdrasilMessage

        data = json.loads(request.body)
        query           = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        session_id      = data.get('session_id') or request.COOKIES.get('ygg_session_id')

        if not query:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # ── Conversation persistence ──────────────────────────────────────
        if conversation_id:
            try:
                conversation = YggdrasilConversation.objects.get(
                    pk=conversation_id, user=request.user
                )
            except YggdrasilConversation.DoesNotExist:
                conversation = YggdrasilConversation.objects.create(user=request.user)
        else:
            conversation = YggdrasilConversation.objects.create(user=request.user)

        if conversation.title == 'New conversation' or not conversation.title:
            conversation.title = query[:50] + ('...' if len(query) > 50 else '')
            conversation.save(update_fields=['title'])

        YggdrasilMessage.objects.create(
            conversation=conversation,
            role=YggdrasilMessage.ROLE_USER,
            content=query,
        )

        # ── Run all 8 research agents ─────────────────────────────────────
        orchestrator = get_research_orchestrator()
        result = orchestrator.research(
            query=query,
            user_id=request.user.id,
            session_id=session_id,
        )

        # Strip asterisks from response before saving and returning
        clean_text = _clean_response(result.get('response', ''))

        # Save bot response
        YggdrasilMessage.objects.create(
            conversation=conversation,
            role=YggdrasilMessage.ROLE_BOT,
            content=clean_text,
            sources=result.get('sources', []),
            faithfulness_score=None,
        )

        YggdrasilConversation.objects.filter(pk=conversation.pk).update(
            updated_at=db_functions.Now()
        )

        response = JsonResponse({
            'response':           clean_text,
            'sources':            result.get('sources', []),
            'plan':               result.get('plan', {}),
            'agent_log':          result.get('agent_log', []),
            'total_ms':           result.get('total_ms', 0),
            'session_id':         result.get('session_id', ''),
            'conversation_id':    conversation.pk,
            'conversation_title': conversation.title,
        })
        # Persist session_id in cookie for multi-turn memory
        response.set_cookie(
            'ygg_session_id',
            result.get('session_id', ''),
            max_age=60 * 60 * 24 * 30,  # 30 days
            httponly=True,
            samesite='Lax',
        )
        return response

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

    msgs = conversation.messages.values('role', 'content', 'sources', 'faithfulness_score', 'timestamp')
    data = [
        {
            'role': m['role'],
            'content': m['content'],
            'sources': m['sources'],
            'faithfulness_score': m['faithfulness_score'],
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
