import django_filters
from django import forms
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from datetime import timezone
from dateutil.parser import parse
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import F
from django.contrib.gis.db.models.functions import Translate
from django.db.models import FloatField, ExpressionWrapper, Func

from heroic_api.models import (Telescope, TelescopeStatus, Instrument, InstrumentCapability, TelescopePointing,
                               PlannedTelescopeStatus, PlannedInstrumentCapability, Site, Observatory)

import math
import logging
logger = logging.getLogger()


EARTH_RADIUS_METERS = 6371008.77141506


class TelescopeFilter(django_filters.FilterSet):
    site = django_filters.ModelMultipleChoiceFilter(queryset=Site.objects.all(), field_name='site__id', to_field_name='id')
    observatory = django_filters.ModelMultipleChoiceFilter(queryset=Observatory.objects.all(), field_name='site__observatory__id', to_field_name='id')

    class Meta:
        model = Telescope
        exclude = ['telescope_url']


class InstrumentFilter(django_filters.FilterSet):
    site = django_filters.ModelMultipleChoiceFilter(queryset=Site.objects.all(), field_name='telescope__site__id', to_field_name='id')
    observatory = django_filters.ModelMultipleChoiceFilter(queryset=Observatory.objects.all(), field_name='telescope__site__observatory__id', to_field_name='id')
    telescope = django_filters.ModelMultipleChoiceFilter(queryset=Telescope.objects.all(), field_name='telescope__id', to_field_name='id')

    class Meta:
        model = Instrument
        exclude = ['instrument_url', 'footprint']


class BaseTelescopeStatusFilter(django_filters.FilterSet):
    site = django_filters.ModelMultipleChoiceFilter(queryset=Site.objects.all(), field_name='telescope__site__id', to_field_name='id')
    observatory = django_filters.ModelMultipleChoiceFilter(queryset=Observatory.objects.all(), field_name='telescope__site__observatory__id', to_field_name='id')
    telescope = django_filters.ModelMultipleChoiceFilter(queryset=Telescope.objects.all(), field_name='telescope__id', to_field_name='id')
    status = django_filters.MultipleChoiceFilter(choices=TelescopeStatus.StatusChoices, field_name='status')
    reason = django_filters.CharFilter(field_name='reason', lookup_expr='contains', label='Reason contains')
    created_after = django_filters.IsoDateTimeFilter(
        field_name='created',
        lookup_expr='gte',
        label='Created After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name='created',
        lookup_expr='lt',
        label='Created Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    class Meta:
        model = TelescopeStatus
        exclude = ['extra', 'date', 'created']



class TelescopeStatusFilter(BaseTelescopeStatusFilter):
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


class PlannedTelescopeStatusFilter(BaseTelescopeStatusFilter):
    start_after = django_filters.IsoDateTimeFilter(
        field_name='start',
        lookup_expr='gte',
        label='Start After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    start_before = django_filters.IsoDateTimeFilter(
        field_name='start',
        lookup_expr='lt',
        label='Start Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    end_after = django_filters.IsoDateTimeFilter(
        field_name='end',
        lookup_expr='gte',
        label='End After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    end_before = django_filters.IsoDateTimeFilter(
        field_name='end',
        lookup_expr='lt',
        label='End Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    modified_after = django_filters.IsoDateTimeFilter(
        field_name='modified',
        lookup_expr='gte',
        label='Modified After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    class Meta:
        model = PlannedTelescopeStatus
        exclude = ['extra', 'start', 'end', 'created', 'modified']


class TelescopePointingFilter(django_filters.FilterSet):
    site = django_filters.ModelMultipleChoiceFilter(queryset=Site.objects.all(), field_name='telescope__site__id', to_field_name='id')
    observatory = django_filters.ModelMultipleChoiceFilter(queryset=Observatory.objects.all(), field_name='telescope__site__observatory__id', to_field_name='id')
    telescope = django_filters.ModelMultipleChoiceFilter(queryset=Telescope.objects.all(), field_name='telescope__id', to_field_name='id')
    instrument = django_filters.ModelMultipleChoiceFilter(queryset=Instrument.objects.all(), field_name='instrument__id', to_field_name='id')
    planned = django_filters.BooleanFilter(field_name='planned')
    target = django_filters.CharFilter(field_name='target', lookup_expr='icontainer', label='Target name contains')
    target_exact = django_filters.CharFilter(field_name='target', lookup_expr='exact', label='Target name exact')
    cone_search = django_filters.CharFilter(method='filter_cone_search', label='Cone Search',
                                            help_text='RA, Dec (degrees)')
    fov_search = django_filters.CharFilter(method='filter_fov_search', label='FOV Search',
                                            help_text='Comma delimited coordinates: "RA,Dec"')
    field_search = django_filters.CharFilter(
        method='filter_field_search',
        label='Field Search',
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
    ordering = django_filters.OrderingFilter(
        fields=(
            ('date', 'date'),
            ('telescope', 'telescope'),
            ('instrument', 'instrument')
        )
    )

    def filter_cone_search(self, queryset, name, value):
        ''' Cone search is expected in the form "ra,dec,radius" all in decimal degress.
        '''
        ra, dec, radius = value.split(',')

        ra = float(ra)
        dec = float(dec)

        radius_meters = 2 * math.pi * EARTH_RADIUS_METERS * float(radius) / 360
        

        return queryset.filter(coordinate__distance_lte=(Point(ra, dec), D(m=radius_meters)))

    def filter_fov_search(self, queryset, name, value):
        ''' The FOV search takes in a coordinate of the form "RA,Dec" and returns a set of pointings where it is within the
            instruments FOV. This uses the instruments 'footprint' + pointings 'coordinate' to do the lookup
        '''
        ra, dec = value.split(',')
        ra = float(ra)
        dec = float(dec)
        polygon_queryset = queryset.alias(
            x=ExpressionWrapper(Func('coordinate', function='ST_X'), output_field=FloatField()),
            y=ExpressionWrapper(Func('coordinate', function='ST_Y'), output_field=FloatField()),
        ).alias(
            fov=Translate('instrument__footprint', F('x'), F('y'))
        ).filter(fov__contains=Point(ra, dec))
        return polygon_queryset
    
    def filter_field_search(self, queryset, name, value):
        ''' The FOV search takes in a coordinate of the form "RA,Dec" and returns a set of pointings where it is within the
            instruments FOV. This uses the internal 'field' to do the lookup efficiently
        '''
        ra, dec = value.split(',')
        ra = float(ra)
        dec = float(dec)
        field_queryset = queryset.filter(field__contains=Point(ra, dec, srid=4326))
        
        return field_queryset

    class Meta:
        model = TelescopePointing
        exclude = ['extra', 'coordinate', 'date', 'field']


class BaseInstrumentCapabilityFilter(django_filters.FilterSet):
    site = django_filters.ModelMultipleChoiceFilter(queryset=Site.objects.all(), field_name='instrument__telescope__site__id', to_field_name='id')
    observatory = django_filters.ModelMultipleChoiceFilter(queryset=Observatory.objects.all(), field_name='instrument__telescope__site__observatory__id', to_field_name='id')
    telescope = django_filters.ModelMultipleChoiceFilter(queryset=Telescope.objects.all(), field_name='instrument__telescope__id', to_field_name='id')
    instrument = django_filters.ModelMultipleChoiceFilter(queryset=Instrument.objects.all(), field_name='instrument__id', to_field_name='id')
    status = django_filters.MultipleChoiceFilter(choices=InstrumentCapability.InstrumentStatus, field_name='status')
    optical_elements_contains = django_filters.CharFilter(method='optical_elements_contains_filter')
    operation_modes_contains = django_filters.CharFilter(method='operation_modes_contains_filter')

    def optical_elements_contains_filter(self, queryset, name, value):
        return queryset.filter(optical_element_groups__has_key=value)

    def operation_modes_contains_filter(self, queryset, name, value):
        return queryset.filter(operation_modes__has_key=value)

    class Meta:
        model = InstrumentCapability
        exclude = ['operation_modes', 'optical_element_groups', 'date', 'created']


class InstrumentCapabilityFilter(BaseInstrumentCapabilityFilter):
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


class PlannedInstrumentCapabilityFilter(BaseInstrumentCapabilityFilter):
    start_after = django_filters.IsoDateTimeFilter(
        field_name='start',
        lookup_expr='gte',
        label='Start After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    start_before = django_filters.IsoDateTimeFilter(
        field_name='start',
        lookup_expr='lt',
        label='Start Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    end_after = django_filters.IsoDateTimeFilter(
        field_name='end',
        lookup_expr='gte',
        label='End After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    end_before = django_filters.IsoDateTimeFilter(
        field_name='end',
        lookup_expr='lt',
        label='End Before',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    modified_after = django_filters.IsoDateTimeFilter(
        field_name='modified',
        lookup_expr='gte',
        label='Modified After (Inclusive)',
        widget=forms.TextInput(attrs={'class': 'input', 'type': 'date'})
    )
    class Meta:
        model = PlannedInstrumentCapability
        exclude = ['operation_modes', 'optical_element_groups', 'start', 'end', 'created', 'modified']
