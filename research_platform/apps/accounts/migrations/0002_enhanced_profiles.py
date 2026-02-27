# Generated migration for enhanced user profiles

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='orcid',
            field=models.CharField(blank=True, help_text='ORCID iD (e.g., 0000-0002-1825-0097)', max_length=19),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='h_index',
            field=models.IntegerField(default=0, help_text='H-index score'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_credentials_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='credentials_document',
            field=models.FileField(blank=True, null=True, upload_to='credentials/'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='website',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='google_scholar',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='research_gate',
            field=models.URLField(blank=True),
        ),
        migrations.CreateModel(
            name='SavedSearch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('query', models.TextField()),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_searches', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'saved_searches',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ResearchInterestTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'research_interest_tags',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='UserResearchInterest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.researchinteresttag')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interest_tags', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_research_interests',
                'unique_together': {('user', 'tag')},
            },
        ),
        migrations.CreateModel(
            name='UserFollow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('follower', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='following', to=settings.AUTH_USER_MODEL)),
                ('following', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='followers', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_follows',
                'ordering': ['-created_at'],
                'unique_together': {('follower', 'following')},
            },
        ),
    ]
