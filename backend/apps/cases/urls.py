from django.urls import path

from .views import CaseDetailView, CaseListCreateView, CaseMessageView

urlpatterns = [
    path("cases", CaseListCreateView.as_view(), name="case-list"),
    path("cases/<int:pk>", CaseDetailView.as_view(), name="case-detail"),
    path("cases/<int:pk>/messages", CaseMessageView.as_view(), name="case-message"),
]
