import re
from events.models import Keyword, KeywordLabel, DataSource
from difflib import get_close_matches

ENDING_PARENTHESIS_PATTERN = r' \([^)]+\)$'


class KeywordMatcher(object):
    def __init__(self):
        label_to_keyword_ids = {}
        self.name_to_keyword_ids = {}
        for label_id, keyword_id in Keyword.alt_labels.through.objects.all().values_list(
                'keywordlabel_id', 'keyword_id'):
            label_to_keyword_ids.setdefault(label_id, set()).add(keyword_id)
        for label_id, name in KeywordLabel.objects.filter(language_id='fi').values_list(
                'id', 'name'):
            self.name_to_keyword_ids[name.lower()] = label_to_keyword_ids.get(label_id, set())
        try:
            yso_source = DataSource.objects.get(pk='yso')
            self.skip = False
        except DataSource.DoesNotExist:
            print('No YSO keyword data source')
            self.skip = True
            return
        for kid, preflabel in Keyword.objects.filter(data_source=yso_source).values_list(
                'id', 'name_fi'):
            if preflabel is not None:
                text = preflabel.lower()
                self.name_to_keyword_ids.setdefault(text, set()).add(kid)
                without_parenthesis = re.sub(ENDING_PARENTHESIS_PATTERN, '', text)
                if without_parenthesis != text:
                    self.name_to_keyword_ids.setdefault(without_parenthesis, set()).add(kid)
        self.labels = self.name_to_keyword_ids.keys()
        print('Initialized', len(self.labels), 'keyword keys')

    def match(self, text):
        if self.skip:
            return None
        wordsplit = re.compile(r'\s+')
        # labels = KeywordLabel.objects
        # match = labels.filter(name__iexact=text)

        text = text.lower()
        if text == 'kokous':
            text = 'kokoukset'
        elif text == 'kuntoilu':
            text = 'kuntoliikunta'
        elif text == 'samba':
            text = 'sambat'

        labels = self.labels
        matches = [l for l in labels if l.lower() == text]
        if matches:
            match_type = 'exact'
        if not matches:
            words = wordsplit.split(text)
            if len(words) > 1:
                for word in words:
                    matches.extend([l for l in labels if l.lower() == word])
                    match_type = 'subword'  # Later attempts will override, if this wasn't a match
        if not matches:
            matches = [l for l in labels if l.lower().startswith(text)]
            match_type = 'prefix'
        if not matches:
            matches = [l for l in labels if l.lower() == text + 't']
            match_type = 'simple-plural'
        if not matches:
            matches = [l for l in labels if l.lower().startswith(text[0:-2])]
            match_type = 'cut-two-letters'
        if not matches:
            if len(text) > 10:
                matches = [l for l in labels if l.lower().startswith(text[0:-5])]
                match_type = 'prefix'
        if not matches:
            for i in range(1, 10):
                matches = [l for l in labels if l.lower() == text[i:]]
                if matches:
                    match_type = 'suffix'
                    break

        if not matches:
            print('no match', text)
            return None

        keyword_ids = set()
        if match_type not in ['exact', 'subword']:
            cmatch = get_close_matches(
                text, [m.lower() for m in matches], n=1)
            if len(cmatch) == 1:
                keyword_ids = self.name_to_keyword_ids.get(cmatch[0])

        else:
            for m in matches:
                keyword_ids.update(self.name_to_keyword_ids[m])

        if len(keyword_ids) < 1:
            print('no matches for', text)
            return None

        objects = Keyword.objects.filter(id__in=keyword_ids, deprecated=False)
        if len(keyword_ids) > 1:
            try:
                aggregate_keyword = objects.get(aggregate=True)
                aggregate_name = re.sub(ENDING_PARENTHESIS_PATTERN, '', aggregate_keyword.name_fi)
                result = [aggregate_keyword]
                for o in objects.exclude(name_fi__istartswith=aggregate_name):
                    result.append(o)
                return result
            except Keyword.DoesNotExist:
                pass
            return objects
        return objects
