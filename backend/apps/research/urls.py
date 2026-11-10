from django.urls import path

from .views import ExportDownloadView, ExportListCreateView, ResearchLocationsView

urlpatterns = [
    path("research/locations", ResearchLocationsView.as_view(), name="research-locations"),
    path("research/exports", ExportListCreateView.as_view(), name="research-exports"),
    path("research/exports/<int:pk>/download", ExportDownloadView.as_view(), name="research-export-download"),
]
