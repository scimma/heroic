# HEROIC
The HEROIC application aims to store telescope status and instrument capabilities and provide an API for querying that data in different ways.


## API
This application provides an API for creating and getting telescope and instrument information. The expected usage of the API for initially setting up Telescope includes:

1. POST observatory info to `/api/observatories/`
2. POST site info to `/api/sites/` for that observatory
3. POST telescope info to `/api/telescopes/` for that site, including status info if you want
4. POST instrument info to `/api/instruments/` for that telescope, including current instrument capabilities

Then once a telescope and instrument are set up, periodic updates can be sent for their status and capabilities through the API:
1. POST new telescope status updates to `/api/telescopes/<telescope_id>/status/` as needed
2. POST new instrument capabilities updates to `/api/instruments/<instrument_id>/capabilities/` as needed.


### Authentication
Authentication occurs via SCiMMA admin, which uses CILogin and KeyCloak. In practice this means that a user account in HEROIC must
first login via the User Interface to "create" their user account in SCiMMA admin and associate it with a HEROIC user account which has an
API Token. After that, their HEROIC API Token can be used for future authentication with HEROIC, which behind the scenes will verify their
SCiMMA credentials. Users with the "SCiMMA Developers" claim will be automatically given a superuser acount in HEROIC.


### Permissions
Everyone has permission to GET from any HEROIC endpoint. POSTs are limited to an account set as the `admin` account of an Observatory
for any data relating to components of that Observatory. This means that initially, a HEROIC admin/superuser account must create a new
Observatory and assign another user as that Observatory's admin. After that, the observatory admin user can POST all other data into
HEROIC for that observatory.


## Development
This project uses poetry for dependency management. To develop with this project run:

    poetry install
    poetry run python manage.py migrate
    poetry run python manage.py runserver

You will likely want to override some settings for local development, so create a `local_settings.py` file in the root directory and fill it in with something like this:

```python
from heroic_base.settings import *

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = (
    'rest_framework.authentication.SessionAuthentication',
    'rest_framework.authentication.TokenAuthentication',
)

CSRF_TRUSTED_ORIGINS = ['http://localhost:5173','http://127.0.0.1:5173','http://*']
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
```

You will also want to create a local superuser account to interact with the admin interface and get its API token to interact with the api.

## Tests
Unit tests can be run with:

    poetry run python manage.py test
