# Generated manually to add user_uuid field for frontend compatibility

import uuid

from django.db import migrations, models


def populate_user_uuid(apps, schema_editor):
    """Populate user_uuid for existing users with unique UUIDs."""
    User = apps.get_model('authentication', 'User')
    for user in User.objects.all():
        # Generate a new unique UUID for each user
        user.user_uuid = uuid.uuid4()
        user.save(update_fields=['user_uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_remove_userprofile_id_alter_userprofile_user'),
    ]

    operations = [
        # Step 1: Add field without unique constraint
        migrations.AddField(
            model_name='user',
            name='user_uuid',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text='UUID for frontend API requests (assignee, reporter, etc.)',
                null=True,  # Allow null temporarily
                db_index=False,  # No index yet
            ),
            preserve_default=False,
        ),
        # Step 2: Populate UUIDs for all existing users
        migrations.RunPython(populate_user_uuid, reverse_code=migrations.RunPython.noop),
        # Step 3: Make field non-nullable and unique
        migrations.AlterField(
            model_name='user',
            name='user_uuid',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text='UUID for frontend API requests (assignee, reporter, etc.)',
                unique=True,
                db_index=True,
            ),
        ),
    ]
