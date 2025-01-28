from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
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

    @action(detail=True, methods=['get', 'post'])
    def status(self, request, pk=None):
        if request.method == 'GET':
            serializer = TelescopeStatusSerializer(self.get_object().statuses.all(), many=True)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
        elif request.method == 'POST':
            data = request.data
            data['telescope'] = pk
            serializer = TelescopeStatusSerializer(data=data, many=isinstance(data, list))
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstrumentViewSet(viewsets.ModelViewSet):
    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer

    @action(detail=True, methods=['get', 'post'])
    def capabilities(self, request, pk=None):
        if request.method == 'GET':
            serializer = InstrumentCapabilitySerializer(self.get_object().capabilities.all(), many=True)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
        elif request.method == 'POST':
            data = request.data
            data['instrument'] = pk
            serializer = InstrumentCapabilitySerializer(data=data, many=isinstance(data, list))
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TelescopeStatusViewSet(viewsets.ModelViewSet):
    queryset = TelescopeStatus.objects.all()
    serializer_class = TelescopeStatusSerializer


class InstrumentCapabilityViewSet(viewsets.ModelViewSet):
    queryset = InstrumentCapability.objects.all()
    serializer_class = InstrumentCapabilitySerializer
