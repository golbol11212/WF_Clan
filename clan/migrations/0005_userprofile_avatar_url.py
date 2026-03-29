from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clan', '0004_discordmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar_url',
            field=models.URLField(blank=True, default='', max_length=512, verbose_name='Аватар Steam'),
        ),
    ]
