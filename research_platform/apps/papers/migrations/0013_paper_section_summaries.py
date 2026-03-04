from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0012_paper_archive_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='paper',
            name='section_summaries',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
