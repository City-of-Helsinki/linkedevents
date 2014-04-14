import re
from events.models import Category, CategoryLabel
from difflib import get_close_matches

ENDING_PARENTHESIS_PATTERN = r' \([^)]+\)$'

class CategoryMatcher(object):
    def __init__(self):
        label_to_category_ids = {}
        self.name_to_category_ids = {}
        for label_id, category_id in Category.alt_labels.through.objects.all().values_list(
            'categorylabel_id', 'category_id'):
            label_to_category_ids.setdefault(label_id, set()).add(category_id)
        for label_id, name in CategoryLabel.objects.filter(language_id='fi').values_list(
            'id', 'name'):
            self.name_to_category_ids[name.lower()] = label_to_category_ids.get(label_id, set())
        for cid, preflabel in Category.objects.all().values_list(
            'id', 'name_fi'):
            if preflabel is not None:
                text = preflabel.lower()
                self.name_to_category_ids.setdefault(text, set()).add(cid)
                without_parenthesis = re.sub(ENDING_PARENTHESIS_PATTERN, '', text)
                if without_parenthesis != text:
                    self.name_to_category_ids.setdefault(without_parenthesis, set()).add(cid)
        self.labels = self.name_to_category_ids.keys()
        print('Initialized', len(self.labels), 'keys')

    def match(self, text):
        wordsplit = re.compile(r'\s+')
        #labels = CategoryLabel.objects
        #match = labels.filter(name__iexact=text)

        text = text.lower()
        if text == 'kokous': text = 'kokoukset'
        elif text == 'kuntoilu': text = 'kuntoliikunta'
        elif text == 'samba': text = 'sambat'

        exact_match = lambda x: x.lower() == text
        labels = self.labels
        matches = [l for l in labels if exact_match(l)]
        success = lambda: len(matches) > 0
        if success():
            match_type = 'exact'
        if not success():
            words = wordsplit.split(text)
            if len(words) > 1:
                for word in words:
                    exact_match = lambda x: x.lower() == word
                    matches.extend([l for l in labels if exact_match(l)])
                    if success(): match_type = 'subword'
        if not success():
            matches = [l for l in labels if l.lower().startswith(text)]
            match_type = 'prefix'
        if not success():
            matches = [l for l in labels if l.lower() == text + 't']
            if success(): match_type = 'simple-plural'
        if not success():
            matches = [l for l in labels if l.lower().startswith(text[0:-2])]
            if success(): match_type = 'cut-two-letters'
        if not success():
            if len(text) > 10:
                matches = [l for l in labels if l.lower().startswith(text[0:-5])]
            if success(): match_type = 'prefix'
        if not success():
            for i in range(1, 10):
                matches = [l for l in labels if l.lower() == text[i:]]
                if success():
                    match_type = 'suffix'
                    break

        if not success():
            print('no match', text)
            return None
        if success():
            category_ids = set()
            if match_type not in ['exact', 'subword']:
                cmatch = get_close_matches(
                    text, [m.lower() for m in matches], n=1)
                if len(cmatch) == 1:
                    category_ids = self.name_to_category_ids.get(cmatch[0])

            else:
                for m in matches:
                    category_ids.update(self.name_to_category_ids[m])

            if len(category_ids) < 1:
                print('no matches for', text)
                return None

            objects = Category.objects.filter(id__in=category_ids)
            if len(category_ids) > 1:
                try:
                    aggregate_category = objects.get(aggregate=True)
                    aggregate_name = re.sub(ENDING_PARENTHESIS_PATTERN, '' , aggregate_category.name_fi)
                    result = [aggregate_category]
                    for o in objects.exclude(name_fi__istartswith=aggregate_name):
                        result.append(o)
                    return result
                except Category.DoesNotExist:
                    pass
                return objects
            return objects
