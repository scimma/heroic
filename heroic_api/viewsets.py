from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend

from heroic_api.visibility import telescope_dark_intervals
from heroic_api.filters import (TelescopeFilter, InstrumentFilter, TelescopeStatusFilter, InstrumentCapabilityFilter,
                                TelescopePointingFilter)
from heroic_api.models import (Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability,
                               TelescopePointing)
from heroic_api.serializers import (
    ObservatorySerializer, SiteSerializer, TelescopeSerializer, TelescopeDarkIntervalsSerializer,
    InstrumentSerializer, TelescopeStatusSerializer, InstrumentCapabilitySerializer, TelescopePointingSerializer,
    TelescopeDarkIntervalResponseSerializer
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
    dark_interval_response_example = {
        'telescope_id_1': [
            ['2019-08-24T14:15:22Z', '2019-08-24T16:15:22Z'],
            ['2019-08-25T14:15:22Z', '2019-08-25T16:15:22Z']
        ],
        'telescope_id_2': [
            ['2019-08-24T14:15:22Z', '2019-08-24T16:15:22Z'],
            ['2019-08-25T14:15:22Z', '2019-08-25T16:15:22Z']
        ],
    }
    
    def get_serializer_class(self):
        if 'dark_intervals' in self.action:
            return TelescopeDarkIntervalsSerializer
        elif self.action == 'status':
            return TelescopeStatusSerializer
        return super().get_serializer_class()

    @extend_schema(
        parameters=[TelescopeDarkIntervalsSerializer],
        responses={
            200: OpenApiResponse(
                response=TelescopeDarkIntervalResponseSerializer,
                examples=[OpenApiExample(name='Success',
                    value=dark_interval_response_example
                )]
           )
        },
        examples = [
            OpenApiExample(
                'Example Dark Intervals Request',
                value={
                    'id': 1,
                    'start': '2019-08-24T14:15:22Z',
                    'end': '2019-08-25T14:15:22Z',
                    'telescopes': ['telescope_id_1', 'telescope_id_2']
                },
                request_only=True
            ),
            OpenApiExample(
                'Example Dark Intervals Response',
                value=dark_interval_response_example,
                response_only=True
            ) 
        ]
    )
    @action(detail=False, methods=['get'], url_path='dark_intervals')
    def dark_intervals_list(self, request):
        
        params = request.query_params.dict()
        # Needed to correctly pass list params
        params['telescopes'] = request.query_params.getlist('telescopes')
        serializer = TelescopeDarkIntervalsSerializer(data=params)
        if serializer.is_valid():
            data = serializer.validated_data
            dark_intervals_by_telescope = {}
            for telescope in data['telescopes']:
                dark_intervals_by_telescope[telescope.id] = telescope_dark_intervals(
                    telescope, start=data['start'], end=data['end'])
            return Response(dark_intervals_by_telescope, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        parameters=[TelescopeDarkIntervalsSerializer],
        responses={
            200: OpenApiResponse(
                response=TelescopeDarkIntervalResponseSerializer,
                examples=[OpenApiExample(name='Success',
                    value=dark_interval_response_example
                )]
           )
        },
        examples = [
            OpenApiExample(
                'Example Dark Intervals Request',
                value={
                    'id': 1,
                    'start': '2019-08-24T14:15:22Z',
                    'end': '2019-08-25T14:15:22Z',
                    'telescopes': ['telescope_id_1', 'telescope_id_2']
                },
                request_only=True
            ),
            OpenApiExample(
                'Example Dark Intervals Response',
                value=dark_interval_response_example,
                response_only=True
            ) 
        ]
    )
    @action(detail=True, methods=['get'], url_path='dark_intervals')
    def dark_intervals(self, request, pk=None):
        params = request.query_params.dict()
        # Needed to correctly pass list params
        params['telescopes'] = request.query_params.getlist('telescopes', [pk])
        serializer = TelescopeDarkIntervalsSerializer(data=params)
        if serializer.is_valid():
            data = serializer.validated_data
            dark_intervals_by_telescope = {}
            for telescope in data['telescopes']:
                dark_intervals_by_telescope[telescope.id] = telescope_dark_intervals(
                    telescope, start=data['start'], end=data['end'])
            return Response(dark_intervals_by_telescope, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=TelescopeStatusSerializer(many=True)
           )
        },
    )
    @action(detail=True, methods=['get', 'post'], pagination_class=None)
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

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=InstrumentCapabilitySerializer(many=True)
           )
        },
    )
    @action(detail=True, methods=['get', 'post'], pagination_class=None)
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


class TelescopePointingViewSet(viewsets.ModelViewSet):
    queryset = TelescopePointing.objects.all()
    serializer_class = TelescopePointingSerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]
    filterset_class = TelescopePointingFilter
    filter_backends = (DjangoFilterBackend,)


class InstrumentCapabilityViewSet(viewsets.ModelViewSet):
    queryset = InstrumentCapability.objects.all()
    serializer_class = InstrumentCapabilitySerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]
    filterset_class = InstrumentCapabilityFilter
    filter_backends = (DjangoFilterBackend,)
