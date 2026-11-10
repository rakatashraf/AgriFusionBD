"""
Server-side role enforcement (plan §1, Phase 1; report §4).

The workspace toggle in the UI is cosmetic — these classes are the authority.
Roles are stored on ``accounts.User`` (``farmer``, ``officer``, ``researcher``,
``rover_operator``). The demo login endpoint swaps the session's user to the
seeded demo identity for the requested role; the permission classes then gate
every object query on the real user's roles.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

ROLE_FARMER = "farmer"
ROLE_OFFICER = "officer"
ROLE_RESEARCHER = "researcher"
ROLE_ROVER_OPERATOR = "rover_operator"

ALL_ROLES = (ROLE_FARMER, ROLE_OFFICER, ROLE_RESEARCHER, ROLE_ROVER_OPERATOR)


def user_roles(user) -> set[str]:
    if user is None or not user.is_authenticated:
        return set()
    try:
        return set(user.roles or [])
    except AttributeError:
        return set()


class IsFarmer(BasePermission):
    """Farmer reads/writes their own fields; officers & researchers read all."""

    def has_object_permission(self, request, view, obj):
        roles = user_roles(request.user)
        if ROLE_OFFICER in roles or ROLE_RESEARCHER in roles:
            return True
        if ROLE_FARMER in roles and getattr(obj, "farmer_id", None):
            return obj.farmer_id == request.user.pk
        return False


class CanSubmitAnalysis(BasePermission):
    """Farmers submit analyses for their own fields; officers may too."""

    def has_permission(self, request, view):
        roles = user_roles(request.user)
        return ROLE_FARMER in roles or ROLE_OFFICER in roles


class IsOfficer(BasePermission):
    def has_permission(self, request, view):
        return ROLE_OFFICER in user_roles(request.user)


class IsResearcher(BasePermission):
    def has_permission(self, request, view):
        return ROLE_RESEARCHER in user_roles(request.user)


class IsRoverOperator(BasePermission):
    def has_permission(self, request, view):
        return ROLE_ROVER_OPERATOR in user_roles(request.user)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
