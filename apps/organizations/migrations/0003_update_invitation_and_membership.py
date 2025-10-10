# Generated migration for invitation system enhancements

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0002_organizationinvitation'),
    ]

    operations = [
        # Update OrganizationInvitation status choices (cancelled -> revoked)
        migrations.AlterField(
            model_name='organizationinvitation',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('accepted', 'Accepted'),
                    ('declined', 'Declined'),
                    ('expired', 'Expired'),
                    ('revoked', 'Revoked'),
                ],
                default='pending',
                max_length=20
            ),
        ),
        
        # Add indexes to OrganizationInvitation
        migrations.AddIndex(
            model_name='organizationinvitation',
            index=models.Index(fields=['token'], name='organizatio_token_idx'),
        ),
        migrations.AddIndex(
            model_name='organizationinvitation',
            index=models.Index(fields=['email'], name='organizatio_email_idx'),
        ),
        migrations.AddIndex(
            model_name='organizationinvitation',
            index=models.Index(fields=['status'], name='organizatio_status_idx'),
        ),
        
        # Add invitation field to OrganizationMembership
        migrations.AddField(
            model_name='organizationmembership',
            name='invitation',
            field=models.ForeignKey(
                blank=True,
                help_text='The invitation that originated this membership',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='memberships',
                to='organizations.organizationinvitation'
            ),
        ),
    ]
