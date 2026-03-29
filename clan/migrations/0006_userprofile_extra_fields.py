from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clan', '0005_userprofile_avatar_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='display_name',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='Отображаемое имя'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='discord_tag',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='Discord'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='region',
            field=models.CharField(
                choices=[('EU', 'EU'), ('RU', 'RU'), ('NA', 'NA'), ('ASIA', 'ASIA')],
                default='EU', max_length=8, verbose_name='Регион',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='bio',
            field=models.TextField(blank=True, default='', max_length=300, verbose_name='О себе'),
        ),
    ]
