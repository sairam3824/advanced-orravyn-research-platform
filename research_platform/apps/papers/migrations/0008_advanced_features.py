# Generated migration for advanced paper features

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0007_pdf_path_max_length'),
        ('groups', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='readingprogress',
            name='reading_time_minutes',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='PaperVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.IntegerField()),
                ('pdf_path', models.FileField(max_length=500, upload_to='papers/versions/')),
                ('changes_description', models.TextField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='papers.paper')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'paper_versions',
                'ordering': ['-version_number'],
                'unique_together': {('paper', 'version_number')},
            },
        ),
        migrations.CreateModel(
            name='RelatedPaper',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('similarity_score', models.FloatField(default=0.0)),
                ('relation_type', models.CharField(choices=[('similar', 'Similar Topic'), ('cited', 'Cited By'), ('cites', 'Cites'), ('same_author', 'Same Author')], max_length=50)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_papers', to='papers.paper')),
                ('related_to', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_from', to='papers.paper')),
            ],
            options={
                'db_table': 'related_papers',
                'unique_together': {('paper', 'related_to')},
            },
        ),
        migrations.CreateModel(
            name='PaperAnnotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_number', models.IntegerField()),
                ('annotation_text', models.TextField()),
                ('highlight_text', models.TextField(blank=True)),
                ('position_data', models.JSONField(default=dict)),
                ('is_public', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to='papers.paper')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'paper_annotations',
                'ordering': ['page_number', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='ReadingList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('is_public', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reading_lists', to=settings.AUTH_USER_MODEL)),
                ('shared_with', models.ManyToManyField(blank=True, related_name='shared_reading_lists', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'reading_lists',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ReadingListPaper',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('notes', models.TextField(blank=True)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='papers.paper')),
                ('reading_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='papers.readinglist')),
            ],
            options={
                'db_table': 'reading_list_papers',
                'ordering': ['-added_at'],
                'unique_together': {('reading_list', 'paper')},
            },
        ),
        migrations.AddField(
            model_name='readinglist',
            name='papers',
            field=models.ManyToManyField(through='papers.ReadingListPaper', to='papers.paper'),
        ),
        migrations.CreateModel(
            name='PaperCollection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paper_collections', to='groups.group')),
                ('papers', models.ManyToManyField(related_name='collections', to='papers.paper')),
            ],
            options={
                'db_table': 'paper_collections',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ResearchProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[('planning', 'Planning'), ('active', 'Active'), ('completed', 'Completed'), ('on_hold', 'On Hold')], default='planning', max_length=20)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='research_projects', to='groups.group')),
                ('members', models.ManyToManyField(blank=True, related_name='research_projects_member', to=settings.AUTH_USER_MODEL)),
                ('papers', models.ManyToManyField(blank=True, related_name='research_projects', to='papers.paper')),
            ],
            options={
                'db_table': 'research_projects',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ProjectTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('todo', 'To Do'), ('in_progress', 'In Progress'), ('completed', 'Completed')], default='todo', max_length=20)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='papers.researchproject')),
            ],
            options={
                'db_table': 'project_tasks',
                'ordering': ['due_date', 'created_at'],
            },
        ),
    ]
