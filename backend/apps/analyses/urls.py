from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AnalysisViewSet, SubmitAnalysisView

router = DefaultRouter()
router.register(r"analyses", AnalysisViewSet, basename="analysis")

urlpatterns = router.urls + [
    path("fields/<slug:field_slug>/analyses", SubmitAnalysisView.as_view(), name="submit-analysis"),
]
