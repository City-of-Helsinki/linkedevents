import pytest
from django.core.management.base import CommandError

from events.exporter.base import Exporter, exporters, register_exporter
from events.management.commands.event_export import Command


@pytest.fixture(autouse=True)
def cleanup_exporters():
    """Clear exporters before each test to ensure test isolation."""
    original_exporters = exporters.copy()
    exporters.clear()
    yield
    exporters.clear()
    exporters.update(original_exporters)


class TestEventExportCommandInitialization:
    """Test command initialization and configuration."""

    def test_command_has_expected_attributes(self):
        """Test that command initializes with expected attributes."""

        @register_exporter
        class TestExporter(Exporter):
            name = "working_exporter"

        cmd = Command()
        assert cmd.help == "Export event data"
        assert cmd.exporter_types == ["events"]
        assert "working_exporter" in cmd.exporters
        assert "working_exporter" in cmd.exp_list
        assert "Valid exporters:" in cmd.missing_args_message


class TestEventExportCommandValidation:
    """Test module validation and error handling."""

    def test_handle_raises_error_for_invalid_module(self):
        """Test that invalid module name raises CommandError."""

        @register_exporter
        class TestExporter(Exporter):
            name = "registered_exporter"

        cmd = Command()
        with pytest.raises(CommandError) as exc_info:
            cmd.handle(module="invalid", new=False, delete=False, events=False)

        assert "not found" in str(exc_info.value)
        assert "registered_exporter" in str(exc_info.value)

    def test_handle_raises_error_when_method_not_supported(self):
        """Test error when exporter doesn't support requested export type."""

        @register_exporter
        class MinimalExporter(Exporter):
            name = "minimal_exporter"
            # No export_events method

        cmd = Command()
        with pytest.raises(CommandError) as exc_info:
            cmd.handle(module="minimal_exporter", new=True, delete=False, events=True)

        assert "does not support" in str(exc_info.value)


class TestEventExportCommandExecution:
    """Test export execution logic."""

    def test_handle_calls_export_method(self):
        """Test that export method is called with correct parameters."""
        export_calls = []

        @register_exporter
        class TestExporter(Exporter):
            name = "test"

            def export_events(self, is_delete=False):
                export_calls.append({"is_delete": is_delete})

        cmd = Command()
        cmd.handle(module="test", new=True, delete=False, events=True)

        assert len(export_calls) == 1, "export_events should be called once"
        assert export_calls[0]["is_delete"] is False, (
            "is_delete should be False when delete flag is not set"
        )

    def test_handle_passes_delete_flag_to_export(self):
        """Test that delete flag is passed to export method."""
        export_calls = []

        @register_exporter
        class TestExporter(Exporter):
            name = "test"

            def export_events(self, is_delete=False):
                export_calls.append(is_delete)

        cmd = Command()
        cmd.handle(module="test", new=True, delete=True, events=True)

        assert export_calls[0] is True, (
            "is_delete should be True when delete flag is set"
        )

    def test_handle_skips_export_when_flag_false(self):
        """Test that export is skipped when type flag is False."""
        export_calls = []

        @register_exporter
        class TestExporter(Exporter):
            name = "test"

            def export_events(self, is_delete=False):
                export_calls.append(True)

        cmd = Command()
        cmd.handle(module="test", new=False, delete=False, events=False)

        assert len(export_calls) == 0, (
            "export_events should not be called when all flags are False"
        )

    def test_handle_runs_export_with_new_flag(self):
        """Test that export runs when --new flag is set."""
        export_calls = []

        @register_exporter
        class TestExporter(Exporter):
            name = "test"

            def export_events(self, is_delete=False):
                export_calls.append(True)

        cmd = Command()
        cmd.handle(module="test", new=True, delete=False, events=False)

        assert len(export_calls) == 1, (
            "export_events should be called when --new flag is set"
        )


class TestEventExportShouldRunLogic:
    """Test the _should_run_export decision logic."""

    def test_should_run_export_with_type_flag(self):
        """Test that export runs when type-specific flag is True."""
        cmd = Command()
        assert (
            cmd._should_run_export(
                {"events": True, "new": False, "delete": False}, "events"
            )
            is True
        ), "Should run export when type-specific flag is True"

    def test_should_run_export_with_new_flag(self):
        """Test that export runs when --new flag is set."""
        cmd = Command()
        assert (
            cmd._should_run_export(
                {"events": False, "new": True, "delete": False}, "events"
            )
            is True
        ), "Should run export when --new flag is set"

    def test_should_run_export_with_delete_flag(self):
        """Test that export runs when --delete flag is set."""
        cmd = Command()
        assert (
            cmd._should_run_export(
                {"events": False, "new": False, "delete": True}, "events"
            )
            is True
        ), "Should run export when --delete flag is set"

    def test_should_not_run_export_when_all_false(self):
        """Test that export doesn't run when all flags are False."""
        cmd = Command()
        assert (
            cmd._should_run_export(
                {"events": False, "new": False, "delete": False}, "events"
            )
            is False
        ), "Should not run export when all flags are False"
