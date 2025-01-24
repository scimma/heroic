from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ObservatoryViewSet, SiteViewSet, TelescopeViewSet,
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
    path('api/', include(router.urls)),
]
