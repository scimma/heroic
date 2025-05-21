import django_filters
from django import forms
from datetime import timezone
from dateutil.parser import parse

from heroic_api.models import Telescope, TelescopeStatus, Instrument, InstrumentCapability

import logging
logger = logging.getLogger()


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
