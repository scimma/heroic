from rest_framework import viewsets
from .models import Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability
from .serializers import (
    ObservatorySerializer, SiteSerializer, TelescopeSerializer,
    InstrumentSerializer, TelescopeStatusSerializer, InstrumentCapabilitySerializer
)


class ObservatoryViewSet(viewsets.ModelViewSet):
    queryset = Observatory.objects.all()
    serializer_class = ObservatorySerializer


class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer


class TelescopeViewSet(viewsets.ModelViewSet):
    queryset = Telescope.objects.all()
    serializer_class = TelescopeSerializer


class InstrumentViewSet(viewsets.ModelViewSet):
    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer


class TelescopeStatusViewSet(viewsets.ModelViewSet):
    queryset = TelescopeStatus.objects.all()
    serializer_class = TelescopeStatusSerializer


class InstrumentCapabilityViewSet(viewsets.ModelViewSet):
    queryset = InstrumentCapability.objects.all()
    serializer_class = InstrumentCapabilitySerializer
