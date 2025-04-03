from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User, AbstractUser
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import AbstractUser


class UserProxy(User):
    # This proxy model exists so the admin interface choices for setting "admin" on the Observatory use email
    # This is because the username is auto generated and makes no sense.
    class Meta:
        proxy = True

    def __str__(self):
        return f'{self.email} - {super().__str__()}'


class Profile(models.Model):
    # This model will store user settings
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    credential_name = models.CharField(max_length=256, blank=True, default='', help_text='Scimma Auth User Scram Credential name')
    credential_password = models.CharField(max_length=256, blank=True, default='', help_text='Scimma Auth User Scram Credential password')

    @property
    def api_token(self):
        return Token.objects.get_or_create(user=self.user)[0]


class Observatory(models.Model):

    class Meta:
        verbose_name_plural = 'Observatories'

    id = models.CharField(max_length=63, primary_key=True)
    name = models.CharField(max_length=255, help_text=_('Observatory Name'))
    admin = models.ForeignKey(UserProxy, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class Site(models.Model):
    id = models.CharField(max_length=127, primary_key=True)
    name = models.CharField(max_length=255, help_text=_('Site Name'))
    timezone = models.CharField(default='UTC', max_length=64, help_text=_('Timezone Name'))
    elevation = models.FloatField(
        validators=[MinValueValidator(-500.0), MaxValueValidator(100000.0)],
        help_text=_('Site elevation in meters')
    )
    observatory = models.ForeignKey(Observatory, on_delete=models.CASCADE, related_name="sites")

    def __str__(self):
        return self.name


class Telescope(models.Model):
    id = models.CharField(max_length=191, primary_key=True)
    name = models.CharField(max_length=255, help_text=_('Telescope Name'))
    aperture = models.FloatField(
        default=0.0, validators=[MinValueValidator(0)],
        help_text=_('The aperture of this telescope in meters')
    )
    latitude = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text=_('Telescope latitude in decimal degrees')
    )
    longitude = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
        help_text=_('Telescope longitude in decimal degrees')
    )
    horizon = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(90)],
        help_text=_('Minimum distance from horizion telescope can point without field of view being obscured, in degrees')
    )
    positive_ha_limit = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        help_text=_('Positive hour-angle limit in hours')
    )
    negative_ha_limit = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-12), MaxValueValidator(0)],
        help_text=_('Negative hour-angle limit in hours')
    )
    zenith_blind_spot = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(180)],
        help_text=_('For AltAz telescopes, radius of zenith blind spot in degrees')
    )
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="telescopes")

    def __str__(self):
        return self.name

    @property
    def observatory(self):
        return self.site.observatory


class Instrument(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, help_text=_('Instrument name'))
    available = models.BooleanField(default=True, help_text=_('Whether this Instrument is available or not'))
    telescope = models.ForeignKey(Telescope, on_delete=models.CASCADE, related_name="instruments")

    def __str__(self):
        return self.name

    @property
    def observatory(self):
        return self.telescope.observatory

class TelescopeStatus(models.Model):

    class Meta:
        verbose_name_plural = 'Telescope Statuses'
        get_latest_by = 'date'
        ordering = ['-date']

    class StatusChoices(models.TextChoices):
        AVAILABLE = 'AVAILABLE', _('Available')
        POINTING = 'POINTING', _('Pointing')
        UNAVAILABLE = 'UNAVAILABLE', _('Unavailable')
        SCHEDULABLE = 'SCHEDULABLE', _('Schedulable')

    date = models.DateTimeField(auto_now_add=True, db_index=True)
    telescope = models.ForeignKey(Telescope, on_delete=models.CASCADE, related_name="statuses")
    status = models.CharField(
        max_length=20, choices=StatusChoices.choices,
        default=StatusChoices.AVAILABLE, help_text=_('Telescope Status')
    )
    reason = models.TextField(blank=True, null=True, help_text=_('Reason for current telescope status'))
    extra = models.JSONField(
        blank=True, default=dict,
        help_text=_('Extra data related to current telescope status or pointing')
    )

    # These fields are just used for a Pointing type status message, to show what instrument pointed where
    target = models.CharField(max_length=255, blank=True, null=True, help_text=_('Target name for current pointing'))
    ra = models.FloatField(
        blank=True, null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(360.0)],
        help_text=_('Target Right Ascension for current pointing in decimal degrees')
    )
    dec = models.FloatField(
        blank=True, null=True,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text=_('Target Declination for current pointing in decimal degrees')
    )
    instrument = models.ForeignKey(
        Instrument, on_delete=models.SET_NULL, blank=True, null=True,
        help_text=_('Instrument reference for current pointing')
    )

    def __str__(self):
        return f"{self.telescope.name} - {self.status} at {self.date}"

    @property
    def observatory(self):
        return self.telescope.observatory

class InstrumentCapability(models.Model):

    class Meta:
        verbose_name_plural = 'Instrument Capabilities'
        get_latest_by = 'date'
        ordering = ['-date']

    class InstrumentStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', _('Available')
        UNAVAILABLE = 'UNAVAILABLE', _('Unavailable')
        SCHEDULABLE = 'SCHEDULABLE', _('Schedulable')

    date = models.DateTimeField(auto_now_add=True, db_index=True)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="capabilities")
    status = models.CharField(
        max_length=32, choices=InstrumentStatus.choices,
        default=InstrumentStatus.AVAILABLE,
        help_text=_('Instrument availability status')
    )
    optical_element_groups = models.JSONField(
        blank=True, default=dict, help_text=_('Dictionary of Optical elements available for instrument')
    )
    operation_modes = models.JSONField(
        blank=True, default=dict, help_text=_('Dictionary of Operation modes available for instrument')
    )

    def __str__(self):
        return f"{self.instrument.name} - Capability at {self.date}"

    @property
    def observatory(self):
        return self.instrument.observatory


class TargetTypes(models.TextChoices):
    ICRS = 'ICRS', _('ICRS')
    MPC_MINOR_PLANET = 'MPC_MINOR_PLANET', _('MPC Minor Planet')
    MPC_COMET = 'MPC_COMET', _('MPC Comet')
    JPL_MAJOR_PLANET = 'JPL_MAJOR_PLANET', _('JPL Major Planet')
