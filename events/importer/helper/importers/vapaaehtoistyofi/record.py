import datetime


class Record:
    STATUS_PUBLISHED = 1
    STATUS_DRAFT = 0
    STATUS = [STATUS_PUBLISHED, STATUS_DRAFT]

    LOCALE_FI = 'fi'
    LOCALE_SE = 'se'
    LOCALE_EN = 'en'
    LOCALE = [LOCALE_FI, LOCALE_SE, LOCALE_EN]

    TASK_URL_FORMAT = 'https://vapaaehtoistyo.fi/%s/task/%s'

    def __init__(self, json_dict):
        self.id = json_dict['id']
        self.organization_id = json_dict['organization']
        self.organization_name = json_dict['organizationName']
        self.title = json_dict['title']
        self.address = json_dict['address']
        self.address_coordinates = {
            'lat': json_dict['addressCoordinates']['lat'],
            'lon': json_dict['addressCoordinates']['lng']
        }
        self.tags = []
        for theme in json_dict['themes']:
            theme_id = theme["id"]
            theme_name = theme["name"]
            self.tags.append({theme_id: theme_name})

        self.timestamp_start = datetime.datetime.utcfromtimestamp(json_dict['timeStampStartTask'])
        self.timestamp_end = datetime.datetime.utcfromtimestamp(json_dict['timeStampEndTask'])
        if json_dict['noActualTime']:
            self.no_time = True
        else:
            self.no_time = False
        self.description = json_dict['description']
        self.contact_details = json_dict['contactDetails']
        self.themes = json_dict['id']
        self.timestamp_publish = datetime.datetime.utcfromtimestamp(json_dict['timeStampPublicationDate'])
        # self.publicationTime = json_dict['id']
        if json_dict['status'] in self.STATUS:
            self.status = json_dict['id']
        else:
            raise RuntimeError("Unknown status %d!" % json_dict['status'])
        self.creator_id = json_dict['creator']
        if json_dict['timeStampAdded']:
            self.timestamp_inserted = datetime.datetime.utcfromtimestamp(json_dict['timeStampAdded'])
        else:
            self.timestamp_inserted = None
        if json_dict['timeStampLastUpdated']:
            self.timestamp_updated = datetime.datetime.utcfromtimestamp(json_dict['timeStampLastUpdated'])
        else:
            self.timestamp_updated = None

    def get_url_locale(self, locale):
        if locale not in self.LOCALE:
            raise ValueError("Unknown locale '%s'!" % locale)
        return self.TASK_URL_FORMAT % (locale, self.id)
