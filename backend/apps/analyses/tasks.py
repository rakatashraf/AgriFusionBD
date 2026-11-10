"""
Analysis run task — Celery-wired, eager by default (plan §3).

The run is idempotent by design: the engine is a pure function over a frozen
input snapshot, so replaying the same inputs yields an identical output.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("fieldshift.analyses")


@shared_task(bind=True, max_retries=1)
def execute_analysis_run(self, run_id: int) -> None:
    """
    Build the frozen input snapshot, run the engine, and persist the result +
    snapshot in ONE transaction (plan §1, Phase 1: run + outbox in one txn).
    """
    from . import engine_inputs
    from .engine.runner import EngineInput, run
    from .models import AnalysisRun, InputSnapshot

    try:
        run_obj = AnalysisRun.objects.select_related("field", "submitted_by").get(pk=run_id)
    except AnalysisRun.DoesNotExist:
        logger.warning("AnalysisRun %s not found for task", run_id)
        return

    run_obj.status = "running"
    run_obj.started_at = timezone.now()
    run_obj.progress_pct = 10
    run_obj.save(update_fields=["status", "started_at", "progress_pct"])

    # Build the frozen input snapshot (POWER + HLS + soil + catalogue + rules).
    snap = engine_inputs.build_input_snapshot(run_obj)
    run_obj.progress_pct = 55
    run_obj.save(update_fields=["progress_pct"])

    inp: EngineInput = snap.engine_input
    result = run(inp)
    run_obj.progress_pct = 90
    run_obj.save(update_fields=["progress_pct"])

    # Persist run + snapshot atomically.
    with transaction.atomic():
        run_obj.status = result["status"]
        run_obj.progress_pct = 100
        run_obj.completed_at = timezone.now()
        run_obj.plans = result["plans"]
        run_obj.warnings = result["warnings"]
        run_obj.evidence = result["evidence"]
        run_obj.rule_version = result["rule_version"]
        run_obj.save()

        existing = InputSnapshot.objects.filter(run=run_obj).first()
        if existing is None:
            existing = InputSnapshot(run=run_obj)
        existing.power_asset_id = snap.power_asset_id
        existing.power_content_hash = snap.power_content_hash
        existing.hls_asset_id = snap.hls_asset_id
        existing.hls_content_hash = snap.hls_content_hash
        existing.catalogue_version = inp.catalogue_version
        existing.rule_version = inp.rule_version
        existing.soil_test_id = inp.soil_test_id
        existing.save()

    logger.info("AnalysisRun %s → %s (%d plans)", run_obj.pk, result["status"], len(result["plans"]))
