# Generated by Django 5.2.1 on 2025-05-28 20:07

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('heroic_api', '0004_instrument_instrument_url_site_weather_url_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='telescopestatus',
            name='dec',
        ),
        migrations.RemoveField(
            model_name='telescopestatus',
            name='instrument',
        ),
        migrations.RemoveField(
            model_name='telescopestatus',
            name='ra',
        ),
        migrations.RemoveField(
            model_name='telescopestatus',
            name='target',
        ),
        migrations.AlterField(
            model_name='instrumentcapability',
            name='date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='telescopestatus',
            name='date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='telescopestatus',
            name='extra',
            field=models.JSONField(blank=True, default=dict, help_text='Extra data related to current telescope status'),
        ),
        migrations.AlterField(
            model_name='telescopestatus',
            name='status',
            field=models.CharField(choices=[('AVAILABLE', 'Available'), ('UNAVAILABLE', 'Unavailable'), ('SCHEDULABLE', 'Schedulable')], default='AVAILABLE', help_text='Telescope Status', max_length=20),
        ),
        migrations.CreateModel(
            name='TelescopePointing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(db_index=True)),
                ('target', models.CharField(blank=True, help_text='Target name for current pointing', max_length=255, null=True)),
                ('coordinate', django.contrib.gis.db.models.fields.PointField(help_text='Target ra/dec for the current pointing in decimal degrees', srid=4326)),
                ('extra', models.JSONField(blank=True, default=dict, help_text='Extra data related to current pointing')),
                ('instrument', models.ForeignKey(blank=True, help_text='Instrument reference for current pointing', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pointings', to='heroic_api.instrument')),
                ('telescope', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pointings', to='heroic_api.telescope')),
            ],
            options={
                'verbose_name_plural': 'Telescope Pointings',
                'ordering': ['-date'],
                'get_latest_by': 'date',
            },
        ),
    ]
