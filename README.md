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


## Tests
Unit tests can be run with:

    poetry run python manage.py test
