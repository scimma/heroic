from rest_framework import serializers
from .models import Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability


class TelescopeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelescopeStatus
        fields = '__all__'


class InstrumentCapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = InstrumentCapability
        fields = '__all__'


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = '__all__'


class TelescopeSerializer(serializers.ModelSerializer):
    instruments = InstrumentSerializer(many=True)
    class Meta:
        model = Telescope
        fields = '__all__'


class SiteSerializer(serializers.ModelSerializer):
    telescopes = TelescopeSerializer(many=True)
    class Meta:
        model = Site
        fields = '__all__'


class ObservatorySerializer(serializers.ModelSerializer):
    sites = SiteSerializer(many=True)
    class Meta:
        model = Observatory
        fields = '__all__'
