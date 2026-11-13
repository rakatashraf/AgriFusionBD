from django.urls import path

from . import rover_api
from .views import (
    DeviceListView,
    ObservationListView,
    ObservationUploadView,
    SurveyRunListView,
    SurveyRunSamplesView,
)

urlpatterns = [
    # Existing (session-authenticated) endpoints
    path("devices", DeviceListView.as_view(), name="device-list"),
    path("observations", ObservationListView.as_view(), name="observation-list"),
    path("devices/<int:pk>/observations", ObservationUploadView.as_view(), name="observation-upload"),
    path("runs", SurveyRunListView.as_view(), name="survey-run-list"),
    path("runs/<str:run_id>/samples", SurveyRunSamplesView.as_view(), name="survey-run-samples"),

    # AgriRover-Q adapter (X-API-Key auth) — plan §5.3
    path("rover/samples", rover_api.rover_samples, name="rover-samples"),
    path("rover/status", rover_api.rover_status, name="rover-status"),
    path("rover/images", rover_api.rover_images, name="rover-images"),
    path("rover/runs", rover_api.rover_runs, name="rover-runs"),
    path("rover/runs/<str:run_id>/samples", rover_api.rover_run_samples, name="rover-run-samples"),
    path("rover/runs/<str:run_id>/status", rover_api.rover_run_status, name="rover-run-status"),
    path("rover/runs/<str:run_id>/geojson", rover_api.rover_run_geojson, name="rover-run-geojson"),
    path("rover/fields/<str:field_id>/contains", rover_api.rover_field_contains, name="rover-field-contains"),
    path("rover/health", rover_api.rover_health, name="rover-health"),
]
