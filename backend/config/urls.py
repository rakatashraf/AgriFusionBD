"""FieldShift root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# OpenAPI + docs (plan §2: /api/schema/ and /api/docs/).
api_schema = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.farms.urls")),
    path("api/v1/", include("apps.catalogue.urls")),
    path("api/v1/", include("apps.environment.urls")),
    path("api/v1/", include("apps.analyses.urls")),
    path("api/v1/", include("apps.cases.urls")),
    path("api/v1/", include("apps.rovers.urls")),
    path("api/v1/", include("apps.research.urls")),
    path("api/", include(api_schema)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
