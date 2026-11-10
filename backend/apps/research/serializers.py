from rest_framework import serializers

from .models import ExportJob


class ExportJobSerializer(serializers.Serializer):
    id = serializers.CharField()
    scope = serializers.CharField()
    format = serializers.CharField()
    status = serializers.CharField()
    rowCount = serializers.IntegerField()
    provenance = serializers.DictField()
    createdAt = serializers.DateTimeField()
    completedAt = serializers.DateTimeField(allow_null=True)


def serialize_job(j: ExportJob) -> dict:
    return {
        "id": f"exp-{j.pk}",
        "scope": j.scope,
        "format": j.format,
        "status": j.status,
        "rowCount": j.row_count,
        "provenance": j.provenance,
        "createdAt": j.created_at,
        "completedAt": j.completed_at,
    }
