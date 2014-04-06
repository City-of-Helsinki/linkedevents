import re
from events.models import Category, CategoryLabel
from difflib import get_close_matches

def match_categories(text):
    wordsplit = re.compile(r'\s+')
    labels = CategoryLabel.objects
    match = labels.filter(label__iexact=text)
    success = lambda: match.exists()

    if success():
        match_type = 'exact'
    if not success():
        words = wordsplit.split(text)
        if len(words) > 1:
            for word in words:
                match |= labels.filter(label__iexact=word)
                if success(): match_type = 'subword'
    if not success():
        match = labels.filter(label__iexact=text + 't')
        if success(): match_type = 'simple-plural'
    if not success():
        match = labels.filter(label__istartswith=text[0:-2])
        if success(): match_type = 'cut-two-letters'
    if not success():
        if len(text) > 10:
            match |= labels.filter(label__istartswith=text[0:-5])
        if success(): match_type = 'prefix'
    if not success():
        for i in range(1, 10):
            match |= labels.filter(label__iexact=text[i:])
            if success():
                match_type = 'suffix'
                break
    if success():
        if match_type not in ['exact', 'subword']:
            cmatch = get_close_matches(
                text.lower(),
                [m.label.lower() for m in match], n=1)
            if len(cmatch) == 1:
                return CategoryLabel.objects.get(label__iexact=cmatch[0]).categories.all()
        else:
            return [m.categories.all()[0] for m in match]
    else:
        return None
