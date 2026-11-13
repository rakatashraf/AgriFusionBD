"""
Cases: farmer→officer assistance cases with a message thread and a review
decision (accept / question / reject) — the "Open officer case" flow (plan §2).
"""

from django.conf import settings
from django.db import models


class AssistanceCase(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_review", "In review"),
        ("accepted", "Accepted"),
        ("questioned", "Questioned"),
        ("rejected", "Rejected"),
        ("closed", "Closed"),
    ]

    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="cases")
    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cases_opened")
    officer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="cases_assigned")
    subject = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="open")
    decision = models.CharField(max_length=16, blank=True)  # accept | question | reject
    decision_note = models.TextField(blank=True)
    linked_analysis = models.ForeignKey("analyses.AnalysisRun", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["farmer", "status"], name="case_farmer_status_idx"),
                   models.Index(fields=["officer", "status"], name="case_officer_status_idx")]

    def __str__(self):
        return f"Case {self.pk} · {self.subject}"


class CaseMessage(models.Model):
    case = models.ForeignKey(AssistanceCase, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="case_messages")
    author_role = models.CharField(max_length=16, default="farmer")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class CaseReview(models.Model):
    """The officer's decision record (accept / question / reject + note)."""

    case = models.ForeignKey(AssistanceCase, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="case_reviews")
    decision = models.CharField(max_length=16)  # accept | question | reject
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
