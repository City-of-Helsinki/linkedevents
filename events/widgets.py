from django import forms
from django_filters import widgets as django_filter_widgets


class DistanceWithinWidget(django_filter_widgets.SuffixedMultiWidget):
    suffixes = ["origin", "metres"]

    def __init__(self):
        super().__init__([django_filter_widgets.CSVWidget, forms.NumberInput])
