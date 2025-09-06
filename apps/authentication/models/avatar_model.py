from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
import uuid
import os


def user_avatar_path(instance, filename):
    """Generate file path for user avatar uploads"""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.id}.{ext}"
    return os.path.join('avatars', 'users', filename)


class UserAvatar(models.Model):
    AVATAR_TYPE_CHOICES = [
        ('uploaded', 'Uploaded Image'),
        ('gravatar', 'Gravatar'),
        ('initials', 'Initials'),
        ('default', 'Default Avatar'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='avatar'
    )
    avatar_type = models.CharField(
        max_length=20,
        choices=AVATAR_TYPE_CHOICES,
        default='default'
    )
    image = models.ImageField(
        upload_to=user_avatar_path,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp']
            )
        ],
        help_text="Upload an image file (JPG, PNG, GIF, WebP)"
    )
    gravatar_email = models.EmailField(
        blank=True,
        help_text="Email for Gravatar service"
    )
    background_color = models.CharField(
        max_length=7,
        default='#6B73FF',
        help_text="Hex color for initials background"
    )
    text_color = models.CharField(
        max_length=7,
        default='#FFFFFF',
        help_text="Hex color for initials text"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_avatars'
        verbose_name = 'User Avatar'
        verbose_name_plural = 'User Avatars'

    def __str__(self):
        return f"Avatar for {self.user.email} ({self.avatar_type})"

    @property
    def avatar_url(self):
        """Return the appropriate avatar URL based on type"""
        if self.avatar_type == 'uploaded' and self.image:
            return self.image.url
        elif self.avatar_type == 'gravatar' and self.gravatar_email:
            import hashlib
            email_hash = hashlib.md5(self.gravatar_email.lower().encode()).hexdigest()
            return f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=200"
        elif self.avatar_type == 'initials':
            return self.generate_initials_url()
        else:
            return '/static/images/default-avatar.png'

    def generate_initials_url(self):
        """Generate a data URL for initials-based avatar"""
        initials = self.get_user_initials()
        # This would typically generate an SVG data URL
        # For now, return a placeholder
        return f"data:image/svg+xml;base64,{self.generate_initials_svg(initials)}"

    def get_user_initials(self):
        """Get user initials for avatar"""
        first_initial = self.user.first_name[0].upper() if self.user.first_name else ''
        last_initial = self.user.last_name[0].upper() if self.user.last_name else ''
        return f"{first_initial}{last_initial}" or self.user.email[0].upper()

    def generate_initials_svg(self, initials):
        """Generate base64 encoded SVG for initials"""
        import base64
        svg = f'''
        <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="200" fill="{self.background_color}"/>
            <text x="100" y="120" font-family="Arial, sans-serif" font-size="80" 
                  text-anchor="middle" fill="{self.text_color}" font-weight="bold">
                {initials}
            </text>
        </svg>
        '''
        return base64.b64encode(svg.encode()).decode()
