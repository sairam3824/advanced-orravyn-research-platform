from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0011_papertag_papercomparison_papertagging'),
    ]

    operations = [
        migrations.AddField(
            model_name='paper',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='paper',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
