from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """The shape the frontend ``types.ts`` ``User`` expects (camelCase)."""

    class Meta:
        model = User
        fields = ["id", "email", "name", "roles", "organization"]
        read_only_fields = fields

    def to_representation(self, instance):
        return {
            "id": str(instance.pk),
            "email": instance.email,
            "name": instance.name,
            "roles": instance.roles or [],
            "organization": instance.organization.name if instance.organization else None,
        }
