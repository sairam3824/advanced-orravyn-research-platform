from django.core.management.base import BaseCommand
from apps.papers.models import Category


class Command(BaseCommand):
    help = 'Create initial research categories'

    def handle(self, *args, **options):
        categories = [
            {
                'name': 'Computer Science',
                'description': 'Research in algorithms, software engineering, artificial intelligence, and computing systems'
            },
            {
                'name': 'Artificial Intelligence',
                'description': 'Machine learning, deep learning, neural networks, and AI applications'
            },
            {
                'name': 'Machine Learning',
                'description': 'Statistical learning, predictive modeling, and data-driven algorithms'
            },
            {
                'name': 'Data Science',
                'description': 'Data analysis, visualization, big data, and statistical methods'
            },
            {
                'name': 'Aerospace',
                'description': 'Aeronautics, astronautics, aircraft design, and space exploration'
            },
            {
                'name': 'Internet Of Things',
                'description': 'Connected devices, IoT systems, smart sensors, and embedded systems'
            },
            {
                'name': 'Nuclear Engineering',
                'description': 'Nuclear energy, reactor design, radiation physics, and nuclear safety'
            },
            {
                'name': 'Quantum Computing',
                'description': 'Quantum algorithms, quantum information theory, and quantum hardware'
            },
            {
                'name': 'Robotics and Control Systems',
                'description': 'Robot design, autonomous systems, control theory, and automation'
            },
            {
                'name': 'Software Engineering',
                'description': 'Software development, design patterns, testing, and software architecture'
            },
        ]

        created_count = 0
        updated_count = 0
        
        for cat_data in categories:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={'description': cat_data['description']}
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {category.name}'))
            else:
                # Update description if category already exists
                if category.description != cat_data['description']:
                    category.description = cat_data['description']
                    category.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f'↻ Updated: {category.name}'))
                else:
                    self.stdout.write(f'  Exists: {category.name}')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} categories'))
        self.stdout.write(self.style.WARNING(f'Updated: {updated_count} categories'))
        self.stdout.write(f'Total categories in database: {Category.objects.count()}')