from django.core.management.base import BaseCommand
from apps.papers.models import Paper


class Command(BaseCommand):
    help = 'Check pending papers in the database'

    def handle(self, *args, **options):
        pending_papers = Paper.objects.filter(is_approved=False)
        approved_papers = Paper.objects.filter(is_approved=True)
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Paper Status Report ==='))
        self.stdout.write(f'Total papers: {Paper.objects.count()}')
        self.stdout.write(f'Pending approval: {pending_papers.count()}')
        self.stdout.write(f'Approved: {approved_papers.count()}')
        
        if pending_papers.exists():
            self.stdout.write(self.style.WARNING(f'\n=== Pending Papers ==='))
            for paper in pending_papers:
                self.stdout.write(f'ID: {paper.id}')
                self.stdout.write(f'Title: {paper.title}')
                self.stdout.write(f'Uploaded by: {paper.uploaded_by.username} ({paper.uploaded_by.user_type})')
                self.stdout.write(f'PDF: {paper.pdf_path.name if paper.pdf_path else "No PDF"}')
                self.stdout.write(f'Created: {paper.created_at}')
                self.stdout.write('-' * 50)
        else:
            self.stdout.write(self.style.WARNING('\nNo pending papers found.'))
