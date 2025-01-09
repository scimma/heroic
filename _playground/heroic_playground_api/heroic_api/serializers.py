from rest_framework import serializers
from .models import Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability


class ObservatorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Observatory
        fields = '__all__'


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = '__all__'


class TelescopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Telescope
        fields = '__all__'


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = '__all__'


class TelescopeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelescopeStatus
        fields = '__all__'


class InstrumentCapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = InstrumentCapability
        fields = '__all__'