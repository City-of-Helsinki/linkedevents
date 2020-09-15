from django import template

register = template.Library()


@register.filter
def html_to_plaintext_linebreaks(html):
    if html:
        return html.replace('<br>', '\n').replace('</p><p>', '\n\n')
    return ''
