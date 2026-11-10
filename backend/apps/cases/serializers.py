from rest_framework import serializers

from .models import AssistanceCase, CaseMessage


class CaseMessageSerializer(serializers.Serializer):
    id = serializers.CharField()
    authorRole = serializers.CharField()
    body = serializers.CharField()
    at = serializers.DateTimeField()


class CaseSerializer(serializers.Serializer):
    id = serializers.CharField()
    fieldId = serializers.CharField()
    farmerId = serializers.CharField()
    subject = serializers.CharField()
    body = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    decision = serializers.CharField(allow_blank=True)
    decisionNote = serializers.CharField(allow_blank=True, source="decision_note")
    messages = CaseMessageSerializer(many=True, read_only=True)
    createdAt = serializers.DateTimeField()
    updatedAt = serializers.DateTimeField()


def serialize_case(c: AssistanceCase) -> dict:
    return {
        "id": f"case-{c.pk}",
        "fieldId": c.field.slug,
        "farmerId": f"u-{c.farmer.pk}",
        "subject": c.subject,
        "body": c.body,
        "status": c.status,
        "decision": c.decision,
        "decisionNote": c.decision_note,
        "messages": [
            {
                "id": f"m-{m.pk}",
                "authorRole": m.author_role,
                "body": m.body,
                "at": m.created_at,
            }
            for m in c.messages.all()
        ],
        "createdAt": c.created_at,
        "updatedAt": c.updated_at,
    }
