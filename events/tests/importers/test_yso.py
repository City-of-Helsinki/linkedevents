from events.importer.yso import YsoImporter
from linkedevents import __version__


def test_load_graph_into_memory_sends_user_agent(requests_mock, settings):
    settings.OUTBOUND_USER_AGENT = f"Test/{__version__}"
    url = "http://localhost/yso"
    requests_mock.get(
        url,
        text="<http://example.org/subject> <http://example.org/predicate> "
        "<http://example.org/object> .",
    )

    importer = YsoImporter.__new__(YsoImporter)
    importer.load_graph_into_memory(url)

    assert (
        requests_mock.request_history[0].headers["User-Agent"] == f"Test/{__version__}"
    )
