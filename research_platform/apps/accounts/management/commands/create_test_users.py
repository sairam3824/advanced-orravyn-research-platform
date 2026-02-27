from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Create test users for development'
    
    def handle(self, *args, **options):
        test_users = [
            {
                'username': 'admin_user',
                'email': 'admin@test.com',
                'password': 'testpass123',
                'user_type': 'admin',
                'first_name': 'Admin',
                'last_name': 'User'
            },
            {
                'username': 'moderator_user',
                'email': 'moderator@test.com',
                'password': 'testpass123',
                'user_type': 'moderator',
                'first_name': 'Moderator',
                'last_name': 'User'
            },
            {
                'username': 'publisher_user',
                'email': 'publisher@test.com',
                'password': 'testpass123',
                'user_type': 'publisher',
                'first_name': 'Publisher',
                'last_name': 'User'
            },
            {
                'username': 'reader_user',
                'email': 'reader@test.com',
                'password': 'testpass123',
                'user_type': 'reader',
                'first_name': 'Reader',
                'last_name': 'User'
            }
        ]
        
        for user_data in test_users:
            if not User.objects.filter(email=user_data['email']).exists():
                profile_data = {
                    'first_name': user_data.pop('first_name'),
                    'last_name': user_data.pop('last_name')
                }
                
                user = User.objects.create_user(**user_data)
                UserProfile.objects.create(user=user, **profile_data)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Created user: {user.username} ({user.user_type})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'User already exists: {user_data["email"]}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Test users creation completed!')
        )
