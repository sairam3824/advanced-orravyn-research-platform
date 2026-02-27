from django.core.management.base import BaseCommand
from apps.papers.models import Category


class Command(BaseCommand):
    help = 'Remove specific categories from the database'

    def handle(self, *args, **options):
        categories_to_remove = [
            'Cybersecurity',
            'Software Engineering',
            'Distributed Systems',
            'Robotics',
            'Bioinformatics',
            'Quantum Computing',
            'Human-Computer Interaction',
            'Internet of Things',
            'Blockchain',
            'Mathematics',
            'Physics',
            'Biology',
            'Chemistry',
            'Medicine',
            'Engineering',
            'Environmental Science',
            'Psychology',
            'Economics',
            'Social Sciences',
        ]

        removed_count = 0
        not_found_count = 0
        
        for cat_name in categories_to_remove:
            try:
                category = Category.objects.get(name=cat_name)
                paper_count = category.paper_set.count()
                
                if paper_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Skipped: {cat_name} (has {paper_count} papers associated)'
                        )
                    )
                else:
                    category.delete()
                    removed_count += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ Removed: {cat_name}'))
                    
            except Category.DoesNotExist:
                not_found_count += 1
                self.stdout.write(f'  Not found: {cat_name}')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
        self.stdout.write(self.style.SUCCESS(f'Removed: {removed_count} categories'))
        if not_found_count > 0:
            self.stdout.write(f'Not found: {not_found_count} categories')
        self.stdout.write(f'Remaining categories in database: {Category.objects.count()}')
