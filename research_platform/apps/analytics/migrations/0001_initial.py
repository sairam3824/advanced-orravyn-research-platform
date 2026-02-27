# Generated migration for analytics app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('papers', '0008_advanced_features'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaperImpactMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_views', models.IntegerField(default=0)),
                ('total_downloads', models.IntegerField(default=0)),
                ('total_citations', models.IntegerField(default=0)),
                ('total_bookmarks', models.IntegerField(default=0)),
                ('total_shares', models.IntegerField(default=0)),
                ('total_likes', models.IntegerField(default=0)),
                ('average_rating', models.FloatField(default=0.0)),
                ('impact_score', models.FloatField(default=0.0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('paper', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='impact_metrics', to='papers.paper')),
            ],
            options={
                'db_table': 'paper_impact_metrics',
            },
        ),
        migrations.CreateModel(
            name='UserReadingStatistics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_papers_read', models.IntegerField(default=0)),
                ('total_reading_time_minutes', models.IntegerField(default=0)),
                ('papers_completed', models.IntegerField(default=0)),
                ('average_reading_speed', models.FloatField(default=0.0)),
                ('favorite_categories', models.JSONField(default=list)),
                ('reading_streak_days', models.IntegerField(default=0)),
                ('last_read_date', models.DateField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reading_stats', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_reading_statistics',
            },
        ),
        migrations.CreateModel(
            name='TrendingTopic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('paper_count', models.IntegerField(default=0)),
                ('view_count', models.IntegerField(default=0)),
                ('trend_score', models.FloatField(default=0.0)),
                ('week_start', models.DateField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='papers.category')),
            ],
            options={
                'db_table': 'trending_topics',
                'ordering': ['-trend_score', '-created_at'],
                'unique_together': {('name', 'week_start')},
            },
        ),
        migrations.CreateModel(
            name='ResearchFieldAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=200)),
                ('total_papers', models.IntegerField(default=0)),
                ('total_researchers', models.IntegerField(default=0)),
                ('total_citations', models.IntegerField(default=0)),
                ('growth_rate', models.FloatField(default=0.0)),
                ('top_keywords', models.JSONField(default=list)),
                ('month', models.DateField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'research_field_analytics',
                'ordering': ['-month'],
                'unique_together': {('field_name', 'month')},
            },
        ),
        migrations.CreateModel(
            name='CollaborationNetwork',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('collaboration_count', models.IntegerField(default=0)),
                ('strength_score', models.FloatField(default=0.0)),
                ('last_collaboration', models.DateTimeField(blank=True, null=True)),
                ('collaborator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaborations', to=settings.AUTH_USER_MODEL)),
                ('shared_papers', models.ManyToManyField(blank=True, to='papers.paper')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaboration_network', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'collaboration_networks',
                'unique_together': {('user', 'collaborator')},
            },
        ),
    ]
