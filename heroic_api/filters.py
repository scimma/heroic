import django_filters
from django import forms
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import D
from datetime import timezone
from dateutil.parser import parse

from heroic_api.models import Telescope, TelescopeStatus, Instrument, InstrumentCapability, TelescopePointing

import math
import logging
logger = logging.getLogger()


EARTH_RADIUS_METERS = 6371008.77141506


class TelescopeFilter(django_filters.FilterSet):
    site = django_filters.CharFilter(field_name='site__id')
    observatory = django_filters.CharFilter(field_name='site__observatory__id')

    class Meta:
        model = Telescope
        exclude = ['telescope_url']


class InstrumentFilter(django_filters.FilterSet):
    site = django_filters.CharFilter(field_name='telescope__site__id')
    observatory = django_filters.CharFilter(field_name='telescope__site__observatory__id')
    telescope = django_filters.CharFilter(field_name='telescope__id')

    class Meta:
        model = Instrument
        exclude = ['instrument_url']


class TelescopeStatusFilter(django_filters.FilterSet):
    site = django_filters.CharFilter(field_name='telescope__site__id')
    observatory = django_filters.CharFilter(field_name='telescope__site__observatory__id')
    telescope = django_filters.CharFilter(field_name='telescope__id')
    status = django_filters.MultipleChoiceFilter(choices=TelescopeStatus.StatusChoices, field_name='status')
    reason = django_filters.CharFilter(field_name='reason', lookup_expr='contains', label='Reason contains')
    start = django_filters.CharFilter(
        method='start_filter',
        label='Date After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    end = django_filters.IsoDateTimeFilter(
        field_name='date',
        lookup_expr='lt',
        label='Date Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )

    def start_filter(self, queryset, name, value):
        ''' This special start filter will also add in the previous state before the start time
            since that state is expected to be valid into the beggining of the start time
        '''
        start_date = parse(value).replace(tzinfo=timezone.utc)
        dates_after = queryset.filter(date__gte=start_date)
        date_before_object = queryset.filter(date__lt=start_date).first()
        if (date_before_object):
            return dates_after | queryset.filter(id=date_before_object.id)
        else:
            return dates_after

    class Meta:
        model = TelescopeStatus
        exclude = ['extra', 'instrument', 'ra', 'dec', 'target', 'date']


class TelescopePointingFilter(django_filters.FilterSet):
    site = django_filters.CharFilter(field_name='telescope__site__id')
    observatory = django_filters.CharFilter(field_name='telescope__site__observatory__id')
    telescope = django_filters.CharFilter(field_name='telescope__id')
    instrument = django_filters.CharFilter(field_name='instrument__id')
    target = django_filters.CharFilter(field_name='target', lookup_expr='icontainer', label='Target name contains')
    target_exact = django_filters.CharFilter(field_name='target', lookup_expr='exact', label='Target name exact')
    cone_search = django_filters.CharFilter(method='filter_cone_search', label='Cone Search',
                                            help_text='RA, Dec, Radius (degrees)')
    polygon_search = django_filters.CharFilter(
        method='filter_polygon_search',
        label='Polygon Search',
        help_text='Comma-separated pairs of space-delimited coordinates (degrees).'
    )
    start = django_filters.CharFilter(
        field_name='date',
        lookup_expr='gte',
        label='Date After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    end = django_filters.IsoDateTimeFilter(
        field_name='date',
        lookup_expr='lt',
        label='Date Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )

    def filter_cone_search(self, queryset, name, value):
        ''' Cone search is expected in the form "ra,dec,radius" all in decimal degress.
        '''
        ra, dec, radius = value.split(',')

        ra = float(ra)
        dec = float(dec)

        radius_meters = 2 * math.pi * EARTH_RADIUS_METERS * float(radius) / 360

        return queryset.filter(coordinate__distance_lte=(Point(ra, dec), D(m=radius_meters)))

    def filter_polygon_search(self, queryset, name, value):
        ''' Polygon search is expected in the form "x1 y1, x2 y2, etc." for however many points the polygon has
            The polygon specified should be a closed shape such that the last coordinate given closed the polygon
            connecting back to the first coordinate.
        '''
        value += ', ' + value.split(', ', 1)[0]
        vertices = tuple((float(v.split(' ')[0]), float(v.split(' ')[1])) for v in value.split(', '))
        polygon = Polygon(vertices, srid=4035)
        return queryset.filter(coordinate__within=polygon)

    class Meta:
        model = TelescopePointing
        exclude = ['extra', 'coordinate', 'date']


class InstrumentCapabilityFilter(django_filters.FilterSet):
    site = django_filters.CharFilter(field_name='instrument__telescope__site__id')
    observatory = django_filters.CharFilter(field_name='instrument__telescope__site__observatory__id')
    telescope = django_filters.CharFilter(field_name='instrument__telescope__id')
    instrument = django_filters.CharFilter(field_name='instrument__id')
    status = django_filters.MultipleChoiceFilter(choices=InstrumentCapability.InstrumentStatus, field_name='status')
    optical_elements_contains = django_filters.CharFilter(method='optical_elements_contains_filter')
    operation_modes_contains = django_filters.CharFilter(method='operation_modes_contains_filter')
    start = django_filters.CharFilter(
        method='start_filter',
        label='Date After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    end = django_filters.IsoDateTimeFilter(
        field_name='date',
        lookup_expr='lt',
        label='Date Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )

    def start_filter(self, queryset, name, value):
        ''' This special start filter will also add in the previous capabilities before the start time
            since those capabilities are expected to be valid into the beggining of the start time
        '''
        start_date = parse(value).replace(tzinfo=timezone.utc)
        dates_after = queryset.filter(date__gte=start_date)
        date_before_object = queryset.filter(date__lt=start_date).first()
        if (date_before_object):
            return dates_after | queryset.filter(id=date_before_object.id)
        else:
            return dates_after

    def optical_elements_contains_filter(self, queryset, name, value):
        return queryset.filter(optical_element_groups__has_key=value)

    def operation_modes_contains_filter(self, queryset, name, value):
        return queryset.filter(operation_modes__has_key=value)

    class Meta:
        model = InstrumentCapability
        exclude = ['operation_modes', 'optical_element_groups', 'date']
