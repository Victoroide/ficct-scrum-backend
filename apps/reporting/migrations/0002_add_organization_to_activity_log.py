# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
        ('reporting', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='activitylog',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='activity_logs',
                to='organizations.organization'
            ),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(
                fields=['organization', 'created_at'],
                name='activity_lo_organiz_idx'
            ),
        ),
    ]
