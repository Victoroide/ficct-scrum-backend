"""
Factory classes for authentication models.
"""
import factory
from factory.django import DjangoModelFactory

from apps.authentication.models import User, UserProfile


class UserFactory(DjangoModelFactory):
    """Factory for User model."""

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"testuser{n}@testexample{n}.com")
    username = factory.Sequence(lambda n: f"testuser{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Set password after user creation."""
        if not create:
            return

        if extracted:
            self.set_password(extracted)
        else:
            self.set_password("testpass123")
        self.save()


class AdminUserFactory(UserFactory):
    """Factory for admin User."""

    email = factory.Sequence(lambda n: f"admin{n}@testexample{n}.com")
    username = factory.Sequence(lambda n: f"admin{n}")
    is_staff = True
    is_superuser = True


class UserProfileFactory(DjangoModelFactory):
    """Factory for UserProfile model."""

    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    phone_number = factory.Faker("phone_number")
    bio = factory.Faker("text", max_nb_chars=200)
    location = factory.Faker("city")
    timezone = "UTC"
