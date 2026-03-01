from django.core.management.base import BaseCommand
from apps.ml_engine.recommendation_engine import ImprovedRecommendationEngine
from apps.accounts.models import User


class Command(BaseCommand):
    help = (
        'Build ML embeddings for all approved papers and optionally generate '
        'recommendations for every active user. Run this once to bootstrap the '
        'recommendation system, or after bulk paper imports.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--for-all-users',
            action='store_true',
            help='Also generate recommendations for every active user after building embeddings.',
        )

    def handle(self, *args, **options):
        engine = ImprovedRecommendationEngine()

        self.stdout.write('Building paper embeddings...')
        engine.build_embeddings()
        self.stdout.write(self.style.SUCCESS('Embeddings built successfully.'))

        if options['for_all_users']:
            users = User.objects.filter(is_active=True)
            self.stdout.write(f'Generating recommendations for {users.count()} users...')
            ok = 0
            for user in users:
                try:
                    ranked = engine.hybrid_recommend(user)
                    engine.save_recommendations(user, ranked)
                    self.stdout.write(f'  ✓ {user.username}: {len(ranked)} recommendations')
                    ok += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ {user.username}: {e}'))
            self.stdout.write(self.style.SUCCESS(f'Done — {ok}/{users.count()} users updated.'))
