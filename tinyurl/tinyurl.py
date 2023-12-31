import logging
from urllib.parse import urlparse

from api.apiclient import ApiClient
from utility.url_tools import get_final_domain

logger = logging.getLogger('')
SUCCESS = 25


class TinyUrl:

    def __init__(self, new_id):
        self.tinyurl = None
        self.alias = None
        self.domain = None
        self.final_url = None
        self.id = new_id

    def instantiate_tinyurl(self, url: str, api_client: ApiClient, expires_at=None, no_check=False):
        data = api_client.create_tinyurl(url, expires_at=expires_at, no_check=no_check)
        self.final_url = f'https://{data["url"]}'.strip('/') if not urlparse(data['url']).scheme else data['url'].strip(
            '/')  # Because tinyurl response sometimes omits scheme
        self.domain = get_final_domain(self.final_url)
        self.tinyurl = f"https://tinyurl.com/{data['alias']}"
        self.alias = data['alias']
        logger.log(SUCCESS, f'Tinyurl[{self.id}] created --> {self.final_url}')

    def update_redirect(self, url: str, api_client: ApiClient):
        data = api_client.update_tinyurl_redirect_user(self.alias, url)
        self.final_url = f'https://{data["url"]}' if not urlparse(data['url']).scheme else data[
            'url']  # Because tinyurl response sometimes omits scheme
        self.domain = get_final_domain(self.final_url)
        logger.log(SUCCESS, f'Tinyurl[{self.id}] updated --> {self.final_url}')

    def __str__(self):
        return f'\033[1;33mTinyurl[{self.id}]' \
               f'\n__________________________________\033[0;33m'\
               f'\nurl:    {self.tinyurl}' \
               f'\ntarget: {self.final_url}'
