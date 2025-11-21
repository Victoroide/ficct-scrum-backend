# Generated migration for changing diagram_data from TextField to JSONField

from django.db import migrations, models


def clear_cache_before_migration(apps, schema_editor):
    """
    Clear all diagram cache before migration.
    
    This is safe because DiagramCache only stores cached diagram data,
    not critical business data. Cache will regenerate on next request.
    """
    DiagramCache = apps.get_model('reporting', 'DiagramCache')
    count = DiagramCache.objects.count()
    DiagramCache.objects.all().delete()
    print(f"Cleared {count} cached diagrams (will regenerate on next request)")


def restore_dummy_data(apps, schema_editor):
    """Reverse migration: No-op, cache was cleared."""


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0002_add_organization_to_activity_log'),
    ]

    operations = [
        # First, clear all cached diagrams (safe - will regenerate)
        migrations.RunPython(
            clear_cache_before_migration,
            reverse_code=restore_dummy_data,
        ),
        # Then change the field type
        migrations.AlterField(
            model_name='diagramcache',
            name='diagram_data',
            field=models.JSONField(
                default=dict,
                help_text="Diagram data as JSON object (for JSON format) or string (for SVG/PNG)"
            ),
        ),
    ]
