"""
Auth endpoints (plan §1, Phase 1):

    POST /api/v1/auth/login/   { "role": "farmer" }  → session for the seeded demo user
    POST /api/v1/auth/logout/
    GET  /api/v1/auth/me/

Demo login swaps the session user to the seeded demo identity for the requested
role. Roles are enforced server-side on every object query (see permissions.py).
"""

from django.contrib.auth import login
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record

from .models import User
from .permissions import ALL_ROLES
from .serializers import UserSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        role = (request.data.get("role") or "").strip().lower()
        if role not in ALL_ROLES:
            return Response(
                {"error": {"code": "validation_error", "message": f"role must be one of {list(ALL_ROLES)}",
                           "details": {"role": role}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Seeded demo user for this role (created by seed_demo).
        # Prefer the user whose email is the canonical {role}@pilot.example so we
        # don't pick up a stale bare-role user from an earlier seed.
        canonical_email = f"{role}@pilot.example"
        user = (
            User.objects.filter(is_active=True, email=canonical_email)
            .first()
            or User.objects.filter(is_active=True).filter(roles__contains=[role]).first()
        )
        if user is None:
            return Response(
                {"error": {"code": "not_found",
                           "message": f"No demo user seeded for role '{role}'. Run `python manage.py seed_demo`.",
                           "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Passwordless session login (demo credential is the role itself).
        user.set_unusable_password()
        user.save(update_fields=["password"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        record("auth.login", user, target_type="role", target_id=role,
               detail={"via": "demo"}, ip=_client_ip(request))
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth import logout
        user = request.user if request.user.is_authenticated else None
        logout(request)
        record("auth.logout", user, detail={}, ip=_client_ip(request))
        return Response({"ok": True})


class MeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": {"code": "unauthenticated", "message": "Not logged in.", "details": None}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(UserSerializer(request.user).data)


def _client_ip(request) -> str | None:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
