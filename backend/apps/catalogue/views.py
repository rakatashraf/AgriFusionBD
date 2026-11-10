from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import Crop
from .serializers import CropSerializer


class CropViewSet(ReadOnlyModelViewSet):
    """GET /catalogue/crops (plan §2)."""

    queryset = Crop.objects.all()
    serializer_class = CropSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
