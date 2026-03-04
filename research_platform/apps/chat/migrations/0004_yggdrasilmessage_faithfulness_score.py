from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_yggdrasilconversation_yggdrasilmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='yggdrasilmessage',
            name='faithfulness_score',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
