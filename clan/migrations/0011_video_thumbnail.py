from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clan', '0010_initial_servers_videos'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='thumbnail_url',
            field=models.URLField(blank=True, default='', verbose_name='Превью (автоматически)'),
        ),
    ]
