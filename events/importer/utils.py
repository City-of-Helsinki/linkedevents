import logging
import re

from bs4 import BeautifulSoup
from django.core.validators import URLValidator, ValidationError
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from events.models import Place

logger = logging.getLogger(__name__)


def clean_text(text, strip_newlines=False, parse_html=False):
    if parse_html:
        soup = BeautifulSoup(text, features="html.parser")
        text = soup.get_text()
    # remove non-breaking spaces and separators
    text = text.replace("\xa0", " ").replace("\x1f", "")
    # remove nil bytes and tabs
    text = text.replace("\u0000", " ").replace("\u200b", " ").replace("\t", " ")
    if strip_newlines:
        text = text.replace("\r", " ").replace("\n", " ")
    # remove consecutive whitespaces
    return re.sub(r"\s\s+", " ", text, flags=re.UNICODE).strip()


def clean_url(url):
    """
    Takes in a string and returns it as a cleaned url, or empty if the string is not a valid URL.
    """  # noqa: E501
    url = clean_text(url, True)
    url = url.replace(" ", "%20")
    if not re.match(r"^\w+?://", url):
        url = "http://" + url
    try:
        URLValidator()(url)
        return url
    except ValidationError:
        logger.warning("URL not valid: " + url)
        return None


def separate_scripts(text, scripts):
    """
    Takes in a string and an iterable of language tags and returns an array of string paragraphs
    separated by language. The first language in scripts is the default. The paragraphs may be either
    html (separated by <p> or triple <br><br><br> tags) or text (separated by \n or dash).

    :param text: The plain text or html to separate paragraphs in by language.
    :param scripts: Iterable of allowed languages.
    :return:
    """  # noqa: E501
    # separate the text by paragraphs, matching to select html and plain text
    # delimiters in data
    paragraphs = re.split(r"(</p><p>|\n|</p>|<p>| – |<br><br><br>)+", text)
    separated = {script: "" for script in scripts}
    # the first language given is the default one
    last_language = scripts[0]
    last_paragraph = ""
    for paragraph in paragraphs:
        if paragraph in (r"</p><p>", r"</p>" r"\n", r"<p>", r"<br><br><br>"):
            # skip paragraph breaks to prevent misdetection
            separated[last_language] += paragraph
            last_paragraph = paragraph
            continue
        # replace any misleading tags left
        paragraph_stripped = re.sub(
            r'(<(/)?strong>)|(<br>)+|&amp;|<a href=.*">|</a>', " ", paragraph
        )
        try:
            language = detect(paragraph_stripped)
        except LangDetectException:
            # an exception means no language could be detected
            language = last_language
        # langdetect maps "Simplified Chinese" to "zh-cn"
        # However, we store it as "zh_hans"
        if language == "zh-cn":
            language = "zh_hans"
        if language not in scripts:
            # only detect allowed languages, no exceptions
            language = last_language
        if language != last_language:
            # fix html paragraph breaks after language change
            if last_paragraph in (r"</p><p>", r"</p>", r"<p>"):
                separated[last_language] = re.sub(r"<p>$", "", separated[last_language])
                separated[language] += r"<p>"
            # remove useless dashes after language change
            if last_paragraph in (r" – ",):
                separated[last_language] = re.sub(r" – $", "", separated[last_language])
            # replace the awful triple-<br>
            if last_paragraph in (r"<br><br><br>",):
                separated[last_language] = re.sub(
                    r"<br><br><br>$", "", separated[last_language]
                )
                separated[last_language] += r"</p>"
                separated[language] += r"<p>"
        separated[language] += paragraph
        last_language = language
        last_paragraph = paragraph
    return separated


def unicodetext(item):
    if item is None or item.text is None:
        return None
    return clean_text(item.text, strip_newlines=True)


def reduced_text(text):
    return re.sub(r"\W", "", text, flags=re.UNICODE).lower()


def text_match(a, b):
    return reduced_text(a) == reduced_text(b)


def address_eq(a, b):
    if (
        "postal_code" in a
        and "postal_code" in b
        and a["postal_code"] != b["postal_code"]
    ):
        return False
    for key in ["locality", "street_address"]:
        languages = a[key].viewkeys() | b[key].viewkeys()
        for lang in languages:
            if (
                lang in a[key]
                and lang in b[key]
                and not text_match(a[key][lang], b[key][lang])
            ):
                return False
    return True


def replace_location(
    replace=None, from_source="tprek", by=None, by_source="matko", include_deleted=False
):
    """
    Takes two locations from different data sources and replaces one by the other. If one or the other is
    not provided, the other is found by the name of the other and the specified data source.

    :param replace: The location to be replaced
    :param from_datasource: The data source to look for the location to be replaced
    :param by: The location to replace by
    :param by_datasource: The data source to look for the location to replace by
    :param include_deleted: Include deleted locations when looking for replacements
    :return: Boolean that determines whether a new location was found for the hapless events
    """  # noqa: E501
    if not by:
        replacements = Place.objects.filter(
            name__iexact=replace.name, data_source=by_source, deleted=False
        )
        if replacements.count() == 1:
            by = replacements[0]
        else:
            # the backup is to look for deleted locations and reinstate them
            if include_deleted:
                replacements = Place.objects.filter(
                    name__iexact=replace.name, data_source=by_source
                )
                if replacements.count() == 1:
                    by = replacements[0]
                else:
                    # no replacement whatsoever was found, this may result in an
                    # exception
                    return False
            else:
                return False
    if not replace:
        to_be_replaced = Place.objects.filter(
            name__iexact=by.name, data_source=from_source
        )
        if to_be_replaced.count() == 1:
            replace = to_be_replaced[0]
        # if no place to be replaced was found, it's alright, we might have a
        # brand new location here!
    by.deleted = False
    by.replaced_by = None
    by.save(update_fields=["deleted", "replaced_by"])
    if replace:
        replace.deleted = True
        replace.replaced_by = by
        replace.save(update_fields=["deleted", "replaced_by"])
        logger.info(
            "Location %s (%s) was deleted. Discovered replacement location %s"
            % (replace.id, str(replace), by.id)
        )
    return True
