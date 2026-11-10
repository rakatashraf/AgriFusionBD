"""Accounts: custom email-login user, organizations, grants, consent."""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-login user with a small role set for the pilot (plan §1)."""

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    roles = models.JSONField(default=list, blank=True)  # ["farmer", "officer", ...]
    organization = models.ForeignKey(
        "accounts.Organization", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="members",
    )
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.name or self.email

    def has_role(self, role: str) -> bool:
        return role in (self.roles or [])


class Organization(models.Model):
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=32, default="ngo")  # ngo | dept | research
    region = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    """Explicit user↔organization link (redundant with User.organization for
    multi-org support; the pilot uses one org per user)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=32, default="member")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "organization")


class FieldGrant(models.Model):
    """A user is granted read access to a field they do not own (e.g. officer)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="field_grants")
    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="grants")
    level = models.CharField(max_length=16, default="read")  # read | write
    granted_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="granted_out")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "field")


class Consent(models.Model):
    """Farmer consent to use their field data in research exports (report §11)."""

    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="consents")
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="consents_given")
    scope = models.CharField(max_length=32, default="research_export")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-granted_at"]
