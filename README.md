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


## Development
This project uses poetry for dependency management. To develop with this project run:

    poetry install
    poetry run python manage.py migrate
    poetry run python manage.py runserver


## Tests
Unit tests can be run with:

    poetry run python manage.py test
