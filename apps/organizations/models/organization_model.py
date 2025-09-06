from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
import uuid


class Organization(models.Model):
    ORGANIZATION_TYPE_CHOICES = [
        ('startup', 'Startup'),
        ('enterprise', 'Enterprise'),
        ('agency', 'Agency'),
        ('nonprofit', 'Non-profit'),
        ('education', 'Educational'),
        ('government', 'Government'),
        ('other', 'Other'),
    ]

    SUBSCRIPTION_PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=100,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message='Slug may only contain lowercase letters, numbers and hyphens.'
            )
        ]
    )
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='organizations/logos/', null=True, blank=True)
    website_url = models.URLField(blank=True)
    organization_type = models.CharField(
        max_length=20,
        choices=ORGANIZATION_TYPE_CHOICES,
        default='startup'
    )
    subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_PLAN_CHOICES,
        default='free'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_organizations'
    )
    organization_settings = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations'
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def member_count(self) -> int:
        return self.memberships.filter(is_active=True).count()

    @property
    def workspace_count(self) -> int:
        return self.workspaces.filter(is_active=True).count()
