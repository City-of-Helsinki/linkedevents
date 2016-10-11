from distutils import dir_util
import json
import os
import pytest

from events.importer.base import recur_dict
from events.importer.espoo import EspooImporter, clean_street_address, clean_url, YSO_KEYWORD_MAPS
from events.models import DataSource, Event, Keyword


URL = "http://www.lippu.fi/Lippuja.html?doc=artistPages%2Ftickets&fun=artist&action=tickets&xtmc=hetki%C3%A4&xtcr=2"
EVENT_FILE = "event_espoo.json"


@pytest.fixture
def datadir(tmpdir, request):
    '''
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely.
    '''
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmpdir))

    return tmpdir


@pytest.fixture
def addresses():
    return {
        'Soittoniekanaukio 1 A': {
            'street_address': 'Soittoniekanaukio 1 A',
            'postal_code': '',
            'address_locality': '',
        },
    }


@pytest.fixture
def data_source():
    defaults = dict(name='City of Espoo')
    ds_args = dict(id='espoo')
    data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)
    defaults = dict(name='TPrek')
    ds_args = dict(id='tprek')
    data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)
    defaults = dict(name='YSO')
    ds_args = dict(id='yso')
    data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)


@pytest.fixture
def yso_keyword():
    for kw, ids in YSO_KEYWORD_MAPS.items():
        if not isinstance(ids, tuple):
            ids = (ids,)
        for id_ in ids:
            kwargs = {
                'id': 'yso:%s' % id_,
                'origin_id': id_,
                'data_source_id': 'yso',
                'name': kw,
            }
            keyword = Keyword(**kwargs)
            keyword.save()


@pytest.mark.django_db
def test_address_is_parsed_correctly(addresses):
    for k, v in addresses.items():
        assert clean_street_address(k) == v


@pytest.mark.django_db
def test_keyword_fetch_from_dict(data_source, yso_keyword):
    importer = EspooImporter({'verbosity': True, 'cached': False})
    importer.setup()
    assert importer._map_classification_keywords_from_dict('Teatteri').pop().id == u'yso:p2625'


@pytest.mark.django_db
def test_clean_url__extract_url_from_tag():
    tag = "<a href=\"%s\" target=\"_blank\">Lippupiste</a>" % URL
    assert clean_url(tag) == URL


@pytest.mark.django_db
def test_clean_url__extract_url_from_tag_single_quote():
    """
    Test that url is correctly from an invalid HTML tag which appears in ESPOO API URL
    """
    tag = "<a href='%s' target='_blank'>Lippupiste</a>" % URL
    assert clean_url(tag) == URL


@pytest.mark.django_db
def test_clean_url__return_url_if_no_tag():
    assert clean_url(URL) == URL


@pytest.mark.django_db
def test_clean_url__return_url_stripped():
    assert clean_url("   %s   " % URL) == URL


@pytest.mark.django_db
def test_keyword_fetch_from_dict(data_source, yso_keyword):
    importer = EspooImporter({'verbosity': True, 'cached': False})
    importer.setup()
    assert 'glimsin tapahtumat' in YSO_KEYWORD_MAPS.keys()
    assert importer._map_classification_keywords_from_dict('glimsin tapahtumat').pop().id == u'yso:p13230'


@pytest.mark.django_db
def test_create_event(data_source, yso_keyword, datadir):
    importer = EspooImporter({'verbosity': True, 'cached': False})
    importer.setup()
    with open(str(datadir.join(EVENT_FILE))) as f:
        reply = json.loads(str(f.read()))
        documents = reply['value']
        events = recur_dict()
        for doc in documents:
            ev = importer._import_event('fi', doc, events)
            importer.save_event(ev)
    assert len(events) == 1
    assert Event.objects.all().count() == 1
    event = Event.objects.first()
    assert event.name == u"Yleis\u00f6opastus KAMUssa: Lasin aika - Kauklahden lasitehdas 1923-1952"
    assert event.name_fi == u"Yleis\u00f6opastus KAMUssa: Lasin aika - Kauklahden lasitehdas 1923-1952"
    assert event.custom_data['ExternalVideoLink'] == u"http://www.video.com"
    assert event.custom_data['PrimaryPhoneNumber'] == u"+358981657052"
    assert event.location_extra_info == u"Espoon kaupunginmuseo KAMU, N\u00e4yttelykeskus WeeGee"
    assert event.location_id
    keywords = Keyword.objects.filter(event__id=event.id)
    assert len(keywords) == 24
