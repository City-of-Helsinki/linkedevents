import pytest
from django.contrib.gis.geos import Point


@pytest.mark.parametrize(
    "position, is_division_expected",
    [(None, False), (Point(1000, 1000), False), (Point(100, 100), True)],
)
@pytest.mark.django_db
def test_place_divisions_by_position(
    place, position, is_division_expected, administrative_division
):
    place.position = position
    place.save()

    if is_division_expected:
        assert place.divisions.count() == 1
        assert place.divisions.first() == administrative_division
    else:
        assert place.divisions.count() == 0


@pytest.mark.parametrize(
    "division_type, is_division_expected",
    [
        ("district", True),
        ("sub_district", True),
        ("neighborhood", True),
        ("muni", True),
        ("some_other_type", False),
    ],
)
@pytest.mark.django_db
def test_place_divisions_by_division_type(
    place, division_type, is_division_expected, administrative_division
):
    administrative_division.type.type = division_type
    administrative_division.type.save()
    place.save()

    if is_division_expected:
        assert place.divisions.count() == 1
        assert place.divisions.first() == administrative_division
    else:
        assert place.divisions.count() == 0


@pytest.mark.django_db
def test_place_cannot_replace_itself(place):
    place.replaced_by = place
    place.deprecated = True
    with pytest.raises(Exception):
        place.save()


@pytest.mark.django_db
def test_prevent_circular_place_replacement(place, place2, place3):
    place.replaced_by = place2
    place.save()
    place2.replaced_by = place3
    place2.save()
    place3.replaced_by = place
    with pytest.raises(Exception):
        place.save()
