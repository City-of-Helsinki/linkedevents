# Python >2.7 or >3 needed

import sys
import os
import json
import argparse

try:  # Try Python3 first
    import urllib.parse as urllib_parse
    import urllib.request as urllib_request
except ImportError:  # Python 2 fallback
    from urllib2 import urlparse as urllib_parse
    import urllib2 as urllib_request


# Constants
API_BASE_URL = "http://api.hel.fi/linkedevents/v0.1/event/"
__VERSION__ = ('0', '0', '1')
USER_AGENT = '{} ({})'.format(
    os.path.basename(sys.argv[0]), '.'.join(__VERSION__))
LANGUAGES = ['fi', 'sv', 'en']


def parse_args():
    """
    Parse arguments.
    :return: parsed arguments (Namespace instance)
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--param',
                        help="one or more request parameters in format key=val",
                        action='append')
    parser.add_argument("--url", help="API url", default=API_BASE_URL)
    parser.add_argument("-v", "--verbosity", action="count", default=0)
    args = parser.parse_args()
    print(args)
    return args


def parse_url_params(params):
    """
    Convert a list of key=val strings to a dict.
    :param params: list of key=val strings
    :return: dict of parameters
    """
    params_tuples = [x.split('=') for x in params]
    return dict(params_tuples)


def get_data(args):
    """
    :param args: parsed command line arguments
    :return: response data in a dict
    """
    params = parse_url_params(args.param)
    url_params = urllib_parse.urlencode(params)
    req = urllib_request.Request(args.url + '?' + url_params)
    req.add_header('User-Agent', USER_AGENT)
    res = urllib_request.urlopen(req)
    res_data = res.read()
    data = json.loads(res_data.decode('utf-8'))
    return data


def main():
    parsed_args = parse_args()
    data = get_data(parsed_args)
    print("META:")
    for k in data['meta'].keys():
        print(k, data['meta'][k])
    print("DATA:")
    for d in data['data']:
        # Find first language version of event's `name`
        for lang in LANGUAGES:
            if lang in d['name']:
                print('{:<20} {} ({})'.format(d['start_time'],
                                              d['name'][lang], lang))
                break

if __name__ == '__main__':
    main()
