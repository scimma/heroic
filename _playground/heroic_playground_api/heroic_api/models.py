from django.db import models


class Observatory(models.Model):
    name = models.CharField(max_length=100)
    observatory_id = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Site(models.Model):
    name = models.CharField(max_length=100)
    site_id = models.CharField(max_length=50, unique=True)
    timezone = models.IntegerField()
    elevation = models.FloatField()
    observatory = models.ForeignKey(Observatory, on_delete=models.CASCADE, related_name="sites")

    def __str__(self):
        return self.name


class Telescope(models.Model):
    name = models.CharField(max_length=100)
    telescope_id = models.CharField(max_length=50, unique=True)
    aperture = models.FloatField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    horizon = models.FloatField()
    positive_ha_limit = models.FloatField()
    negative_ha_limit = models.FloatField()
    zenith_blind_spot = models.FloatField()
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="telescopes")

    def __str__(self):
        return self.name


class Instrument(models.Model):
    name = models.CharField(max_length=100)
    instrument_id = models.CharField(max_length=50, unique=True)
    available = models.BooleanField(default=True)
    telescope = models.ForeignKey(Telescope, on_delete=models.CASCADE, related_name="instruments")

    def __str__(self):
        return self.name


class TelescopeStatus(models.Model):
    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("POINTING", "Pointing"),
        ("UNAVAILABLE", "Unavailable"),
        ("SCHEDULABLE", "Schedulable"),
    ]
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    reason = models.TextField(blank=True, null=True)
    extra = models.JSONField(blank=True, null=True)
    target = models.CharField(max_length=100, blank=True, null=True)
    ra = models.FloatField(blank=True, null=True)
    dec = models.FloatField(blank=True, null=True)
    instrument = models.ForeignKey(Instrument, on_delete=models.SET_NULL, blank=True, null=True)
    telescope = models.ForeignKey(Telescope, on_delete=models.CASCADE, related_name="statuses")

    def __str__(self):
        return f"{self.telescope.name} - {self.status} at {self.date}"


class InstrumentCapability(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    available = models.BooleanField(default=True)
    optical_element_groups = models.JSONField(blank=True, null=True)
    operation_modes = models.JSONField(blank=True, null=True)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="capabilities")

    def __str__(self):
        return f"{self.instrument.name} - Capability at {self.date}"
    