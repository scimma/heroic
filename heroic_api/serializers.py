from rest_framework import serializers
from .models import (Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability,
                     Profile)


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source='user.email', read_only=True)
    api_token = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = ('api_token', 'email', 'credential_name')


class TelescopeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelescopeStatus
        fields = '__all__'


class InstrumentCapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = InstrumentCapability
        fields = '__all__'


class InstrumentSerializer(serializers.ModelSerializer):
    optical_element_groups = serializers.JSONField(write_only=True, required=False, default=dict)
    operation_modes = serializers.JSONField(write_only=True, required=False, default=dict)
    status = serializers.ChoiceField(choices=InstrumentCapability.InstrumentStatus.choices,
                                     write_only=True, required=False)

    class Meta:
        model = Instrument
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add in the current instrument capability into the response
        try:
            current_capability = instance.capabilities.latest()
            data['status'] = current_capability.status
            data['optical_element_groups'] = current_capability.optical_element_groups
            data['operation_modes'] = current_capability.operation_modes
        except InstrumentCapability.DoesNotExist:
            pass
        return data

    def create(self, validated_data):
        status = validated_data.pop('status', None)
        optical_element_groups = validated_data.pop('optical_element_groups', {})
        operation_modes = validated_data.pop('operation_modes', {})
        instance = super().create(validated_data)
        # If we set any instrument capability fields on creation, then create an associated InstrumentCapability instance
        if (status or optical_element_groups or operation_modes):
            InstrumentCapability.objects.create(
                instrument=instance,
                status=status,
                optical_element_groups=optical_element_groups,
                operation_modes=operation_modes
            )
        instance.refresh_from_db()
        return instance


class TelescopeSerializer(serializers.ModelSerializer):
    instruments = InstrumentSerializer(many=True, required=False)
    extra = serializers.JSONField(write_only=True, required=False, default=dict)
    status = serializers.ChoiceField(choices=TelescopeStatus.StatusChoices.choices,
                                     write_only=True, required=False)
    reason = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Telescope
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add in the current telescope status into the response
        try:
            current_status = instance.statuses.latest()
            data['status'] = current_status.status
            if current_status.reason:
                data['reason'] = current_status.reason
            if current_status.extra:
                data['extra'] = current_status.extra
            if current_status.ra:
                data['ra'] = current_status.ra
            if current_status.dec:
                data['dec'] = current_status.dec
            if current_status.instrument:
                data['instrument'] = current_status.instrument.id
        except TelescopeStatus.DoesNotExist:
            pass
        return data

    def create(self, validated_data):
        status = validated_data.pop('status', None)
        reason = validated_data.pop('reason', None)
        extra = validated_data.pop('extra', {})
        instance = super().create(validated_data)
        # If we set any instrument capability fields on creation, then create an associated InstrumentCapability instance
        if (status or reason or extra):
            TelescopeStatus.objects.create(
                telescope=instance,
                status=status,
                reason=reason,
                extra=extra
            )
        instance.refresh_from_db()
        return instance


class SiteSerializer(serializers.ModelSerializer):
    telescopes = TelescopeSerializer(many=True, required=False)
    class Meta:
        model = Site
        fields = '__all__'


class ObservatorySerializer(serializers.ModelSerializer):
    sites = SiteSerializer(many=True, required=False)
    class Meta:
        model = Observatory
        fields = '__all__'
