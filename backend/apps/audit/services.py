"""Tiny helper to record an audit event from any code path."""

from .models import AuditEvent


def record(action: str, actor=None, *, target_type: str = "", target_id: str = "",
           detail: dict | None = None, ip: str | None = None) -> AuditEvent:
    return AuditEvent.objects.create(
        action=action,
        actor=actor,
        target_type=target_type,
        target_id=str(target_id or ""),
        detail=detail or {},
        ip=ip,
    )
