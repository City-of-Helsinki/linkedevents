from unittest import mock

import pytest

from registrations.pseudonymize import (
    datestring,
    day,
    email,
    integer,
    month,
    name,
    phone,
    street,
    text,
    year,
)

test_secret = "secret"
test_other_secret = "other secret"
test_text = "foobar"
test_other_text = "barfoo"


def test_same_result_for_same_value_and_secret():
    pseudo1 = text(test_text, test_secret)
    pseudo2 = text(test_text, test_secret)
    assert pseudo1 == pseudo2


def test_different_result_for_same_value_and_other_secret():
    pseudo1 = text(test_text, test_secret)
    pseudo2 = text(test_text, test_other_secret)
    assert pseudo1 != pseudo2


def test_different_result_for_different_value_and_same_secret():
    pseudo1 = text(test_text, test_secret)
    pseudo2 = text(test_other_text, test_secret)
    assert pseudo1 != pseudo2


def test_different_result_for_different_value_and_different_secret():
    pseudo1 = text(test_text, test_secret)
    pseudo2 = text(test_other_text, test_other_secret)
    assert pseudo1 != pseudo2


def test_text_pseudonymization_uses_length_of_input():
    assert len(test_text) == len(text(test_text, test_secret))


def test_text_pseudonymization_uses_length_of_input_even_for_longer_texts():
    data = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Mauris rhoncus suscipit arcu et volutpat. Aliquam vitae porttitor ipsum, at dictum dui. ..."
    assert len(data) == len(text(data, "secret"))
    assert (
        "db2d816120ce1bc13ee322fbf51d8e58a8f5a28f291463709e3aa726a742e176bfa1737d22a854beb197b42fa21f0afc3d3c054e6cc6ce17ced81d889a13808ed03a90c4435d30efeb3b"
        == text(data, "secret")
    )


def test_text_pseudonymization_returns_different_results_for_longer_texts():
    data1 = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Mauris rhoncus suscipit arcu et volutpat. Aliquam vitae porttitor ipsum, at dictum dui. ..1"
    data2 = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Mauris rhoncus suscipit arcu et volutpat. Aliquam vitae porttitor ipsum, at dictum dui. ..2"
    assert text(data1, "secret") != text(data2, "secret")


@pytest.mark.parametrize(
    "method", [datestring, day, email, integer, month, name, phone, street, text, year]
)
def test_unchanged_value_is_returned_for_falsy_value(method):
    assert method("", test_secret) == ""
    assert method(None, test_secret) is None


def test_pseudonymize_integer():
    """It returns an integer of the same length."""
    assert integer(4711, test_secret) == 1073


def test_integer_returns_unpseudonymized_value_for_falsy_value():
    assert integer("", test_secret) == ""
    assert integer(None, test_secret) is None


def test_pseudonymize_integer_value_0():
    """It pseudonymizes the value `0`."""
    assert integer(0, test_secret) == 8


def test_pseudonymize_name():
    """It returns pseudonymized text with only first letter a capital one."""
    assert name("Lastname", test_secret) == "B3de5a83"


def test_pseudonymize_street():
    """It returns pseudonymized street name and number."""
    assert street("Street-address 34b", test_secret) == "2bd6d7759bec85 819"


def test_pseudonymize_street_without_number():
    """It omits a not existing number."""
    assert street("Street-address", test_secret) == "2bd6d7759bec85"


def test_pseudonymize_email():
    assert email("test@email.com", test_secret) == "3efe@46ec8b.fi"


def test_pseudonymize_invalid_email():
    """It returns email without `@` if the input does not contain an `@` symbol."""
    assert email("test-email.com", test_secret) == "4483f1343f5592.fi"


def test_pseudonymize_phone_number():
    """It returns a number starting with `0`."""
    assert phone("044 1234567", test_secret) == "0234392410"
    assert phone("+358 44 1234567", test_secret) == "0527260759576"


def test_pseudonymize_short_phone_number():
    """It does not break if the input is very short."""
    assert phone("1", test_secret) == "0"
    assert phone("99", test_secret) == "08"


def test_pseudonymize_day():
    assert day(10, test_secret) == 9


def test_pseudonymize_month():
    assert month(11, test_secret) == 12


def test_pseudonymize_year():
    assert year(1976, test_secret) == 9382


def test_year_is_always_greater_than_1900():
    with mock.patch("hashlib.sha512") as sha512:
        hash_object = mock.Mock()
        hash_object.hexdigest.return_value = "1899"
        sha512.return_value = hash_object

        assert year(1983, test_secret) == 3799


def test_pseudonymize_datestring():
    assert datestring("2022-05-11", test_secret) == "8710-12-24"
    assert datestring("11.05.2022", test_secret, format="DD.MM.YYYY") == "24.12.8710"


def test_datestring_returns_zero_parts_as_zero():
    assert datestring("00002022", test_secret, format="DDMMYYYY") == "00008710"
    assert datestring("20120000", test_secret, format="DDMMYYYY") == "17100000"


def test_datestring_raises_exception_on_invalid_format():
    with pytest.raises(AssertionError):
        datestring("000020", test_secret, format="DDMMYY")
