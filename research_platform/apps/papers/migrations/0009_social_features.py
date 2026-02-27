# Generated migration for social features

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0008_advanced_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaperLike',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='likes', to='papers.paper')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paper_likes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'paper_likes',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'paper')},
            },
        ),
        migrations.CreateModel(
            name='PaperShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('twitter', 'Twitter'), ('linkedin', 'LinkedIn'), ('facebook', 'Facebook'), ('email', 'Email'), ('link', 'Copy Link')], max_length=20)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='papers.paper')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paper_shares', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'paper_shares',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PaperComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('is_edited', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='papers.paper')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='papers.papercomment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paper_comments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'paper_comments',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='PeerReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_review', 'In Review'), ('completed', 'Completed')], default='pending', max_length=20)),
                ('recommendation', models.CharField(blank=True, choices=[('accept', 'Accept'), ('minor_revision', 'Minor Revision'), ('major_revision', 'Major Revision'), ('reject', 'Reject')], max_length=20, null=True)),
                ('originality_score', models.IntegerField(blank=True, null=True)),
                ('methodology_score', models.IntegerField(blank=True, null=True)),
                ('clarity_score', models.IntegerField(blank=True, null=True)),
                ('significance_score', models.IntegerField(blank=True, null=True)),
                ('strengths', models.TextField(blank=True)),
                ('weaknesses', models.TextField(blank=True)),
                ('detailed_comments', models.TextField(blank=True)),
                ('confidential_comments', models.TextField(blank=True)),
                ('is_anonymous', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='peer_reviews', to='papers.paper')),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews_given', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'peer_reviews',
                'ordering': ['-created_at'],
                'unique_together': {('paper', 'reviewer')},
            },
        ),
        migrations.CreateModel(
            name='ResearchBlogPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('slug', models.SlugField(max_length=350, unique=True)),
                ('content', models.TextField()),
                ('excerpt', models.TextField(blank=True, max_length=500)),
                ('featured_image', models.ImageField(blank=True, null=True, upload_to='blog/')),
                ('tags', models.JSONField(default=list)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('published', 'Published')], default='draft', max_length=20)),
                ('view_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blog_posts', to=settings.AUTH_USER_MODEL)),
                ('related_papers', models.ManyToManyField(blank=True, related_name='blog_posts', to='papers.paper')),
            ],
            options={
                'db_table': 'research_blog_posts',
                'ordering': ['-published_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BlogComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('blog_post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='papers.researchblogpost')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='papers.blogcomment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blog_comments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'blog_comments',
                'ordering': ['created_at'],
            },
        ),
    ]
