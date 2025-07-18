from django import forms
from django.contrib import admin
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import PointField
from django.contrib.gis import forms as gis_forms
from django.urls import reverse
from django.utils.safestring import mark_safe
import json

from heroic_api import models


class RaDecWidget(forms.MultiWidget):
    def __init__(self, attrs=None, date_format=None, time_format=None):
        widgets = (forms.TextInput(attrs={'placeholder': 'RA (degrees)'}),
                   forms.TextInput(attrs={'placeholder': 'Dec (degrees)'}))
        super(RaDecWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return tuple(value.coords)
        return (None, None)

    def value_from_datadict(self, data, files, name):
        ra = data[name + '_0']
        dec = data[name + '_1']

        try:
            return Point(float(ra), float(dec), srid=4326)
        except ValueError:
            return None


class RaDecFormField(gis_forms.PointField):
    widget = RaDecWidget

    def to_python(self, value):
        if isinstance(value, str):
            try:
                ra, dec = map(float, value.split(','))
                return Point(ra, dec, srid=4326)
            except (ValueError, TypeError):
                return None
        return super().to_python(value)


class PrettyJSONEncoder(json.JSONEncoder):
    """ To pretty print the json sections in the admin interface forms """
    def __init__(self, *args, indent, sort_keys, **kwargs):
        super().__init__(*args, indent=2, sort_keys=True, **kwargs)


class InstrumentCapabilityAdmin(admin.ModelAdmin):
    optical_element_groups = forms.JSONField(encoder=PrettyJSONEncoder)
    operation_modes = forms.JSONField(encoder=PrettyJSONEncoder)
    list_display = ('date', 'instrument', 'status')
    list_filter = ('status', 'instrument__name', 'instrument__telescope__name')
    search_fields = ('instrument__name', 'instrument__id')


class LatestFormset(forms.BaseInlineFormSet):
    def get_queryset(self):
        return super().get_queryset().order_by('-date')[:1]


class LatestInline(admin.TabularInline):
    can_delete = False
    formset = LatestFormset
    extra = 0
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LatestInstrumentCapabilityInline(LatestInline):
    model = models.InstrumentCapability
    verbose_name = 'Current Instrument Capability'


class TelescopeStatusAdmin(admin.ModelAdmin):
    extra = forms.JSONField(encoder=PrettyJSONEncoder)
    list_display = ('date', 'telescope', 'status', 'reason')
    list_filter = ('status', 'telescope__name', 'telescope__site__name', 'telescope__site__observatory__name')
    search_fields = ('telescope__name', 'telescope__id', 'target')


class LatestTelescopeStatusInline(LatestInline):
    model = models.TelescopeStatus
    verbose_name = 'Current Telescope Status'


class TelescopePointingAdmin(admin.ModelAdmin):
    extra = forms.JSONField(encoder=PrettyJSONEncoder)
    list_display = ('date', 'telescope', 'instrument', 'target')
    list_filter = ('telescope__name', 'telescope__site__name', 'telescope__site__observatory__name', 'instrument__name')
    search_fields = ('telescope__name', 'telescope__id', 'target', 'instrument__name')
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, PointField):
            return RaDecFormField(**kwargs)
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class InstrumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'available', 'telescope')
    list_filter = ('available', 'telescope__name', 'telescope__site__name', 'telescope__site__observatory__name')
    search_fields = ('id', 'name', 'telescope__name', 'telescope__site__name', 'telescope__site__observatory__name')
    inlines = (LatestInstrumentCapabilityInline,)

class TelescopeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'aperture', 'site', 'instruments_count')
    list_filter = ('aperture', 'site__name', 'site__observatory__name')
    search_fields = ('id', 'name', 'site__observatory__name', 'site__name')
    readonly_fields = ('instruments',)
    inlines = (LatestTelescopeStatusInline,)

    def instruments_count(self, obj):
        return obj.instruments.count()

    def instruments(self, obj):
        html = ''
        for instrument in obj.instruments.all():
            html += '<a href="{0}">{1}</a></p>'.format(
                reverse('admin:heroic_api_instrument_change', args=(instrument.id,)),
                instrument.id
            )
        return mark_safe(html)


class SiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'observatory', 'telescopes_count')
    list_filter = ('observatory__name',)
    search_fields = ('id', 'name', 'observatory__name', 'observatory__id')
    readonly_fields = ('telescopes',)

    def telescopes_count(self, obj):
        return obj.telescopes.count()

    def telescopes(self, obj):
        html = ''
        for telescope in obj.telescopes.all():
            html += '<a href="{0}">{1}</a></p>'.format(
                reverse('admin:heroic_api_telescope_change', args=(telescope.id,)),
                telescope.id
            )
        return mark_safe(html)


class ObservatoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'admin', 'sites_count')
    search_fields = ('id', 'name')
    readonly_fields = ('sites',)
    autocomplete_fields = ('admin',)

    def sites_count(self, obj):
        return obj.sites.count()

    def sites(self, obj):
        html = ''
        for site in obj.sites.all():
            html += '<a href="{0}">{1}</a></p>'.format(
                reverse('admin:heroic_api_site_change', args=(site.id,)),
                site.id
            )
        return mark_safe(html)


class UserProxyAdmin(admin.ModelAdmin):
    search_fields = ('email', 'first_name', 'last_name')


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'credential_name')
    search_fields = ('user', 'credential_name')


admin.site.register(models.UserProxy, UserProxyAdmin)
admin.site.register(models.Profile, ProfileAdmin)
admin.site.register(models.InstrumentCapability, InstrumentCapabilityAdmin)
admin.site.register(models.TelescopeStatus, TelescopeStatusAdmin)
admin.site.register(models.TelescopePointing, TelescopePointingAdmin)
admin.site.register(models.Instrument, InstrumentAdmin)
admin.site.register(models.Telescope, TelescopeAdmin)
admin.site.register(models.Site, SiteAdmin)
admin.site.register(models.Observatory, ObservatoryAdmin)
