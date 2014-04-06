class OrganizationOrPersonRelatedField(serializers.RelatedField):
    def __init__(self, hide_ld_context=False):
        self.hide_ld_context = hide_ld_context
        super(OrganizationOrPersonRelatedField, self).__init__(
            queryset=Organization.objects, read_only=False)

    def to_native(self, value):
        if isinstance(value, Organization):
            serializer = OrganizationSerializer(
                value, hide_ld_context=self.hide_ld_context)
        elif isinstance(value, Person):
            serializer = PersonSerializer(value,
                                          hide_ld_context=self.hide_ld_context)
        else:
            raise Exception('Unexpected type of related object')

        return serializer.data

    def from_native(self, data):
        """
        TODO: fix, this is just a skeleton. We should save and fetch right
        content_type (and content_id) to parent.
        """
        if data["@type"] == 'Organization':
            pass  # Organization is the default queryset
        elif data["@type"] == 'Person':
            self.queryset = Person.objects
        else:
            raise ValidationError('Unexpected type of related object')

        super(OrganizationOrPersonRelatedField, self).from_native(data)


class PersonSerializer(LinkedEventsSerializer):
    # Fallback to URL references to get around of circular serializer problem
    creator = JSONLDHyperLinkedRelatedField(view_name='person-detail')
    editor = JSONLDHyperLinkedRelatedField(view_name='person-detail')

    view_name = 'person-detail'

    class Meta:
        model = Person


class OrganizationSerializer(LinkedEventsSerializer):
    creator = PersonSerializer(hide_ld_context=True)
    editor = PersonSerializer(hide_ld_context=True)

    view_name = 'organization-detail'

    class Meta:
        model = Organization
