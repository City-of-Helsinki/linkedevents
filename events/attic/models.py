class Person(BaseModel):
    description = models.TextField(blank=True)
    family_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    creator = models.ForeignKey('self', null=True, blank=True,
                                related_name='person_creators')
    editor = models.ForeignKey('self', null=True, blank=True,
                               related_name='person_editors')
    # Custom fields
    member_of = models.ForeignKey('Organization', null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True)

    class Meta:
        verbose_name = _('person')
        verbose_name_plural = _('persons')

reversion.register(Person)


class Organization(BaseModel):
    description = models.TextField(blank=True)
    base_IRI = models.CharField(max_length=200, null=True, blank=True)
    compact_IRI_name = models.CharField(max_length=200, null=True, blank=True)
    creator = models.ForeignKey(Person, null=True, blank=True,
                                related_name='organization_creators')
    editor = models.ForeignKey(Person, null=True, blank=True,
                               related_name='organization_editors')

    class Meta:
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')


reversion.register(Organization)
