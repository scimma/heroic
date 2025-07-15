from django.urls import re_path, include
from rest_framework.routers import DefaultRouter
from heroic_api.viewsets import (
    ObservatoryViewSet, SiteViewSet, TelescopeViewSet, TelescopePointingViewSet,
    InstrumentViewSet, TelescopeStatusViewSet, InstrumentCapabilityViewSet
)
from heroic_api.views import (ProfileAPIView, TargetVisibilityAPIView, TargetAirmassAPIView,
                              RevokeApiTokenApiView)


router = DefaultRouter()
router.register(r'observatories', ObservatoryViewSet)
router.register(r'sites', SiteViewSet)
router.register(r'telescopes', TelescopeViewSet)
router.register(r'instruments', InstrumentViewSet)
router.register(r'telescope-statuses', TelescopeStatusViewSet)
router.register(r'telescope-pointings', TelescopePointingViewSet)
router.register(r'instrument-capabilities', InstrumentCapabilityViewSet)

urlpatterns = [
    re_path(r'^', include(router.urls)),
    re_path(r'profile', ProfileAPIView.as_view()),
    re_path(r'revoke_api_token', RevokeApiTokenApiView.as_view(), name='revoke_api_token'),
    re_path(r'visibility/intervals', TargetVisibilityAPIView.as_view(), name='visibility-intervals'),
    re_path(r'visibility/airmass', TargetAirmassAPIView.as_view(), name='visibility-airmass'),
]
