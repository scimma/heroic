from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from django.contrib.auth.models import User
from django.views.generic import RedirectView
from django.conf import settings

from heroic_api.serializers import (ProfileSerializer, TargetVisibilityQuerySerializer,
                                    TargetVisibilityIntervalResponseSerializer,
                                    TargetVisibilityAirmassResponseSerializer,
                                    GWVisibilityQuerySerializer, GWVisibilityResponseSerializer)
from heroic_api.visibility import get_rise_set_intervals_by_telescope_for_target, get_airmass_by_telescope_for_target
from heroic_api.gw_calculations import calculate_gw_visibility_timeline
from heroic_api.models import TelescopeStatus

import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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


class LoginRedirectView(RedirectView):
    pattern_name = 'login-redirect'

    def get(self, request, *args, **kwargs):

        logger.debug(f'LoginRedirectView.get -- request.user: {request.user}')

        login_redirect_url = f'{settings.HEROIC_FRONT_END_BASE_URL}'
        logger.info(f'LoginRedirectView.get -- setting self.url and redirecting to {login_redirect_url}')
        self.url = login_redirect_url

        return super().get(request, *args, **kwargs)


class LogoutRedirectView(RedirectView):
    pattern_name = 'logout-redirect'

    def get(self, request, *args, **kwargs):

        logout_redirect_url = f'{settings.HEROIC_FRONT_END_BASE_URL}'
        logger.info(f'LogoutRedirectView.get setting self.url and redirecting to {logout_redirect_url}')
        self.url = logout_redirect_url

        return super().get(request, *args, **kwargs)


class RevokeApiTokenApiView(APIView):
    """View to revoke an API token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """A simple POST request (empty request body) with user authentication information in the HTTP header will revoke a user's API Token."""
        request.user.auth_token.delete()
        Token.objects.create(user=request.user)
        return Response({'message': 'API token revoked.'}, status=status.HTTP_200_OK)

    def get_endpoint_name(self):
        return 'revokeApiToken'


class GWVisibilityAPIView(APIView):
    """API view to get GW network visibility for a sky position over time"""
    serializer_class = GWVisibilityQuerySerializer
    
    @extend_schema(
        request=GWVisibilityQuerySerializer,
        responses={200: GWVisibilityResponseSerializer},
        description="Calculate GW network detectability for a sky position over time",
        examples=[
            OpenApiExample(
                'GW visibility query',
                summary='Query GW network visibility',
                description='Get horizon distance where network SNR >= 10',
                value={
                    'ra': 180.0,
                    'dec': -30.0,
                    'start': '2025-01-22T00:00:00Z',
                    'end': '2025-01-23T00:00:00Z',
                    'time_resolution_minutes': 15
                }
            )
        ]
    )
    def post(self, request):
        """Calculate GW visibility for POST request"""
        serializer = GWVisibilityQuerySerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                # Get telescope status data for the time range
                telescopes_status = {}
                for telescope in data['telescopes']:
                    # Get all status changes in the time range
                    statuses_in_range = TelescopeStatus.objects.filter(
                        telescope=telescope,
                        date__gte=data['start'],
                        date__lte=data['end']
                        ).order_by('date')
                    status_before = TelescopeStatus.objects.filter(
                        telescope=telescope,
                        date__lt=data['start']
                        ).first()
                    if (status_before):
                        statuses_in_range |= TelescopeStatus.objects.filter(id=status_before.id)

                    # Convert to intervals
                    status_intervals = []
                    for i, status in enumerate(statuses_in_range):
                        interval = {
                            'start': status.date,
                            'status': status.status,
                            'sensitivity': status.extra.get('sensitivity', '0')
                        }
                        # Set end time to next status or query end
                        if i + 1 < len(statuses_in_range):
                            interval['end'] = statuses_in_range[i + 1].date
                        else:
                            interval['end'] = data['end']
                        
                        status_intervals.append(interval)

                    telescopes_status[telescope.id] = status_intervals
                
                # Calculate GW visibility timeline
                timeline = calculate_gw_visibility_timeline(
                    telescopes_status,
                    data['ra'],
                    data['dec'],
                    data['start'],
                    data['end'],
                    data.get('time_resolution_minutes', 15)
                )
                
                response_data = {
                    'query_info': {
                        'ra': data['ra'],
                        'dec': data['dec'],
                        'start': data['start'].isoformat(),
                        'end': data['end'].isoformat(),
                        'telescopes': [t.id for t in data['telescopes']],
                        'time_resolution_minutes': data.get('time_resolution_minutes', 15)
                    },
                    'timeline': timeline
                }
                
                from rest_framework import status as http_status
                return Response(response_data, status=http_status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error in GW visibility calculation: {str(e)}", exc_info=True)
                from rest_framework import status as http_status
                return Response(
                    {'error': f'Internal server error: {str(e)}'}, 
                    status=http_status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            from rest_framework import status as http_status
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        """Handle GET requests by converting to POST data"""
        return self.post(request)
    
    def get_endpoint_name(self):
        return 'gwVisibility'
