import requests
import logging
from .record import Record

log = logging.getLogger(__name__)


class Reader:
    endpoint_url = 'https://apiv2.vapaaehtoistyo.fi'
    rest_user_agent = 'HelsinkiVETImporter/0.1'
    timeout = 5.0

    def __init__(self, api_key):
        if not api_key:
            raise ValueError("Really need API-key!")
        self.api_key = api_key
        self.http_client = None

    def _setup_client(self):
        headers = {
            'Accept': 'application/json',
            'User-Agent': self.rest_user_agent,
            "Authorization": "Bearer %s" % self.api_key
        }

        s = requests.Session()
        s.headers.update(headers)

        return s

    def _get_client(self):
        if self.http_client:
            return self.http_client

        self.http_client = self._setup_client()

        return self.http_client

    @staticmethod
    def _load_status_check(data):
        if 'status' not in data or data['status'] != "ok":
            raise RuntimeError("Vapaaehtoistyö.fi response isn't ok!")
        if 'data' not in data:
            raise RuntimeError("Vapaaehtoistyö.fi response doesn't contain 'data'!")

    def load_entry(self, event_id):
        url = "%s/task/%s" % (self.endpoint_url, event_id)
        response = self._get_client().get(url, timeout=self.timeout)
        if response.status_code != 200:
            raise RuntimeError("Failed to request data from Vapaaehtoistyö.fi API! HTTP/%d" %
                               response.status_code)

        data = response.json()
        self._load_status_check(data)
        data_obj = Record(data)

        return data_obj

    def load_entries(self):
        page = 1
        total_records = None
        batch_size = 1
        ret = []
        while batch_size:
            url = "%s/collection/task?page=%d" % (self.endpoint_url, page)
            response = self._get_client().get(url, timeout=self.timeout)

            if response.status_code != 200:
                raise RuntimeError("Failed to request data from Vapaaehtoistyö.fi API! HTTP/%d" %
                                   response.status_code)
            data = response.json()
            self._load_status_check(data)
            if not total_records:
                total_records = int(data['data']['totalRecords'])

            batch_size = len(data['data']['records'])
            for data in data['data']['records']:
                data_obj = Record(data)
                ret.append(data_obj)
            page += 1

        return total_records, ret

    def load_photo(self, id):
        http_client = self._setup_client()
        url = "%s/collection/task-photo/%s" % (self.endpoint_url, id)
        response = http_client.get(url, timeout=self.timeout)
        if response.status_code != 200:
            if response.status_code == 404:
                # No photo for this event
                return None, None

            raise RuntimeError("Failed to request data from Vapaaehtoistyö.fi API! HTTP/%d" %
                               response.status_code)

        data = response.json()
        if 'status' not in data or data['status'] != "ok":
            raise RuntimeError("Vapaaehtoistyö.fi response isn't ok!")
        if 'data' not in data:
            log.warning("Requested photo for %s, but didn't receive any data!" % id)
            return None, None
        if data['data']['photo']['type'] != "Buffer":
            raise RuntimeError("Vapaaehtoistyö.fi response isn't ok!")
        mime_type = data['data']['mimetype']
        photo = bytearray(data['data']['photo']['data'])

        return mime_type, photo
