import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ChatRoom, ChatMessage

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        user = self.scope['user']
        
        # Save message to database
        await self.save_message(self.room_id, user, message)
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': user.username,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Generate bot response if needed
        if message.startswith('@bot'):
            bot_response = await self.generate_bot_response(message, self.room_id)
            await self.save_message(self.room_id, None, bot_response, is_bot=True)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': bot_response,
                    'user': 'Research Bot',
                    'timestamp': timezone.now().isoformat(),
                    'is_bot': True
                }
            )
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
    
    @database_sync_to_async
    def save_message(self, room_id, user, message, is_bot=False):
        room = ChatRoom.objects.get(id=room_id)
        return ChatMessage.objects.create(
            room=room,
            user=user,
            message=message,
            is_bot_message=is_bot
        )
    
    @database_sync_to_async
    def generate_bot_response(self, message, room_id):
        # Simple bot response - can be enhanced with AI
        return f"I received your message: {message[4:]}. This is a simple bot response."
