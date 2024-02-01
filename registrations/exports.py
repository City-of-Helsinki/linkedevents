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
        self.signups = (
            registration.signups.all()
            .select_related("contact_person", "signup_group__contact_person")
            .order_by("first_name", "last_name")
            .only(
                "first_name",
                "last_name",
                "phone_number",
                "attendee_status",
                "contact_person",
                "signup_group",
            )
        )
        self.columns = self._get_columns()
        self.formats = {}

    @staticmethod
    def _get_columns() -> list[dict]:
        return [
            {"header": _("Name"), "accessor": "full_name"},
            {"header": _("Phone number"), "accessor": "phone_number"},
            {
                "header": _("Contact person's email"),
                "accessor": lambda signup: signup.actual_contact_person.email
                if signup.actual_contact_person
                else None,
            },
            {
                "header": _("Contact person's phone number"),
                "accessor": lambda signup: signup.actual_contact_person.phone_number
                if signup.actual_contact_person
                else None,
            },
            {
                "header": "Status",  # In the UI, this same word is used for all three languages
                "accessor": lambda signup: str(signup.get_attendee_status_display()),
            },
        ]

    @staticmethod
    def _add_info_texts(worksheet: Worksheet, row: int = 1) -> None:
        worksheet.write(
            row,
            0,
            _(
                "This material is subject to data protection. This material must be processed "
                "in the manner required by data protection and only to verify \nthe participants "
                "of the event. This list should be discarded when the event is over and the "
                "attendees have been entered into the system."
            ),
        )
        worksheet.set_row(row, 40)

        worksheet.write(
            row + 1,
            0,
            _(
                "Please note that the participant and the participant's contact information "
                "may be the information of different persons."
            ),
        )
        worksheet.set_row(row + 1, 20)

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

    def _add_signups_table(self, worksheet: Worksheet, row: int = 4) -> None:
        table_columns = self._get_signups_table_columns()
        table_data = self._get_signups_table_data()

        worksheet.add_table(
            row,
            0,
            row + len(table_data),
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
            self._add_signups_table(worksheet, 6)

            # Automatically try to adjust signup table column widths to make values visible in the columns.
            worksheet.autofit()

            # Add info texts about data protection and contact information.
            self._add_info_texts(worksheet, 2)

        return output.getvalue()
