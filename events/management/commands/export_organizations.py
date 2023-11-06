from django.core.management.base import BaseCommand
from django_orghierarchy.models import Organization


class Command(BaseCommand):
    help = "Export organization data"

    def add_arguments(self, parser):
        parser.add_argument("filename", help="Export filename")
        parser.add_argument("--delimiter", default=";", help="CSV delimiter")

    def _iterate_tree(self, objects, delimiter, depth=0, max_depth=0):
        tree = []

        for obj in objects:
            children = obj.children.all()

            line = depth * delimiter + f"{obj.name} ({obj.id})"
            tree.append(line)

            if children:
                subtree, max_depth = self._iterate_tree(
                    children, delimiter, depth=depth + 1, max_depth=max_depth
                )
                tree.extend(subtree)

        if max_depth < depth:
            max_depth = depth

        return tree, max_depth

    def make_valid_csv(self, rows, max_depth, delimiter):
        """
        Make sure all lines contain newline characters and the same amount
        of delimiters. Add header.
        """

        header = ""
        for i in range(max_depth + 1):
            header += f"Level {i+1}{delimiter}"

        fixed_rows = [header.rstrip(delimiter) + "\n"]

        for row in rows:
            depth_after_node = max_depth - row.count(delimiter)

            new_row = row + depth_after_node * delimiter + "\n"
            fixed_rows.append(new_row)

        return fixed_rows

    def _write_csv(self, filename, delimiter):
        orgs = Organization.objects.filter(parent__isnull=True)
        rows, max_depth = self._iterate_tree(orgs, delimiter)

        rows = self.make_valid_csv(rows, max_depth, delimiter)

        with open(filename, "w", encoding="utf-8-sig") as csvfile:
            csvfile.writelines(rows)

    def handle(self, *args, **options):
        filename = options["filename"]
        delimiter = options["delimiter"]

        self._write_csv(filename, delimiter)

        self.stdout.write(f"Data written to {filename}")
