from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth.models import User

from heroic_api.serializers import ProfileSerializer, TargetVisibilityQuerySerializer
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
    def get(self, request):
        serializer = TargetVisibilityQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            data = serializer.validated_data
            visibility_intervals = get_rise_set_intervals_by_telescope_for_target(data)
            return Response(visibility_intervals, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TargetAirmassAPIView(APIView):
    def get(self, request):
        serializer = TargetVisibilityQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            data = serializer.validated_data
            airmass_data = get_airmass_by_telescope_for_target(data)
            return Response(airmass_data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
