import json
import time
from typing import Optional, List, Dict
from urllib.parse import urlparse

import requests
from requests.exceptions import HTTPError, RequestException, Timeout
from urllib3.exceptions import LocationParseError

from exceptions.tinyurl_exceptions import TinyUrlUpdateError, TinyUrlCreationError, NetworkError, RequestError
from tunneling.tunnelservicehandler import TunnelServiceHandler
from utility.url_tools import generate_string_5_30

BASE_URL = "https://api.tinyurl.com"


class ApiClient:
    def __init__(self, auth_tokens: [], fallback_urls=None):
        self.auth_tokens: List[str] = auth_tokens
        self.token_selected = self.auth_tokens[0]
        self.alias_token_mapping: Dict[int, str] = {}
        self.tunneling_service: TunnelServiceHandler = TunnelServiceHandler(fallback_urls)

    def create_tinyurl(self, target_url: str, expires_at: str = None, no_check: bool = False):
        headers = self.build_headers(token=self.token_selected)
        request_url = f'{BASE_URL}/create'
        if not no_check:
            self.check_target_url(target_url)

        length = 5
        while True:
            try:
                payload = {
                           'url': target_url,
                           'alias': generate_string_5_30(length=length),
                           'expires_at': expires_at
                           }
                response = requests.post(url=request_url, headers=headers, data=json.dumps(payload), timeout=3)
                response.raise_for_status()
                data = response.json()['data']
                self.alias_token_mapping[data['alias']] = self.token_selected
                return data
            except HTTPError as e:
                if response.json()['errors']:
                    if response.json()['errors'][0] == 'Alias is not available.':
                        length += 1
                        continue
                    raise TinyUrlCreationError(response.json()['errors'], response.status_code)
                else:
                    raise TinyUrlCreationError([str(e)], response.status_code)
            except Timeout:
                raise NetworkError('Connection error. Request timed out!')
            except RequestException as e:
                raise RequestError(e)
            except ValueError:
                raise NetworkError("Can't find ['data'] in response! Check Tinyurl docs")

    """
    Updates the redirect target of a TinyURL alias.

    Args:
        alias (str): The TinyURL alias to update.
        target_url (str): The new target URL for the alias.
        token_id (int): The token ID used for authorization.

    Returns:
        str: The updated TinyURL alias.

    Raises:
        TinyUrlCreationError: If there's an issue creating the TinyURL.
        NetworkError: If there's a network error during the update.
        RequestError: If the request to update the TinyURL fails.
    """
    def update_tinyurl_redirect_service(self, alias: str, target_url: str, headers: dict = None, retry: int = 3,
                                        timeout: int = 3):
        headers = self.build_headers(token=self.alias_token_mapping[alias], headers=headers)
        request_url = f'{BASE_URL}/change'
        payload = {
            'domain': 'tinyurl.com',
            'url': target_url,
            'alias': alias,
        }
        while True:
            try:
                response = requests.patch(url=request_url, headers=headers, data=json.dumps(payload), timeout=timeout)
                response.raise_for_status()
                data = response.json()['data']
                return data
            except HTTPError as e:
                if retry:
                    retry -= 1
                    continue
                if response.json() and 'errors' in response.json():
                    raise TinyUrlUpdateError(response.json()['errors'], response.status_code)
                else:
                    raise TinyUrlUpdateError([str(e)], response.status_code)
            except Timeout:
                if retry:
                    retry -= 1
                raise NetworkError('Connection error. Request timed out!')
            except RequestException as e:
                raise RequestError(e)
            except ValueError:
                raise NetworkError("Can't find ['data'] in response! Check Tinyurl docs")

    def update_tinyurl_redirect_user(self, alias: str, target_url: str, headers: dict = None):
        self.check_target_url(target_url)
        headers = self.build_headers(token=self.alias_token_mapping[alias], headers=headers)
        request_url = f'{BASE_URL}/change'
        payload = {
            'domain': 'tinyurl.com',
            'url': target_url,
            'alias': alias,
        }

        attempts = 0
        delay = 1
        while attempts < 3:
            try:
                response = requests.patch(url=request_url, headers=headers, data=json.dumps(payload), timeout=3)
                response.raise_for_status()
                data = response.json()['data']
                return data
            except HTTPError as e:
                if response.json() and 'errors' in response.json():
                    raise TinyUrlUpdateError(response.json()['errors'], response.status_code)
                else:
                    raise TinyUrlUpdateError([str(e)], response.status_code)
            except Timeout:
                attempts += 1
                if attempts == 3:
                    raise NetworkError('Connection error. Request timed out!')
                time.sleep(delay)
                delay *= 2
            except RequestException as e:
                raise RequestError(e)
            except ValueError:
                raise NetworkError("Can't find ['data'] in response! Check Tinyurl docs")

    #  Used in tum cli
    def switch_auth_token(self, token_id):
        self.token_selected = self.auth_tokens[token_id - 1]

    #   For api usage
    def cycle_next_token(self):
        current_index = self.auth_tokens.index(self.token_selected)
        new_index = (current_index + 1) if current_index != len(self.auth_tokens) else 0
        self.token_selected = self.auth_tokens[new_index]
        return self.token_selected

    @staticmethod
    def check_target_url(url: str):
        try:
            response = requests.head(url, timeout=3)
            if urlparse(response.url).netloc == urlparse(url).netloc:
                return
            response.raise_for_status()
        except HTTPError as e:
            raise RequestError(f"Error: {e}")
        except Timeout:
            raise NetworkError('Connection error. Request timed out!')
        except RequestException:
            raise RequestError("Unknown url", url=url)
        except LocationParseError:
            raise RequestError("Incorrect url format", url=url)

    def build_headers(self, token_index: Optional[int] = None, token: Optional[str] = None,
                      headers: Optional[dict] = None) -> dict:
        auth_token = token or self.alias_token_mapping.get(token_index)
        auth_headers = {'Authorization': f'Bearer {auth_token}',
                        'Content-Type': 'application/json',
                        'User-Agent': 'Google Chrome'
                        }
        if not headers:
            headers = {}
        joint_headers = {**auth_headers, **headers}
        return joint_headers

    """
    def _make_request(self,
                      token_id: int, request_call: Callable, request_url: str,
                      headers: Optional[dict] = None, data: Optional[dict] = None,
                      params: Optional[dict] = None
                      ):
        if not headers:
            headers = {}
        self.headers = self.build_headers(token_id)
        joint_headers = {**self.headers, **headers}
        if request_call == requests.post:
            request_url = BASE_URL + '/create'
        elif request_call == requests.patch:
            request_url = BASE_URL + '/change'
        else:
            pass
        pass
"""