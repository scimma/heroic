from rest_framework import viewsets
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth.models import User

from heroic_api.models import Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability
from heroic_api.serializers import (
    ObservatorySerializer, SiteSerializer, TelescopeSerializer, ProfileSerializer,
    InstrumentSerializer, TelescopeStatusSerializer, InstrumentCapabilitySerializer
)
from heroic_api.permissions import IsObservatoryAdminOrReadOnly, IsAdminOrReadOnly


class ProfileAPIView(RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Once authenticated, retrieve profile data"""
        qs = User.objects.filter(pk=self.request.user.pk).prefetch_related(
            'profile'
        )
        return qs.first().profile


class ObservatoryViewSet(viewsets.ModelViewSet):
    queryset = Observatory.objects.all()
    serializer_class = ObservatorySerializer
    permission_classes = [IsAdminOrReadOnly]


class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]


class TelescopeViewSet(viewsets.ModelViewSet):
    queryset = Telescope.objects.all()
    serializer_class = TelescopeSerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]

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
    permission_classes = [IsObservatoryAdminOrReadOnly]

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


class InstrumentCapabilityViewSet(viewsets.ModelViewSet):
    queryset = InstrumentCapability.objects.all()
    serializer_class = InstrumentCapabilitySerializer
    permission_classes = [IsObservatoryAdminOrReadOnly]
