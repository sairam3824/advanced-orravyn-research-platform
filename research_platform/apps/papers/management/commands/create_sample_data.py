from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.papers.models import Paper, Category
from apps.accounts.models import UserProfile
from datetime import date, timedelta
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample data for testing'
    
    def handle(self, *args, **options):
        # Create sample users first
        users_data = [
            {'username': 'john_researcher', 'email': 'john@example.com', 'user_type': 'publisher'},
            {'username': 'jane_student', 'email': 'jane@example.com', 'user_type': 'reader'},
            {'username': 'prof_smith', 'email': 'smith@example.com', 'user_type': 'publisher'},
            {'username': 'moderator1', 'email': 'mod@example.com', 'user_type': 'moderator'},
        ]
        
        created_users = []
        for user_data in users_data:
            if not User.objects.filter(email=user_data['email']).exists():
                user = User.objects.create_user(
                    username=user_data['username'],
                    email=user_data['email'],
                    password='testpass123',
                    user_type=user_data['user_type']
                )
                UserProfile.objects.create(
                    user=user,
                    first_name=user_data['username'].split('_')[0].title(),
                    last_name=user_data['username'].split('_')[1].title(),
                    institution='Sample University'
                )
                created_users.append(user)
                self.stdout.write(f'Created user: {user.username}')
        
        # Get all categories
        categories = list(Category.objects.all())
        if not categories:
            self.stdout.write(self.style.ERROR('No categories found. Run setup_initial_data first.'))
            return
        
        # Get publisher users
        publishers = User.objects.filter(user_type__in=['publisher', 'moderator', 'admin'])
        if not publishers:
            self.stdout.write(self.style.ERROR('No publisher users found.'))
            return
        
        # Create sample papers with APPROVED status
        sample_papers = [
            {
                'title': 'Machine Learning Applications in Healthcare',
                'abstract': 'This comprehensive paper explores the various applications of machine learning algorithms in modern healthcare systems. We discuss supervised learning for diagnosis, unsupervised learning for pattern recognition, and reinforcement learning for treatment optimization. The paper includes case studies from real-world implementations and discusses ethical considerations in AI-driven healthcare.',
                'authors': 'John Doe, Jane Smith, Robert Johnson',
                'doi': '10.1000/ml-healthcare-2024',
            },
            {
                'title': 'Quantum Computing: Current State and Future Prospects',
                'abstract': 'An in-depth analysis of quantum computing technologies and their potential impact on computational science. This paper covers quantum algorithms, quantum supremacy achievements, current hardware limitations, and future research directions. We also discuss the implications for cryptography, optimization problems, and scientific simulations.',
                'authors': 'Alice Johnson, Bob Wilson, Carol Martinez',
                'doi': '10.1000/quantum-computing-2024',
            },
            {
                'title': 'Climate Change and Environmental Impact Assessment',
                'abstract': 'A comprehensive analysis of climate change effects on global ecosystems and biodiversity. This research presents new methodologies for environmental impact assessment, discusses adaptation strategies, and provides recommendations for policy makers. The study includes data from multiple continents and spans a 20-year observation period.',
                'authors': 'Carol Brown, David Lee, Emma Davis',
                'doi': '10.1000/climate-change-2024',
            },
            {
                'title': 'Artificial Intelligence in Education: Transforming Learning',
                'abstract': 'This paper examines the integration of artificial intelligence technologies in educational systems. We explore personalized learning algorithms, automated assessment tools, and intelligent tutoring systems. The research includes pilot studies from various educational institutions and discusses the challenges and opportunities in AI-driven education.',
                'authors': 'Michael Chen, Sarah Williams, James Taylor',
                'doi': '10.1000/ai-education-2024',
            },
            {
                'title': 'Blockchain Technology in Supply Chain Management',
                'abstract': 'An exploration of blockchain applications in supply chain transparency and traceability. This research presents a novel framework for implementing distributed ledger technology in complex supply networks. We discuss smart contracts, consensus mechanisms, and real-world case studies from the food and pharmaceutical industries.',
                'authors': 'Lisa Anderson, Mark Thompson, Nina Rodriguez',
                'doi': '10.1000/blockchain-supply-2024',
            },
            {
                'title': 'Renewable Energy Systems: Efficiency and Sustainability',
                'abstract': 'A technical analysis of modern renewable energy systems focusing on solar, wind, and hydroelectric power generation. This paper presents new optimization algorithms for energy grid management and discusses the economic and environmental benefits of renewable energy adoption. Includes performance data from installations across different geographical regions.',
                'authors': 'Thomas Green, Maria Gonzalez, Peter Kim',
                'doi': '10.1000/renewable-energy-2024',
            }
        ]
        
        for paper_data in sample_papers:
            if not Paper.objects.filter(title=paper_data['title']).exists():
                paper = Paper.objects.create(
                    title=paper_data['title'],
                    abstract=paper_data['abstract'],
                    authors=paper_data['authors'],
                    doi=paper_data['doi'],
                    publication_date=date.today() - timedelta(days=random.randint(1, 365)),
                    uploaded_by=random.choice(publishers),
                    is_approved=True
                )
                
                # Add random categories (1-3 categories per paper)
                num_categories = random.randint(1, min(3, len(categories)))
                selected_categories = random.sample(categories, num_categories)
                paper.categories.add(*selected_categories)
                
                self.stdout.write(f'Created paper: {paper.title}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created sample data with approved papers!')
        )
