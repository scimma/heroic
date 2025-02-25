from rest_framework.permissions import BasePermission, SAFE_METHODS
from heroic_api.models import Observatory, Telescope, Instrument


def get_observatory_from_request(request, pk=''):
    """ This attempts to pull out the observatory of a request.
        This applies to all types of HEROIC post requests
    """
    data = request.data
    observatory = None
    try:
        if 'observatory' in data:
            observatory = Observatory.objects.get(id=data['observatory'])
        elif 'site' in data:
            observatory = Observatory.objects.get(sites__id=data['site'])
        elif 'telescope' in data:
            observatory = Telescope.objects.get(id=data['telescope']).observatory
        elif 'instrument' in data:
            observatory = Instrument.objects.get(id=data['instrument']).observatory
        elif 'status' in request.path and pk:
            observatory = Telescope.objects.get(id=pk).observatory
        elif 'capabilities' in request.path and pk:
            observatory = Instrument.objects.get(id=pk).observatory
    except (Observatory.DoesNotExist, Telescope.DoesNotExist, Instrument.DoesNotExist):
        # If these structures are not found, then this request is bound to fail in serialization
        pass
    return observatory


class IsObservatoryAdminOrReadOnly(BasePermission):
    
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS or request.user.is_superuser:
            return True
        else:
            # Check if the request's observatory id matches an observatory for which this user is admin
            observatory = get_observatory_from_request(request, view.kwargs.get('pk'))
            # This looks crazy - allowing permission if we don't find an associated observatory!
            # The reason for this is that this message will be rejected as missing data that can
            # link it back to an observatory by the serializer, so it should be safe...
            if observatory is None or (observatory.admin and observatory.admin == request.user):
                return True
            return False

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or request.user.is_superuser:
            return True
        else:
            # Check if the requests user is the admin of the requests Observatory
            # All models have a property of 'observatory' linking up to its observatory
            if obj.observatory.admin and obj.observatory.admin == request.user:
                return True
            return False


class IsAdminOrReadOnly(BasePermission):
    """The request is either read-only, or the user is a superuser"""
    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS
            or request.user and request.user.is_superuser
        )
