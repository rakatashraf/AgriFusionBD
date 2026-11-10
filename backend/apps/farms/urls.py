from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import FieldViewSet

router = DefaultRouter()
router.register(r"fields", FieldViewSet, basename="field")

urlpatterns = router.urls
