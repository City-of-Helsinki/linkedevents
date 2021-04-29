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
        if json_dict:
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
        else:
            self.id = None
            self.organization_id = None
            self.organization_name = None
            self.title = None
            self.address = None
            self.address_coordinates = None
            self.tags = []

            self.no_time = None
            self.timestamp_start = None
            self.timestamp_end = None

            self.description = None
            self.contact_details = None
            self.themes = None
            self.timestamp_publish = None

            self.status = None
            self.creator_id = None
            self.timestamp_inserted = None
            self.timestamp_updated = None

    def get_url_locale(self, locale):
        if locale not in self.LOCALE:
            raise ValueError("Unknown locale '%s'!" % locale)
        return self.TASK_URL_FORMAT % (locale, self.id)

    def __copy__(self) -> object:
        newrecord = Record(None)
        newrecord.id = self.id
        newrecord.organization_id = self.organization_id
        newrecord.organization_name = self.organization_name
        newrecord.title = self.title
        newrecord.address = self.address
        newrecord.address_coordinates = self.address_coordinates
        newrecord.tags = self.tags

        newrecord.no_time = self.no_time
        newrecord.timestamp_start = self.timestamp_start
        newrecord.timestamp_end = self.timestamp_end

        newrecord.description = self.description
        newrecord.contact_details = self.contact_details
        newrecord.themes = self.themes
        newrecord.timestamp_publish = self.timestamp_publish

        newrecord.status = self.status
        newrecord.creator_id = self.creator_id
        newrecord.timestamp_inserted = self.timestamp_inserted
        newrecord.timestamp_updated = self.timestamp_updated

        return newrecord

    def to_dict(self):
        newrecord = {
            "id": self.id,
            "organization_id": self.organization_id,
            "organization_name": self.organization_name,
            "title": self.title,
            "address": self.address,
            "address_coordinates": self.address_coordinates,

            "no_time": self.no_time,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,

            "description": self.description,
            "contact_details": self.contact_details,
            "themes": self.themes,
            "timestamp_publish": self.timestamp_publish,

            "status": self.status,
            "creator_id": self.creator_id,
            "timestamp_inserted": self.timestamp_inserted,
            "timestamp_updated": self.timestamp_updated
        }

        return newrecord
