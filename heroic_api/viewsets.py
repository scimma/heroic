from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend

from heroic_api.visibility import telescope_dark_intervals
from heroic_api.filters import TelescopeFilter, InstrumentFilter, TelescopeStatusFilter, InstrumentCapabilityFilter
from heroic_api.models import Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability
from heroic_api.serializers import (
    ObservatorySerializer, SiteSerializer, TelescopeSerializer, TargetDarkIntervalsSerializer,
    InstrumentSerializer, TelescopeStatusSerializer, InstrumentCapabilitySerializer
)
from heroic_api.permissions import IsObservatoryAdminOrReadOnly, IsAdminOrReadOnly


class ObservatoryViewSet(viewsets.ModelViewSet):
    queryset = Observatory.objects.all()
    serializer_class = ObservatorySerializer
    permission_classes = [IsAdminOrReadOnly]


class SiteViewSet(viewsets.ModelViewSet):
    lookup_value_regex = '[^/]+'
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]


class TelescopeViewSet(viewsets.ModelViewSet):
    lookup_value_regex = '[^/]+'
    queryset = Telescope.objects.all()
    serializer_class = TelescopeSerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]
    filterset_class = TelescopeFilter
    filter_backends = (DjangoFilterBackend,)

    @action(detail=False, methods=['get'], url_path='dark_intervals')
    def dark_intervals_list(self, request):
        params = request.query_params.dict()
        # Needed to correctly pass list params
        params['telescopes'] = request.query_params.getlist('telescopes')
        serializer = TargetDarkIntervalsSerializer(data=params)
        if serializer.is_valid():
            data = serializer.validated_data
            dark_intervals_by_telescope = {}
            for telescope in data['telescopes']:
                dark_intervals_by_telescope[telescope.id] = telescope_dark_intervals(
                    telescope, start=data['start'], end=data['end'])
            return Response(dark_intervals_by_telescope, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='dark_intervals')
    def dark_intervals(self, request, pk=None):
        params = request.query_params.dict()
        # Needed to correctly pass list params
        params['telescopes'] = request.query_params.getlist('telescopes', [pk])
        serializer = TargetDarkIntervalsSerializer(data=params)
        if serializer.is_valid():
            data = serializer.validated_data
            dark_intervals_by_telescope = {}
            for telescope in data['telescopes']:
                dark_intervals_by_telescope[telescope.id] = telescope_dark_intervals(
                    telescope, start=data['start'], end=data['end'])
            return Response(dark_intervals_by_telescope, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
    lookup_value_regex = '[^/]+'
    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]
    filterset_class = InstrumentFilter
    filter_backends = (DjangoFilterBackend,)

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
    permission_classes = [IsObservatoryAdminOrReadOnly]
    filterset_class = TelescopeStatusFilter
    filter_backends = (DjangoFilterBackend,)


class InstrumentCapabilityViewSet(viewsets.ModelViewSet):
    queryset = InstrumentCapability.objects.all()
    serializer_class = InstrumentCapabilitySerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]
    filterset_class = InstrumentCapabilityFilter
    filter_backends = (DjangoFilterBackend,)
