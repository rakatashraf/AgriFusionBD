from django.urls import path

from .views import AssetsView, IndicatorsView

urlpatterns = [
    path("fields/<slug:field_slug>/indicators", IndicatorsView.as_view(), name="field-indicators"),
    path("environmental/assets", AssetsView.as_view(), name="assets"),
]
