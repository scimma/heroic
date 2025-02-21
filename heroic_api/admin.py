from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
import json

from heroic_api import models


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
            html += f'<a href="{reverse('admin:heroic_api_instrument_change', args=(instrument.id,))}">{instrument.id}</a></p>'
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
            html += f'<a href="{reverse('admin:heroic_api_telescope_change', args=(telescope.id,))}">{telescope.id}</a></p>'
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
            html += f'<a href="{reverse('admin:heroic_api_site_change', args=(site.id,))}">{site.id}</a></p>'
        return mark_safe(html)


class UserProxyAdmin(admin.ModelAdmin):
    search_fields = ('email', 'first_name', 'last_name')


admin.site.register(models.UserProxy, UserProxyAdmin)
admin.site.register(models.InstrumentCapability, InstrumentCapabilityAdmin)
admin.site.register(models.TelescopeStatus, TelescopeStatusAdmin)
admin.site.register(models.Instrument, InstrumentAdmin)
admin.site.register(models.Telescope, TelescopeAdmin)
admin.site.register(models.Site, SiteAdmin)
admin.site.register(models.Observatory, ObservatoryAdmin)
