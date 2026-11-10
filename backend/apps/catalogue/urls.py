from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CropViewSet

router = DefaultRouter()
router.register(r"catalogue/crops", CropViewSet, basename="crop")

urlpatterns = router.urls
