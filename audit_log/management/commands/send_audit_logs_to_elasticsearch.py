from django.conf import settings
from django.core.management import BaseCommand, CommandError
from elasticsearch import Elasticsearch

from audit_log.utils import send_audit_log_entries_to_elasticsearch


class Command(BaseCommand):
    help = "Send all unsent audit log entries to Elasticsearch"

    @staticmethod
    def _elasticsearch_is_properly_configured():
        return (
            settings.ELASTICSEARCH_HOST
            and settings.ELASTICSEARCH_PORT
            and settings.ELASTICSEARCH_APP_AUDIT_LOG_INDEX
            and settings.ELASTICSEARCH_USERNAME
            and settings.ELASTICSEARCH_PASSWORD
        )

    @staticmethod
    def _elasticsearch_client():
        return Elasticsearch(
            [
                {
                    "host": settings.ELASTICSEARCH_HOST,
                    "port": settings.ELASTICSEARCH_PORT,
                    "scheme": "https",
                }
            ],
            http_auth=(
                settings.ELASTICSEARCH_USERNAME,
                settings.ELASTICSEARCH_PASSWORD,
            ),
        )

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            dest="manual",
            help="Manual override - will try to send the log entries even if audit "
            "logging and sending is not enabled in settings.",
        )

    def handle(self, *args, **options):
        if not (
            settings.AUDIT_LOG_ENABLED
            and settings.ENABLE_SEND_AUDIT_LOG
            or options["manual"]
        ):
            self.stdout.write(
                self.style.NOTICE("Audit log sending not enabled in settings")
            )
            return

        if not self._elasticsearch_is_properly_configured():
            raise CommandError(
                "Improperly configured ElasticSearch settings: "
                "host, port, app audit log index, username or password missing"
            )

        client = self._elasticsearch_client()

        sent_entries, total_entries = send_audit_log_entries_to_elasticsearch(client)

        self.stdout.write(
            self.style.SUCCESS(f"Sent {sent_entries} out of {total_entries} entries")
        )
