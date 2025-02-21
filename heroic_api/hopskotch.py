"""heroic_api/hopskotch.py

This contains code to authenticate a user, generate a credential, and get aspects of a users account

After the SCIMMA_ADMIN_BASE_URL is defined in settings.py, this module encodes specifics
of the scimma_admin (hopauth) API that goes beyond that configuration. That is, this module
is intended depend on HOPSKOTCH/hopauth/scimma_admin specifics. For example, how the versioning
works, etc

Notes on the change of OIDC Provider from CILogon to SCiMMA's Keycloak instance:
 * Usernames
   * for CILogon, 'vo_person_id' was the key of the username claim. It looked like this: SCiMMA10000030
   * for Keycloak, 'sub' is the key of the username claim. Like this: 0d988bdd-ec83-420d-8ded-dd9091318c24
   * In the changeover from CILogon to Keycloak, vo_person_id variable names were changed to username

The top level functions are:
  * create_credential_for_user()
  * delete_credential()

Lower level and utility functions:
  * TODO: make function glossary
"""
from http.client import responses
import json
import logging
import requests

from django.conf import settings
from django.core.cache import cache
from django.utils import dateparse, timezone
from django.contrib.auth.models import User

from hop.auth import Auth
import scramp


logger = logging.getLogger(__name__)

 # this API client was written against this version of the SCIMMA Admin API
SCIMMA_AUTH_API_VERSION = 1


def get_hop_auth_api_url(api_version=SCIMMA_AUTH_API_VERSION) -> str:
    """Use the SCIMMA_AUTH_BASE_URL from settings.py and construct the API url from that.
    """
    return settings.SCIMMA_AUTH_BASE_URL + f'/api/v{api_version}'


def get_heroic_api_token():
    heroic_api_token = cache.get('heroic_api_token', None)
    if not heroic_api_token:
        logger.debug("Heroic api token doesn't exist in cache, regenerating it now.")
        heroic_api_token, heroic_api_token_expiration = _get_heroic_api_token(
            settings.SCIMMA_AUTH_USERNAME,
            settings.SCIMMA_AUTH_PASSWORD
        )
        expiration_date = dateparse.parse_datetime(heroic_api_token_expiration)
        # Subtract a small amount from timeout to ensure credential is available when retrieved
        timeout = (expiration_date - timezone.now()).total_seconds() - 60
        cache.set('heroic_api_token', heroic_api_token, timeout=timeout)
    return heroic_api_token


def _get_heroic_api_token(scram_username, scram_password) -> str:
    """return the Hop Auth API token for the HEROIC service account
    """
    hop_auth_api_url = get_hop_auth_api_url()

    # Peform the first round of the SCRAM handshake:
    client = scramp.ScramClient(["SCRAM-SHA-512"], scram_username, scram_password)
    client_first = client.get_client_first()
    logger.debug(f'_get_heroic_api_token: SCRAM client first request: {client_first}')

    scram_resp1 = requests.post(hop_auth_api_url + '/scram/first',
                                json={"client_first": client_first},
                                headers={"Content-Type":"application/json"})
    logger.debug(f'_get_heroic_api_token: SCRAM server first response: {scram_resp1.json()}')

    # Peform the second round of the SCRAM handshake:
    client.set_server_first(scram_resp1.json()["server_first"])
    client_final = client.get_client_final()
    logger.debug(f'_get_heroic_api_token: SCRAM client final request: {client_final}')

    scram_resp2 = requests.post(hop_auth_api_url + '/scram/final',
                                json={"client_final": client_final},
                                headers={"Content-Type":"application/json"})
    logger.debug(f'_get_heroic_api_token: SCRAM server final response: {scram_resp2.json()}')

    client.set_server_final(scram_resp2.json()["server_final"])

    # Get the token we should have been issued:
    response_json = scram_resp2.json()
    heroic_api_token = response_json["token"]
    heroic_api_token_expiration = response_json['token_expires']
    heroic_api_token = f'Token {heroic_api_token}'  # Django wants this (Token<space>) prefix
    logger.debug(f'_get_heroic_api_token: Token issued: {heroic_api_token} expiration: {heroic_api_token_expiration}')

    return heroic_api_token, heroic_api_token_expiration


def get_or_create_user(claims: dict):
    """Create a User instance in the SCiMMA Auth Django project. If a SCiMMA Auth User
    matching the claims already exists, return that Users json dict from the API..

    Because this method requires the OIDC Provider claims, it must be called from some where
    the claims are available, e.g.
     * `auth_backend.HopskotchOIDCAuthenticationBackend.create_user` (if the Heroic User doesn't exist).
     * `auth_backend.HopskotchOIDCAuthenticationBackend.update_user.` (if the Heroic User does exist).

    :param claims: The claims dictionary from the OIDC Provider.
    :type claims: dict

    Heroic requires that SCiMMA Auth have a User instance matching the OIDC claims.
    (Both Heroic and SCiMMA Auth have similar OIDC Provider configuration and workflows).

    The claims dictionary is passed through to the SCiMMA Auth API as the request.data and
    it looks like this:
    {
        'sub': 'edb01519-2541-4fa4-a96b-95d09e152f51',
        'email': 'lindy.lco@gmail.com'
        'email_verified': False,
        'name': 'W L',
        'given_name': 'W',
        'family_name': 'L',
        'preferred_username': 'lindy.lco@gmail.com',
        'upstream_idp': 'http://google.com/accounts/o8/id',
        'is_member_of': ['/Hopskotch Users'],
    }
    However, SCiMMA Auth needs the following keys added:
    {
        'vo_person_id': claims['sub']
    }
    (This is for historical reasons having to do with the CILogon to Keycloak move).

    If a User matching the given claims already exists at SCiMMA Auth,
    return it's JSON dict, which looks like this:
    {
        "pk": 45,
        "username": "0d988bdd-ec83-420d-8ded-dd9091318c24",
        "email": "llindstrom@lco.global"
    }
    """
    logger.debug(f'get_or_create_user claims: {claims}')

    # check to see if the user already exists in SCiMMA Auth
    heroic_api_token = get_heroic_api_token()
    username = claims['sub']

    hop_user = get_hop_user(username, heroic_api_token)
    if hop_user is not None:
        logger.debug(f'get_or_create_user SCiMMA Auth User {username} already exists')
        return hop_user, False  # not created
    else:
        logger.debug(f'hopskotch.get_or_create_user {username}')
        # add the keys that SCiMMA Auth needs
        claims['vo_person_id'] = username

        # pass the claims on to SCiMMA Auth to create the User there.
        url = get_hop_auth_api_url() +  f'/users'
        # this requires admin priviledge so use HEROIC service account API token
        response = requests.post(url, json=claims,
                                 headers={'Authorization': heroic_api_token,
                                          'Content-Type': 'application/json'})
        if response.status_code == 201:
            hop_user = response.json()
            logger.debug(f'get_or_create_user new hop_user: {hop_user} type: {type(hop_user)}')
        else:
            logger.debug(f'get_or_create_user failed with status {response.status_code} and content {response.text}')

        return hop_user, True


def verify_credential_for_user(username: str, credential_name: str):
    """
        Attempt to retrieve an existing credential to verify that it exists on the server
    """
    url = get_hop_auth_api_url() + f'/users/{username}/credentials/{credential_name}'
    user_api_token = get_user_api_token(username)

    try:
        response = requests.get(url,
                                headers={'Authorization': user_api_token,
                                        'Content-Type': 'application/json'})
        response.raise_for_status()
        credential = response.json()
        if credential.get('username') == credential_name:
            return True
        else:
            logger.warning(f"Credential with name {credential_name} for user {username} does not match")
    except Exception as e:
        logger.warning(f"Failed to verify credential with name {credential_name} for user {username}")

    return False


def check_and_regenerate_hop_credential(user: User):
    """ Check that the Django model user profile has a valid credential, and if not, generate a new one
    """
    if ((not user.profile.credential_name or not user.profile.credential_password) or
        not verify_credential_for_user(user.username, user.profile.credential_name)):
        regenerate_hop_credential(user)


def regenerate_hop_credential(user: User):
    """ Create hop credential for django model user
    """
    hop_auth = create_credential_for_user(user.get_username())
    user.profile.credential_name = hop_auth.username
    user.profile.credential_password = hop_auth.password
    user.profile.save()


def create_credential_for_user(username: str, heroic_api_token: str = None) -> Auth:
    """Set up user for all Hopskotch interactions.
    (Should be called upon logon (probably via OIDC authenticate)

    In SCiMMA Auth:
    * creates user SCRAM credential (hop.auth.Auth instance)
    * returns hop.auth.Auth to authenticate() for inclusion in Session dictionary
    """
    logger.info(f'create_credential_for_user Authorizing for Hopskotch, user: {username}')

    if not heroic_api_token:
        heroic_api_token = get_heroic_api_token()

    user_api_token = get_user_api_token(username, heroic_api_token=heroic_api_token)

    # create user SCRAM credential (hop.auth.Auth instance)
    user_hop_auth = _create_credential_for_user(username, user_api_token)
    logger.info(f'create_credential_for_user SCRAM credential {user_hop_auth.username} created for {username}')

    return user_hop_auth


def get_hop_user(username, api_token) -> dict:
    """Return the SCiMMA Auth User with the given username.
    If no SCiMMA Auth User exists with the given username, return None.

    /api/v1/users/{username} returns that user dictionary of the form:

    {
        "id": 20,
        "username": "0d988bdd-ec83-420d-8ded-dd9091318c24",
        "email": "llindstrom@lco.global"
    }
    """
    url = f"{get_hop_auth_api_url()}/users/{username}"
    response = requests.get(url,
                            headers={'Authorization': api_token,
                                     'Content-Type': 'application/json'})

    if response.status_code == 200:
        # from the response, extract the user dictionarie
        hop_user = response.json()
        logger.info(f'get_hop_user hop_user: {hop_user}')
    else:
        logger.debug(f'get_hop_user: failed with status {response.status_code} and response.json(): {response.json()}')
        hop_user = None

    if hop_user is None:
        logger.warning(f'get_hop_user: SCiMMA Auth user {username} not found.')

    return hop_user


def _create_credential_for_user(username: str, user_api_token) -> Auth:
    """Creates and returns a new credential's hop Auth for the user with the given username.
    """
    # Construct URL to create Hop Auth SCRAM credentials for this user
    url = get_hop_auth_api_url() + f'/users/{username}/credentials'

    logger.info(f'_create_credential_for_user Creating SCRAM credentials for user {username}')
    user_hop_authorization = None
    try:
        response = requests.post(url,
                                data=json.dumps({'description': 'Created by HEROIC'}),
                                headers={'Authorization': user_api_token,
                                        'Content-Type': 'application/json'})
        # for example, {'username': 'llindstrom-93fee00b', 'password': 'asdlkjfsadkjf', 'pk': 0}
        user_hop_username = response.json()['username']
        user_hop_password = response.json()['password']

        # you can never again get this SCRAM credential, so save it somewhere (like the Session)
        user_hop_authorization: Auth = Auth(user_hop_username, user_hop_password)
        logger.debug(f'_create_credential_for_user user_credentials_response.json(): {response.json()}')
    except Exception:
        logger.error(f"_create_credential_for_user Failed to create credential for user {username} with status {response.status_code}: {response.text}")

    return user_hop_authorization


def delete_user_hop_credentials(username, credential_name, user_api_token):
    """Remove the given SCRAM credentials from Hop Auth

    The intention is for HEROIC to create user SCRAM credentials in Hop Auth
    when the user logs in (to HEROIC). HEROIC will save the hop.auth.Auth instance
    in the Django Session and use it if needed with Hopskotch. When
    the user wants to revoke their SCRAM credentials from Hop Auth, use this
    method to do that.
    """
    url = get_hop_auth_api_url() + f'/users/{username}/credentials/{credential_name}'

    # find the <PK> of the SCRAM credential just issued
    response = requests.delete(url,
                               headers={'Authorization': user_api_token,
                                        'Content-Type': 'application/json'})
    if response.status_code == 204:
        logger.info(f"delete_user_hop_credentials: Successfully deleted credential {credential_name} for user {username}")
    else:
        logger.error(f'delete_user_hop_credentials: Failed to delete {credential_name} for user {username}: status {response.status_code} and content {response.text}')


def get_user_api_token(username: str, heroic_api_token=None):
    """return a Hop Auth API token for the given user.

    The tuple returned is the API token, and the expiration date as a string.

    You need an API token to get the user API token and that's what the
    HEROIC service account is for. Use the heroic_api_token (the API token
    for the HEROIC service account), to get the API token for the user with
    the given username. If the heroic_api_token isn't passed in, get one.
    """
    user_api_token = cache.get(f'user_{username}_api_token', None)
    if not user_api_token:
        logger.debug(f"User {username} api token doesn't exist in cache, regenerating it now.")
        # Set up the URL
        # see scimma-admin/scimma_admin/hopskotch_auth/urls.py (scimma-admin is Hop Auth repo)
        url = get_hop_auth_api_url() + '/oidc/token_for_user'

        # Set up the request data
        # the username comes from the request.user.username for OIDC Provider-created
        # User instances. It is the value of the sub key from Keycloak
        # that Hop Auth (scimma-admin) is looking for.
        # see scimma-admin/scimma_admin.hopskotch_auth.api_views.TokenForOidcUser
        hop_auth_request_data = {
            'vo_person_id': username, # this key didn't change over the switch to Keycloak
        }

        if not heroic_api_token:
            heroic_api_token = get_heroic_api_token()

        # Make the request and extract the user api token from the response
        response = requests.post(url,
                                data=json.dumps(hop_auth_request_data),
                                headers={'Authorization': heroic_api_token,
                                        'Content-Type': 'application/json'})

        if response.status_code == 200:
            # get the user API token out of the response
            token_info = response.json()
            user_api_token = token_info['token']
            user_api_token = f'Token {user_api_token}'  # Django wants a 'Token ' prefix
            user_api_token_expiration_date_as_str = token_info['token_expires']
            # Subtract a small amount from timeout to ensure credential is available when retrieved
            expiration_date = dateparse.parse_datetime(user_api_token_expiration_date_as_str)
            timeout = (expiration_date - timezone.now()).total_seconds() - 60
            cache.set(f'user_{username}_api_token', user_api_token, timeout=timeout)
            logger.debug("Caching ")
            logger.debug(f'get_user_api_token username: {username};  user_api_token: {user_api_token}')
            logger.debug(f'get_user_api_token user_api_token Expires: {user_api_token_expiration_date_as_str}')
        else:
            logger.error((f'get_user_api_token response.status_code: '
                        f'{responses[response.status_code]} [{response.status_code}] ({url})'))

    return user_api_token
