from django.core.management.base import BaseCommand
from apps.papers.models import Category
from apps.accounts.models import User

class Command(BaseCommand):
    help = 'Setup initial data for the platform'
    
    def handle(self, *args, **options):
        categories = [
            'Computer Science', 'Mathematics', 'Physics', 'Chemistry',
            'Biology', 'Medicine', 'Engineering', 'Psychology',
            'Economics', 'Social Sciences'
        ]
        
        for cat_name in categories:
            Category.objects.get_or_create(
                name=cat_name,
                defaults={'description': f'Papers related to {cat_name}'}
            )
        
        if not User.objects.filter(email='admin@example.com').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123',
                user_type='admin'
            )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully setup initial data')
        )
