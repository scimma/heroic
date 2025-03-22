from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from django.contrib.auth.models import User

from heroic_api.serializers import (ProfileSerializer, TargetVisibilityQuerySerializer,
                                    TargetVisibilityIntervalResponseSerializer,
                                    TargetVisibilityAirmassResponseSerializer)
from heroic_api.visibility import get_rise_set_intervals_by_telescope_for_target, get_airmass_by_telescope_for_target


class ProfileAPIView(RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Once authenticated, retrieve profile data"""
        qs = User.objects.filter(pk=self.request.user.pk).prefetch_related(
            'profile'
        )
        return qs.first().profile




class TargetVisibilityAPIView(APIView):
    """ A API view to get visiblity intervals for targets on telescopes
        Supports being called through POST with a data dict or GET with query params
    """
    serializer_class = TargetVisibilityQuerySerializer
    example_response = {
        'telescope_id': [['2025-03-01T16:15:00Z', '2025-03-01T19:00:37.291560Z'], ['2025-03-01T16:15:00Z', '2025-03-01T19:00:37.291560Z']],
        'telescope2_id': [['2025-03-01T16:15:00Z', '2025-03-01T19:00:37.291560Z']]
    }

    def get_visibility(self, data):
        serializer = TargetVisibilityQuerySerializer(data=data)
        if serializer.is_valid():
            data = serializer.validated_data
            visibility_intervals = get_rise_set_intervals_by_telescope_for_target(data)
            return Response(visibility_intervals, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id='query visibility intervals',
        parameters=[TargetVisibilityQuerySerializer],
        responses={
            200: OpenApiResponse(
                response=TargetVisibilityIntervalResponseSerializer,
                examples=[OpenApiExample(name='Success',
                    value=example_response
                )]
           )
        }
    )
    def get(self, request):
        return self.get_visibility(request.query_params)

    @extend_schema(
        operation_id='query visibility intervals (post)',
        responses={
            200: OpenApiResponse(
                response=TargetVisibilityIntervalResponseSerializer,
                examples=[OpenApiExample(name='Success',
                    value=example_response
                )]
           )
        })
    def post(self, request):
        return self.get_visibility(request.data)


class TargetAirmassAPIView(APIView):
    """ A API view to get airmasses for targets on telescopes at times
        Supports being called through POST with a data dict or GET with query params
    """
    serializer_class = TargetVisibilityQuerySerializer
    example_response = {
        'telescope_id': {'times': ['2025-03-01T16:15:00Z', '2025-03-01T16:25:00.00Z', '2025-03-01T16:35:00.00Z'],
                         'airmasses': [1.2342, 1.34543, 1.4564]
                        },
        'telescope2_id': {'times': ['2025-03-01T16:15:00Z', '2025-03-01T16:25:00.00Z', '2025-03-01T16:35:00.00Z'],
                         'airmasses': [1.2342, 1.34543, 1.4564]
                        },
        }

    def get_airmass(self, data):
        serializer = TargetVisibilityQuerySerializer(data=data)
        if serializer.is_valid():
            data = serializer.validated_data
            airmass_data = get_airmass_by_telescope_for_target(data)
            return Response(airmass_data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id='query airmass values',
        parameters=[TargetVisibilityQuerySerializer],
        responses={
            200: OpenApiResponse(
                response=TargetVisibilityAirmassResponseSerializer,
                examples=[OpenApiExample(name='Success',
                    value=example_response
                )]
           )
        }
    )
    def get(self, request):
        return self.get_airmass(request.query_params)

    @extend_schema(
        operation_id='query airmass values (post)',
        responses={
            200: OpenApiResponse(
                response=TargetVisibilityAirmassResponseSerializer,
                examples=[OpenApiExample(name='Success',
                    value=example_response
                )]
           )
        }
    )
    def post(self, request):
        return self.get_airmass(request.data)
