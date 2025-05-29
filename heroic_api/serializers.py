from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from rest_framework import serializers
from heroic_api.visibility import telescope_dark_intervals
from heroic_api.models import (Observatory, Site, Telescope, Instrument, TelescopeStatus, InstrumentCapability,
                     Profile, TargetTypes)


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

    def validate(self, data):
        validated_data = super().validate(data)
        split_id = validated_data.get('id', '').rsplit('.', 1)
        if len(split_id) != 2 or split_id[0] != validated_data.get('telescope').id:
            raise serializers.ValidationError(_("Instrument id must follow the format 'observatory.site.telescope.instrument'"))

        return validated_data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add in the current instrument capability into the response
        try:
            current_capability = instance.capabilities.latest()
            data['last_capability_update'] = current_capability.date
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
    next_twilight = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Telescope
        fields = '__all__'

    def get_next_twilight(self, obj):
        ''' This returns an array of either one or two twilights, depending on if we are currently within
            a twilight period or not. If in twilight, it returns now to the end for the first plust the whole
            next twilight, otherwise it just returns the whole next twilight.
        '''
        dark_intervals = telescope_dark_intervals(obj)
        if dark_intervals[0][0] < timezone.now():
            # We are within the first interval, so show that plus one more
            return dark_intervals[:2]
        else:
            # The first interval is in the future, so only return it
            return dark_intervals[:1]

    def validate(self, data):
        validated_data = super().validate(data)
        split_id = validated_data.get('id', '').rsplit('.', 1)
        if len(split_id) != 2 or split_id[0] != validated_data.get('site').id:
            raise serializers.ValidationError(_("Telescope id must follow the format 'observatory.site.telescope'"))

        return validated_data


    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add in the current telescope status into the response
        try:
            current_status = instance.statuses.latest()
            data['status'] = current_status.status
            data['last_status_update'] = current_status.date
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

    def validate(self, data):
        validated_data = super().validate(data)
        split_id = validated_data.get('id', '').rsplit('.', 1)
        if len(split_id) != 2 or split_id[0] != validated_data.get('observatory').id:
            raise serializers.ValidationError(_("Site id must follow the format 'observatory.site'"))

        return validated_data


class ObservatorySerializer(serializers.ModelSerializer):
    sites = SiteSerializer(many=True, required=False)
    class Meta:
        model = Observatory
        fields = '__all__'


class TelescopeDarkIntervalsSerializer(serializers.Serializer):
    start = serializers.DateTimeField(required=True)
    end = serializers.DateTimeField(required=True)
    telescopes = serializers.SlugRelatedField(
        slug_field='id', queryset=Telescope.objects.all(), many=True, required=False, allow_null=True
    )

    def validate(self, data):
        validated_data = super().validate(data)

        # Validate start is < end time
        if validated_data['start'] >= validated_data['end']:
            raise serializers.ValidationError(
                {'end': _('The end datetime must be greater than the start datetime')}
            )

        # If no specific telescopes were choosen, assume all will be used
        if not validated_data.get('telescopes'):
            validated_data['telescopes'] = list(Telescope.objects.all())

        return validated_data


class TargetVisibilityQuerySerializer(serializers.Serializer):
    MINOR_PLANET_FIELDS = [
        'epoch_of_elements', 'orbital_inclination', 'longitude_of_ascending_node', 'argument_of_perihelion',
        'mean_distance', 'eccentricity', 'mean_anomaly'
    ]
    COMET_FIELDS = [
        'epoch_of_elements', 'orbital_inclination', 'longitude_of_ascending_node', 'argument_of_perihelion',
        'perihelion_distance', 'eccentricity', 'epoch_of_perihelion'
    ]
    MAJOR_PLANET_FIELDS = [
        'epoch_of_elements', 'orbital_inclination', 'longitude_of_ascending_node', 'argument_of_perihelion',
        'mean_distance', 'eccentricity', 'mean_anomaly', 'daily_motion'
    ]
    # Base fields
    telescopes = serializers.SlugRelatedField(
        slug_field='id', queryset=Telescope.objects.all(), many=True, required=False, allow_null=True
    )
    start = serializers.DateTimeField(required=True)
    end = serializers.DateTimeField(required=True)
    # Constraints
    max_airmass = serializers.FloatField(
        min_value=1.0, max_value=25.0, default=2.0, required=False, help_text=_('Maximum acceptable airmass')
    )
    max_lunar_phase = serializers.FloatField(
        min_value=0.0, max_value=1.0, default=1.0, required=False,
        help_text=_('Maximum acceptable lunar phase fraction from 0 (new moon) to 1 (full moon)')
    )
    min_lunar_distance = serializers.FloatField(
        min_value=0.0, max_value=180.0, default=0.0, required=False,
        help_text=_('Minimum acceptable angular separation between the target and moon in decimal degrees')
    )

    # Target params
    target_type = serializers.CharField(
        read_only=True, allow_blank=True, help_text=_('Type of target set by serializer')
    )
    ## ra/dec ICRS targets
    ra = serializers.FloatField(
        min_value=0.0, max_value=360.0, required=False, help_text=_('Right Ascension in decimal degrees')
    )
    dec = serializers.FloatField(
        min_value=-90.0, max_value=90.0, required=False, help_text=_('Declination in decimal degrees')
    )
    proper_motion_ra = serializers.FloatField(
        min_value=-20000.0, max_value=20000.0, required=False,
        label=_('Right Ascience Proper Motion mas/yr'),
        help_text=_('Right Ascension Proper Motion of the target in mas/yr')
    )
    proper_motion_dec = serializers.FloatField(
        min_value=-20000.0, max_value=20000.0, required=False,
        label=_('Declination Proper Motion mas/yr'),
        help_text=_('Declination Proper Motion of the target in mas/yr')
    )
    parallax = serializers.FloatField(
        min_value=-2000.0, max_value=2000.0, required=False,
        help_text=_('Parallax of the target in mas, up to 2000.0')
    )
    epoch = serializers.FloatField(max_value=2100.0, default=2000.0, required=False, help_text=_('Epoch in MJD'))

    ## Non-sidereal targets
    epoch_of_elements = serializers.FloatField(
        min_value=10000.0, max_value=100000.0, required=False,
        help_text=_('The epoch of orbital elements (MJD)')
    )
    epoch_of_perihelion = serializers.FloatField(
        min_value=361.0, max_value=240000.0, required=False,
        help_text=_('The epoch of perihelion (MJD)')
    )
    orbital_inclination = serializers.FloatField(
        min_value=0.0, max_value=180.0, required=False,
        help_text=_('Orbital Inclination angle in decimal degrees')
    )
    longitude_of_ascending_node = serializers.FloatField(
        min_value=0.0, max_value=360.0, required=False,
        help_text=_('Longitude of Ascending Node angle in decimal degrees')
    )
    longitude_of_perihelion = serializers.FloatField(
        min_value=0.0, max_value=360.0, required=False,
        help_text=_('Longitude of Perihelion angle in degrees')
    )
    argument_of_perihelion = serializers.FloatField(
        min_value=0.0, max_value=360.0, required=False,
        help_text=_('Argument of Perihelion angle in degrees')
    )
    mean_distance = serializers.FloatField(
        required=False, help_text=_('Mean distance in AU')
    )
    perihelion_distance = serializers.FloatField(
        required=False, help_text=_('Perihelion distance in AU')
    )
    eccentricity = serializers.FloatField(
        min_value=0.0, required=False,
        help_text=_('Eccentricity of the orbit')
    )
    mean_anomaly = serializers.FloatField(
        min_value=0.0, max_value=360.0, required=False, help_text=_('Mean Anomaly angle in degrees')
    )
    daily_motion = serializers.FloatField(
        required=False, help_text=_('Daily Motion angle in degrees')
    )

    def validate(self, data):
        validated_data = super().validate(data)

        # Validate start is < end time
        if validated_data['start'] >= validated_data['end']:
            raise serializers.ValidationError(
                {'end': _('The end datetime must be greater than the start datetime')}
            )

        # If no specific telescopes were choosen, assume all will be used
        if not validated_data.get('telescopes'):
            validated_data['telescopes'] = list(Telescope.objects.all())

        # Make sure that a valid target was submitted
        if validated_data.get('ra') or validated_data.get('dec'):
            if not validated_data.get('ra'):
                raise serializers.ValidationError(
                    {'ra': _(f'The field "ra" is required for ICRS targets')}
                )
            elif not validated_data.get('dec'):
                raise serializers.ValidationError(
                    {'dec': _(f'The field "dec" is required for ICRS targets')}
                )
            validated_data['target_type'] = TargetTypes.ICRS.name
        else:
            # Check how many if any fields are missing from the orbital element types to see what error to return
            missing_minor_planet_fields = [field for field in self.MINOR_PLANET_FIELDS if field not in validated_data]
            missing_comet_fields = [field for field in self.COMET_FIELDS if field not in validated_data]
            missing_major_planet_fields = [field for field in self.MAJOR_PLANET_FIELDS if field not in validated_data]
            if len(missing_major_planet_fields) == 0:
                validated_data['target_type'] = TargetTypes.JPL_MAJOR_PLANET.name
            elif len(missing_minor_planet_fields) == 0:
                validated_data['target_type'] = TargetTypes.MPC_MINOR_PLANET.name
            elif len(missing_comet_fields) == 0:
                validated_data['target_type'] = TargetTypes.MPC_COMET.name
            else:
                missing_minor = len(missing_minor_planet_fields)
                missing_comet = len(missing_comet_fields)
                missing_major = len(missing_major_planet_fields)
                missing_fields = []
                # We are missing some fields of an orbital element target or missing a target completely
                # Sort by which orbital element scheme is missing the least fields
                # But prioritize minor -> comet -> major if missing fields are equal
                if (missing_minor <= missing_comet and
                    missing_minor <= missing_major and
                    missing_minor < len(self.MINOR_PLANET_FIELDS)):
                    missing_fields = missing_minor_planet_fields
                    validated_data['target_type'] = TargetTypes.MPC_MINOR_PLANET.name
                elif (missing_comet <= missing_minor and
                      missing_comet <= missing_major and
                      missing_comet < len(self.COMET_FIELDS)):
                    missing_fields = missing_comet_fields
                    validated_data['target_type'] = TargetTypes.MPC_COMET.name
                elif (missing_major < len(self.MAJOR_PLANET_FIELDS)):
                    missing_fields = missing_major_planet_fields
                    validated_data['target_type'] = TargetTypes.JPL_MAJOR_PLANET.name
                if missing_fields:
                    raise serializers.ValidationError(
                        {field: _(f'This field is required for {validated_data["target_type"]} targets') for field in missing_fields}
                    )
                else:
                    raise serializers.ValidationError(
                        _('Must submit a valid target using either ra/dec, hour_angle/dec, altitude/azimuth, or orbital elements')
                    )
        return validated_data


class TargetVisibilityIntervalResponseSerializer(serializers.Serializer):
    telescope_id = serializers.ListField(child=serializers.ListField(
        child=serializers.DateTimeField(), min_length=2, max_length=2), allow_empty=True)


class TargetVisibilityAirmassSubSerializer(serializers.Serializer):
    times = serializers.ListField(child=serializers.DateTimeField())
    airmasses = serializers.ListField(child=serializers.FloatField())


class TargetVisibilityAirmassResponseSerializer(serializers.Serializer):
    telescope_id = TargetVisibilityAirmassSubSerializer()


class TelescopeDarkIntervalResponseSerializer(serializers.Serializer):
    telescope_id = serializers.ListField(child=serializers.ListField(
        child=serializers.DateTimeField(), min_length=2, max_length=2), allow_empty=True)
