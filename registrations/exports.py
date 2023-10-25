import io

from django.utils.translation import gettext as _
from xlsxwriter import Workbook
from xlsxwriter.worksheet import Worksheet

from registrations.models import Registration


class RegistrationSignUpsExportXLSX:
    def __init__(self, registration: Registration) -> None:
        self.worksheet_header = "{event_name} - {registered_persons}".format(
            event_name=registration.event.name,
            registered_persons=_("Registered persons"),
        )
        self.signups = registration.signups.all().only(
            "first_name", "last_name", "email", "phone_number", "attendee_status"
        )
        self.columns = self._get_columns()
        self.formats = {}

    @staticmethod
    def _get_columns() -> list[dict]:
        return [
            {"header": _("Name"), "accessor": "full_name"},
            {"header": _("E-mail"), "accessor": "email"},
            {"header": _("Phone number"), "accessor": "phone_number"},
            {
                "header": "Status",  # In the UI, this same word is used for all three languages
                "accessor": lambda signup: str(signup.get_attendee_status_display()),
            },
        ]

    def _get_signups_table_columns(self) -> list[dict]:
        table_columns = [{"header": column["header"]} for column in self.columns]

        return table_columns

    def _get_signups_table_data(self) -> list[list]:
        table_data = []

        for signup in self.signups:
            signup_data = []

            for column in self.columns:
                if callable(column["accessor"]):
                    col_value = column["accessor"](signup)
                else:
                    col_value = getattr(signup, column["accessor"], None)

                signup_data.append(col_value or "-")

            table_data.append(signup_data)

        return table_data

    def _add_signups_table(self, worksheet: Worksheet) -> None:
        table_columns = self._get_signups_table_columns()
        table_data = self._get_signups_table_data()

        worksheet.add_table(
            2,
            0,
            2 + len(table_data),
            len(self.columns) - 1,
            {
                "columns": table_columns,
                "data": table_data,
            },
        )

    def get_xlsx(self) -> bytes:
        output = io.BytesIO()

        with Workbook(output, {"in_memory": True}) as workbook:
            # Add "bold" formatting.
            self.formats["bold"] = workbook.add_format({"bold": True})

            # Add a worksheet.
            worksheet = workbook.add_worksheet()

            # Add the worksheet's title to the beginning of the worksheet.
            worksheet.write(0, 0, self.worksheet_header, self.formats["bold"])

            # Add a table containing the signups' data.
            self._add_signups_table(worksheet)

            # Automatically try to adjust column widths to make values visible in the columns.
            worksheet.autofit()

        return output.getvalue()
