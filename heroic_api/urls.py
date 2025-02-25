from django.urls import re_path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ObservatoryViewSet, SiteViewSet, TelescopeViewSet, ProfileAPIView,
    InstrumentViewSet, TelescopeStatusViewSet, InstrumentCapabilityViewSet
)


router = DefaultRouter()
router.register(r'observatories', ObservatoryViewSet)
router.register(r'sites', SiteViewSet)
router.register(r'telescopes', TelescopeViewSet)
router.register(r'instruments', InstrumentViewSet)
router.register(r'telescope-statuses', TelescopeStatusViewSet)
router.register(r'instrument-capabilities', InstrumentCapabilityViewSet)

urlpatterns = [
    re_path(r'^', include(router.urls)),
    re_path(r'profile', ProfileAPIView.as_view()),
]
