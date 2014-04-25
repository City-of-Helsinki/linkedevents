from rest_framework.reverse import reverse
from rest_framework.routers import DefaultRouter
from rest_framework.response import Response
from rest_framework import views

class DocumentedRouter(DefaultRouter):
    # The following method overrides the DefaultRouter method with the
    # only difference being the view class name and docstring, which
    # are shown on the API front page.
    def get_api_root_view(self):
        """
        Return a view to use as the API root.
        """
        api_root_dict = {}
        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        class LinkedEvents(views.APIView):
            """Linked Events provides categorized data on events and places for the
            Helsinki capital region. The API contains data from the [Helsinki City
            Tourist & Convention Bureau](http://www.visithelsinki.fi/ "Visit Helsinki"),
            the [City of Helsinki Cultural Office](http://www.hel.fi/hki/Kulke/ "Kulke")
            and the [Helmet metropolitan area public libraries](http://www.helmet.fi/).

            The location information is linked to the City of Helsinki registry of
            service units which contains e.g. information about accessibility.

            In the API, you can search data by date or location as
            well as city neighborhoods.

            The API provides data in JSON and JSON-LD format. The data
            is modeled after [schema.org/Event](http://www.schema.org/Event) and
            [schema.org/CreativeWork](http://www.schema.org/CreativeWork).

            *The API is in beta phase. To help improve the API, please don’t
            hesitate to comment, give feedback or make suggestions on
            the [Linked Events API discussion forum](http://dev.hel.fi/forum/linkedevents)*

            # Usage

            [See below for examples and a browsable API.](#usage-instructions "Usage")

            # License

            The use of the data is free under the following license.

            ## Linked Events – tietoaineistojen lisenssi

            Tällä lisenssillä lisenssinantaja (lisensoidun aineiston tekijän- tai
            lähioikeuksien haltija) antaa lisenssinsaajalle (lisensoitua aineistoa
            tämän lisenssin mukaisesti käyttävä) kohdissa 2 ja 3 mainituin ehdoin
            maailmanlaajuisen, maksuttoman, ei-yksinomaisen ja pysyvän luvan
            kopioida, levittää, muokata, yhdistellä sekä muutoin käyttää
            lisensoitua aineistoa. Lisensoitua aineistoa voi käyttää sekä
            ei-kaupallisiin että kaupallisiin tarkoituksiin.

            Lisensoidun aineiston alkuperäiset tekijänoikeustiedot on ilmoitettava
            lisenssinantajan ilmoittamalla tavalla. Lisenssinantajan pyynnöstä
            tämä viittaus on poistettava.  Lisensoidun aineiston
            tekijäoikeustietoja ei saa ilmoittaa siten, että ilmoitus viittaisi
            lisensoidun aineiston tekijän millään tavoin tukevan lisensoidun
            aineiston käyttäjää tai aineiston käyttötapaa.

            ## Linked Events – data pool licence

            The licensor (holder of copyright or associated rights in the licensed
            material) hereby grants the licensee (user of the licensed material
            under the terms of this licence) a global, free of charge,
            non-exclusive, permanent licence to copy, disseminate, edit, combine
            and otherwise use the licensed material according to the terms and
            conditions set out in items 2 and 3 below. The licensed material may
            be used for non-commercial and commercial purposes.  The original
            copyright information in the licensed material must be acknowledged in
            the manner indicated by the licensor. This attribution must be deleted
            if so requested by the licensor.

            The copyright details of the licensed material must not be attributed
            in any way that suggests that the publisher of the licensed material
            endorses the user or the use of the data material.

            ## Licens för datamaterial i Linked Events

            Med denna licens ger licensgivaren (innehavaren av upphovs- eller de
            närstående rätterna till det licensierade materialet) licenstagaren
            (den som använder det licensierade materialet enligt denna licens)
            tillstånd att enligt villkoren i punkt 2 och 3 globalt, avgiftsfritt,
            permanent och utan ensamrätt kopiera, sprida, redigera, förena och på
            annat sätt använda det licensierade materialet. Det licensierade
            materialet får användas i både icke-kommersiellt och kommersiellt
            syfte.

            De ursprungliga upphovsrätterna till det licensierade materialet ska
            uppges på det sätt som licensgivaren anger. På licensgivarens begäran
            ska denna referens avlägsnas.

            Uppgifter om upphovsrätterna till det licensierade materialet får inte
            anges på ett sådant sätt att angivelsen kan tolkas som att
            upphovsmannen till det licensierade materialet på något sätt stödjer
            användaren av det licensierade materialet eller det sätt på vilket
            materialet används.

            # Usage instructions

            Use the browsable version of the API at the bottom of this
            page to explore the data in your browser.

            Events are the main focus point of this API. Click on the event
            link below to see the documentation for events.

            # Browsable API

            """
            _ignore_model_permissions = True

            def get(self, request, format=None):
                ret = {}
                for key, url_name in api_root_dict.items():
                    ret[key] = reverse(url_name, request=request, format=format)
                return Response(ret)

        return LinkedEvents.as_view()
