from django.urls import path

from .views import DeviceListView, ObservationListView, ObservationUploadView

urlpatterns = [
    path("devices", DeviceListView.as_view(), name="device-list"),
    path("observations", ObservationListView.as_view(), name="observation-list"),
    path("devices/<int:pk>/observations", ObservationUploadView.as_view(), name="observation-upload"),
]
