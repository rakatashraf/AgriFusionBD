"""
Case endpoints (plan §2):

    GET/POST  /cases
    PATCH     /cases/{id}          (accept / question / reject)
    POST      /cases/{id}/messages
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import user_roles, ROLE_FARMER, ROLE_OFFICER
from apps.audit.services import record
from apps.farms.models import Field

from .models import AssistanceCase, CaseMessage, CaseReview
from .serializers import serialize_case


class CaseListCreateView(APIView):
    """GET /cases (list for the user) + POST /cases (farmer opens one)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = user_roles(request.user)
        qs = AssistanceCase.objects.select_related("field", "farmer", "officer")
        if ROLE_OFFICER in roles:
            qs = qs.filter(officer=request.user)
        else:
            qs = qs.filter(farmer=request.user)
        field_slug = request.query_params.get("field")
        if field_slug:
            qs = qs.filter(field__slug=field_slug)
        qs = qs.prefetch_related("messages").order_by("-updated_at")[:50]
        return Response([serialize_case(c) for c in qs])

    def post(self, request):
        if ROLE_FARMER not in user_roles(request.user):
            return Response(
                {"error": {"code": "forbidden", "message": "Only farmers can open cases.", "details": None}},
                status=status.HTTP_403_FORBIDDEN,
            )
        field_slug = request.data.get("fieldId")
        try:
            field = Field.objects.get(slug=field_slug, farmer=request.user)
        except Field.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Field not found (must be yours).", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        case = AssistanceCase.objects.create(
            field=field,
            farmer=request.user,
            subject=request.data.get("subject", "Assistance request"),
            body=request.data.get("body", ""),
            status="open",
        )
        first_body = request.data.get("body")
        if first_body:
            CaseMessage.objects.create(case=case, author=request.user, author_role="farmer", body=first_body)
        record("case.create", request.user, target_type="case", target_id=str(case.pk), ip=_ip(request))
        return Response(serialize_case(case), status=status.HTTP_201_CREATED)


class CaseDetailView(APIView):
    """GET/PATCH /cases/{id} — PATCH carries the accept/question/reject decision."""

    permission_classes = [IsAuthenticated]

    def _get(self, pk, request):
        c = AssistanceCase.objects.prefetch_related("messages").select_related(
            "field", "farmer", "officer"
        ).filter(pk=pk)
        roles = user_roles(request.user)
        if ROLE_OFFICER in roles:
            c = c.filter(officer=request.user)
        else:
            c = c.filter(farmer=request.user)
        try:
            return c.first()
        except Exception:
            return None

    def get(self, request, pk):
        c = self._get(pk, request)
        if c is None:
            return Response(
                {"error": {"code": "not_found", "message": "Case not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_case(c))

    def patch(self, request, pk):
        c = self._get(pk, request)
        if c is None:
            return Response(
                {"error": {"code": "not_found", "message": "Case not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Only the assigned officer decides.
        if ROLE_OFFICER not in user_roles(request.user):
            return Response(
                {"error": {"code": "forbidden", "message": "Only the assigned officer can decide.", "details": None}},
                status=status.HTTP_403_FORBIDDEN,
            )
        decision = request.data.get("decision")
        if decision not in ("accept", "question", "reject"):
            return Response(
                {"error": {"code": "validation_error", "message": "decision must be accept|question|reject",
                           "details": {"decision": decision}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        c.decision = decision
        c.decision_note = request.data.get("note", "")
        c.status = {"accept": "accepted", "question": "questioned", "reject": "rejected"}[decision]
        c.officer = request.user
        c.save(update_fields=["decision", "decision_note", "status", "officer", "updated_at"])
        CaseReview.objects.create(case=c, reviewer=request.user, decision=decision,
                                  note=request.data.get("note", ""))
        record("case.decide", request.user, target_type="case", target_id=str(c.pk),
               detail={"decision": decision}, ip=_ip(request))
        return Response(serialize_case(c))


class CaseMessageView(APIView):
    """POST /cases/{id}/messages — a participant adds to the thread."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        c = AssistanceCase.objects.filter(pk=pk).first()
        if c is None:
            return Response(
                {"error": {"code": "not_found", "message": "Case not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        roles = user_roles(request.user)
        if request.user.pk not in (c.farmer_id, c.officer_id):
            return Response(
                {"error": {"code": "forbidden", "message": "Not a participant.", "details": None}},
                status=status.HTTP_403_FORBIDDEN,
            )
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response(
                {"error": {"code": "validation_error", "message": "body is required.", "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        m = CaseMessage.objects.create(
            case=c, author=request.user,
            author_role="officer" if request.user.pk == c.officer_id else "farmer",
            body=body,
        )
        return Response({
            "id": f"m-{m.pk}", "authorRole": m.author_role, "body": m.body, "at": m.created_at,
        }, status=status.HTTP_201_CREATED)


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
