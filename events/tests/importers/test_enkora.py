import json
from datetime import datetime
from unittest.mock import patch

import pytest
import pytz
from django.core import serializers
from django.utils import timezone

from events.importer.enkora import EnkoraImporter
from events.models import Event


class TestEnkoraImporter:
    @pytest.mark.no_test_audit_log
    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "test_input_descriptions,expected_ages",
        [
            ("Äijäjumppa", (None, None)),
            ("Aikuisten tekniikka uimakoulu", (None, None)),
            ("Aikuisten tekniikkauimakoulu", (None, None)),
            ("ALKEET 5-6 -VUOTIAAT", (5, 6)),
            ("ALKEET 5-6-VUOTIAAT", (5, 6)),
            ("ALKEET yli 7 -vuotiaat", (7, None)),
            ("ALKEET YLI 7-vuotiaat", (7, None)),
            ("ALKEET, 5-6 -vuotiaat", (5, 6)),
            ("ALKEET, naiset", (None, None)),
            ("ALKEET, työikäiset", (None, None)),
            ("ALKEET, yli 7 -vuotiaat", (7, None)),
            ("Alkeisjatko uimakoulu, työikäiset", (None, None)),
            ("Alkeisjatko, työikäiset", (None, None)),
            ("Alkeisjatkouimakoulu N, työikäiset", (None, None)),
            ("Alkeisuimakoulu, työikäiset N+M", (None, None)),
            ("AquaPolo -kurssi M + N", (None, None)),
            ("AquaPoLo -kurssi Naiset", (None, None)),
            ("Balans och styrketräning D + H", (None, None)),
            ("Balansgång D + H", (None, None)),
            ("Circuit", (None, None)),
            ("Core ja kehonhuolto", (None, None)),
            ("Dancemix", (None, None)),
            ("Easy Hockey", (None, None)),
            ("EasySport jääkiekko", (None, None)),
            ("EasySport luistelu", (None, None)),
            ("EasySport -luistelukoulu 1. - 3. lk.", (7, 10)),
            ("EasySport -mailapelit 1. - 4. lk.", (7, 11)),
            ("EasySport -mailapelit 1. - 6. lk.", (7, 13)),
            ("EasySport -mailapelit 3. - 6. lk.", (9, 13)),
            ("EasySport -mailapelit 5. - 6. lk.", (11, 13)),
            ("EASYSPORT MELONKURSSI 12-15 -vuotiaat", (12, 15)),
            ("EASYSPORT MELONKURSSI 9-12 -vuotiaat", (9, 12)),
            ("EASYSPORT MELONTA 10-13 -vuotiaat", (10, 13)),
            ("EASYSPORT MELONTA 12-15 -vuotiaat", (12, 15)),
            ("EASYSPORT MELONTA 13-15 -vuotiaat", (13, 15)),
            ("EASYSPORT MELONTA 9-12 -vuotiaat", (9, 12)),
            ("EASYSPORT PADEL-MAILAPELIKURSSI 10-13 -vuotiaat", (10, 13)),
            ("EasySport -Parkour, akrobatia ja sirkuslajit", (None, None)),
            ("EasySport -sirkus", (None, None)),
            ("EasySport -sulkapallo &  squash 3. - 4. lk.", (9, 11)),
            ("EasySport -sulkapallo & squash 5. - 6. lk.", (11, 13)),
            ("EasySport -sulkapallo ja squash 3. - 4. lk.", (9, 11)),
            ("EasySport -sulkapallo ja squash 5. - 6. lk.", (11, 13)),
            ("EasySport -tanssi 1. - 6. lk.", (7, 13)),
            ("EasySport -tanssi 1. - 6. lk. (Break dance)", (7, 13)),
            ("EasySport -tanssi 1. - 6. lk. (Hip Hop, opetuskieli englanti)", (7, 13)),
            ("EasySport -tanssi 1. - 6. lk. (Showtanssi)", (7, 13)),
            ("EasySport Temppu ja tramppa", (None, None)),
            ("EASYSPORT TENNIS, ALKEET 10-12 -vuotiaat", (10, 12)),
            ("EASYSPORT TENNIS, ALKEET yli 10 -vuotiaat", (10, None)),
            ("EASYSPORT TENNIS, ALKEET,  7-9 -vuotiaat", (7, 9)),
            ("EASYSPORT TENNIS, ALKEET, yli 10 -vuotiaat", (10, None)),
            ("EASYSPORT YLEISURHEILUKOULU, 7-14 -vuotiaat", (7, 14)),
            ("ERITYISLASTEN UIMAKOULU ALKEET YLI 6 -VUOTIAAT", (6, None)),
            ("ERITYISLASTEN UIMAKOULU JATKO YLI 6 -VUOTIAAT", (6, None)),
            ("ERITYISLASTEN UIMAKOULU, ALKEET, yli 7 -vuotiaat", (7, None)),
            ("Erityislasten vesiliikunta", (None, None)),
            ("Erityislasten vesiliikunta 10-16 -vuotiaat", (10, 16)),
            ("Erityislasten vesiliikunta 6-9 -vuotiaat", (6, 9)),
            ("Erityislasten vesiseikkailu", (None, None)),
            ("Foam roller", (None, None)),
            ("Foam roller & kehonhuolto", (None, None)),
            ("Fortsättningssimskola på svenska för nybörjare, 5-6 år", (5, 6)),
            ("Hallivesijumppa", (None, None)),
            ("Hyvänolonjumppa", (None, None)),
            ("Hyväolo", (None, None)),
            ("Itsenäinen harjoittelu kuntosalissa ja uima-altaassa N+M", (None, None)),
            ("Itsenäinen kuntosaliharjoittelu /Aktiivix", (None, None)),
            ("Jääkiekko", (None, None)),
            ("JATKO", (None, None)),
            ("JATKO 1", (None, None)),
            ("Jatko 1 (10m uimataito vaaditaan)", (None, None)),
            ("JATKO 1, YLI 6 -VUOTIAAT", (6, None)),
            ("Jatko 1, yli 6 -vuotiaat (10m uimataito vaaditaan)", (6, None)),
            ("JATKO 2", (None, None)),
            ("JATKO 2, YLI 6 -VUOTIAAT", (6, None)),
            ("Jatko 2, yli 6-vuotiaat (25 m uimataito vaaditaan)", (6, None)),
            ("JATKO YLI 6 -VUOTIAAT", (6, None)),
            ("Jatko, työikäiset", (None, None)),
            ("JATKOUIMAKOULU, Työikäiset", (None, None)),
            ("Jumppakortti Seniorit kevät 2018", (None, None)),
            ("Jumppakortti Seniorit Kevät 2019", (None, None)),
            ("Jumppakortti Seniorit kevät 7.1. - 27.4.2020", (None, None)),
            ("Jumppakortti Työikäiset kevät 2018", (None, None)),
            ("Jumppakortti Työikäiset Kevät 2019", (None, None)),
            ("Jumppakortti Työikäiset kevät 7.1. - 27.4.2020", (None, None)),
            ("Juoksukoulu", (None, None)),
            ("Kahvakuula", (None, None)),
            ("Kahvakuula M + N", (None, None)),
            ("Kehitysvammaisten liikuntaryhmä M + N", (None, None)),
            ("Kehonhuolto", (None, None)),
            ("Kehonhuolto M + N", (None, None)),
            ("KESÄJUMPPA", (None, None)),
            ("Kesäkuntokurssi, kuulonäkövammaiset", (None, None)),
            ("Kesäkuntokurssi, mielenterveyskuntoutujat ja", (None, None)),
            ("KEVYT KESÄJUMPPA", (None, None)),
            ("Kevytjumppa", (None, None)),
            ("Kevytjumppa M + N", (None, None)),
            ("Kevytjumppa N+M", (None, None)),
            ("Kevytjumppa,  Kuulovammaiset ja huonokuuloise", (None, None)),
            ("Kevytjumppa,  Kuulovammaiset ja huonokuuloiset  M + N", (None, None)),
            ("Kiekkokoulu", (None, None)),
            ("Kierto- ja kuntosaliharjoittelu, Kuulovammais", (None, None)),
            (
                "Kierto- ja kuntosaliharjoittelu, Kuulovammaiset ja huonokuuloiset M + N",
                (None, None),
            ),
            ("Kiinteytys", (None, None)),
            ("Konditionssal, Instruerad D + H", (None, None)),
            ("Koululaisuinti", (None, None)),
            ("Kroppsvård och stretching", (None, None)),
            ("Kuntojumppa", (None, None)),
            ("Kuntokävely", (None, None)),
            ("Kuntosalin starttikurssi M + N", (None, None)),
            ("Kuntosaliohjelman laadinta", (None, None)),
            ("Kuntosaliohjelmat ja testaus", (None, None)),
            ("Kuntosalistartti", (None, None)),
            ("Kuulovammaisten lasten Alkeet 4-5-vuotiaat", (4, 5)),
            ("Kuulovammaisten lasten Alkeet 4-7-vuotiaat", (4, 7)),
            ("Kuulovammaisten lasten Alkeet 5-6-vuotiaat", (5, 6)),
            ("Kuulovammaisten lasten Alkeet 6-8-vuotiaat", (6, 8)),
            ("Kuulovammaisten lasten Alkeet yli 7-vuotiaat", (7, None)),
            ("Kuulovammaisten lasten jatko 1, yli 6 -vuotiaat", (6, None)),
            ("Lapsi-aikuinen temppujumppa 2-3 -vuotiaat", (2, 3)),
            ("Lapsi-aikuinen temppujumppa 3-4 -vuotiaat", (3, 4)),
            ("Lattarijumppa", (None, None)),
            ("Lempeää jooga aloittelijoille", (None, None)),
            ("Liikuntahulinat", (None, None)),
            ("Liikuntakaruselli", (None, None)),
            ("LIVcircuit", (None, None)),
            ("LIVcore M + N", (None, None)),
            ("LIVhyväolo", (None, None)),
            ("LIVkahvakuula", (None, None)),
            ("LIVkahvakuula M + N", (None, None)),
            ("LIVkevytjumppa", (None, None)),
            ("LIVkevytjumppa M + N", (None, None)),
            ("LIVlattarit", (None, None)),
            ("LIVsyke", (None, None)),
            ("LIVSyke M + N", (None, None)),
            ("LIVteema", (None, None)),
            ("LIVULKOTREENI", (None, None)),
            ("LIVvenyttely", (None, None)),
            ("LIVvenyttely M + N", (None, None)),
            ("LIVvoima", (None, None)),
            ("LIVvoima M + N", (None, None)),
            ("Luistelukoulu 1. - 3. lk.", (7, 10)),
            ("Luistelukoulu 4-6 lk.", (10, 13)),
            ("Luovan liikkeen ryhmä, kehitysvammaiset aikuiset", (None, None)),
            ("Luovan liikkeen ryhmä, Mielenterveyskuntoutu", (None, None)),
            ("Mailapelit 1. - 6. lk.", (7, 13)),
            ("Mailapelit 3. - 6. lk.", (9, 13)),
            ("Mammatreeni", (None, None)),
            ("Maratonjumppa", (None, None)),
            ("Metsäjooga", (None, None)),
            ("Niska-selkähuolto", (None, None)),
            ("Niska-selkätunti", (None, None)),
            ("NYBÖRJARSIM FÖR ÖVER 7 ÅR", (7, None)),
            ("NYBÖRJARSIM PÅ SVENSKA FÖR BARN, 6-9 år", (6, 9)),
            ("NYBÖRJARSIM PÅ SVENSKA FÖR FLICKOR OCH POJKAR, 5-6 år", (5, 6)),
            ("Ohjattu kuntosaliCircuit M + N", (None, None)),
            ("Ohjattu kuntosaliharjoittelu + 75 vuotiaat M + N", (75, None)),
            ("Ohjattu kuntosaliharjoittelu M", (None, None)),
            ("Ohjattu kuntosaliharjoittelu M + N", (None, None)),
            ("Ohjattu kuntosaliharjoittelu M+N", (None, None)),
            ("Ohjattu kuntosaliharjoittelu Miehet", (None, None)),
            ("Ohjattu kuntosaliharjoittelu Naiset", (None, None)),
            ("Ohjattu Kuntosaliharjoittelu, Kehitysvammaise", (None, None)),
            ("Ohjattu Kuntosaliharjoittelu, Kehitysvammaiset M + N", (None, None)),
            ("Ohjattu Kuntosaliharjoittelu, Kehitysvammaiset M+N", (None, None)),
            ("Ohjattu kuntosaliharjoittelu, Mielenterveysku", (None, None)),
            (
                "Ohjattu kuntosaliharjoittelu, Mielenterveyskuntoutujat M + N",
                (None, None),
            ),
            ("Päiväkotiuinti, Mustikka", (None, None)),
            ("Pallomylly", (None, None)),
            ("Parkour", (None, None)),
            ("Parkour, akrobatia ja sirkuslajit", (None, None)),
            ("Perhehulinat", (None, None)),
            ("Perheliikunta 2-3 -vuotiaat", (2, 3)),
            ("Perhepalloilu", (None, None)),
            ("Pilates", (None, None)),
            ("Porrastreeni", (None, None)),
            ("PUISTOJUMPPA", (None, None)),
            ("PUISTOJUMPPA (Heteniitynkenttä)", (None, None)),
            ("PUISTOJUMPPA (Kansallismuseo)", (None, None)),
            ("PUISTOJUMPPA (Mellunmäen virkistysalue)", (None, None)),
            ("Puistojumppa ja kävely", (None, None)),
            ("Puistojumppa ja sauvakävely", (None, None)),
            ("Redi", (None, None)),
            ("Säestetty jumppa (kevyt) M + N", (None, None)),
            ("Säestetty jumppa M + N", (None, None)),
            ("Sauvakävely", (None, None)),
            ("SENIORI VESIJUMPPA, MIEHET JA NAISET", (None, None)),
            ("SENIORI VESIJUMPPA, NAISET", (None, None)),
            ("SenioriCircuit", (None, None)),
            ("SenioriCircuit M + N", (None, None)),
            ("SenioriCircuit N+M", (None, None)),
            ("SenioriCore", (None, None)),
            ("SenioriCore N+M", (None, None)),
            ("SenioriCore Naiset", (None, None)),
            ("SenioriCore+Venyttely", (None, None)),
            ("SenioriJumppa Miehet", (None, None)),
            ("SenioriJumppa Naiset", (None, None)),
            ("SenioriKahvakuula", (None, None)),
            ("SenioriKehonhuolto", (None, None)),
            ("SenioriKeppijumppa", (None, None)),
            ("SenioriKevytjumppa N + M", (None, None)),
            ("SenioriKuntojumppa", (None, None)),
            ("SenioriKuntojumppa Naiset", (None, None)),
            ("SenioriKuntokävely", (None, None)),
            ("SenioriKuntokävelyTreeni", (None, None)),
            ("Seniorikuntosalistartti", (None, None)),
            ("SenioriKuntotanssi", (None, None)),
            ("SenioriKuntotanssi Naiset", (None, None)),
            ("SenioriLattarijumppa", (None, None)),
            ("Seniorilattarijumppa Naiset", (None, None)),
            ("SenioriLattarijumppa, Naiset", (None, None)),
            ("SenioriLattarit", (None, None)),
            ("SenioriLattarit Naiset", (None, None)),
            ("Senioriltanssi vasta-alkajille M + N", (None, None)),
            ("SenioriPorrastreeni", (None, None)),
            ("SenioriSäestys", (None, None)),
            ("SenioriSäestys N + M", (None, None)),
            ("SenioriSäestys N+M", (None, None)),
            ("Seniorisäpinät", (None, None)),
            ("SenioriSauvakävely", (None, None)),
            ("SenioriSyke", (None, None)),
            ("SenioriSyke M + N", (None, None)),
            ("SenioriTanssi M + N", (None, None)),
            ("Senioritanssi vasta-alkajille M + N", (None, None)),
            ("SenioriTanssillinenSyke", (None, None)),
            ("SenioriTeema", (None, None)),
            ("SenioriUlkojumppa", (None, None)),
            ("SenioriUlkoliikunta", (None, None)),
            ("SenioriUlkotreeni", (None, None)),
            ("SenioriUlkovoima", (None, None)),
            ("SenioriuUlkojumppa", (None, None)),
            ("SenioriuUlkoliikunta", (None, None)),
            ("SenioriVenytely", (None, None)),
            ("SenioriVenyttely", (None, None)),
            ("SenioriVenyttely M + N", (None, None)),
            ("SenioriVenyttely N + M", (None, None)),
            ("SenioriVKehonhuolto", (None, None)),
            ("SenioriVoima", (None, None)),
            ("SenioriVoima N+M", (None, None)),
            ("Showjazz", (None, None)),
            ("Stolgymnastik", (None, None)),
            ("Stretching", (None, None)),
            ("Sunnuntaijumppa", (None, None)),
            ("Syke", (None, None)),
            ("Syke (tanssillinen)", (None, None)),
            ("Syke/Core", (None, None)),
            ("SYVÄNVEDEN JUMPPA", (None, None)),
            ("Syvänveden jumppa M +N", (None, None)),
            ("Syvänveden jumppa Naiset", (None, None)),
            ("Syvänvedenvesijumppa  M + N", (None, None)),
            ("Tanssillinen syke", (None, None)),
            ("Tasapaino ja core", (None, None)),
            ("Tasapaino- ja voimaharjoittelu", (None, None)),
            ("Tasapaino- ja voimaharjoittelu M + N", (None, None)),
            ("Teema", (None, None)),
            ("Teema M + N", (None, None)),
            ("TEKNIIKKA", (None, None)),
            ("TEKNIIKKA 1, työikäiset", (None, None)),
            ("TEKNIIKKA 1, yli 7 -VUOTIAAT", (7, None)),
            ("TEKNIIKKA, Työikäiset", (None, None)),
            ("Temppuhulinat 2-6 -vuotiaat", (2, 6)),
            ("Temppujumppa 3-4 -vuotiaat", (3, 4)),
            ("Temppujumppa 4-5 vuotiaat", (4, 5)),
            ("Temppujumppa 4-5 -vuotiaat", (4, 5)),
            ("Temppujumppa 5-6 vuotiaat", (5, 6)),
            ("Temppujumppa 5-6 -vuotiaat", (5, 6)),
            ("Temppujumppa 7-9 -vuotiaat", (7, 9)),
            ("Temppujumppa perheet 2-6 -vuotiaat", (2, 6)),
            ("Tempputaito 5-6 -vuotiaat", (5, 6)),
            ("TemppuTaito 7-8 -vuotiaat", (7, 8)),
            ("testikurssi", (None, None)),
            ("TUOLIJUMPPA", (None, None)),
            ("Tuolijumppa M + N", (None, None)),
            ("Tuolijumppa N+M", (None, None)),
            ("Tuolijumppa Naiset", (None, None)),
            ("TYTTÖJEN UIMAKOULU, ALKEET 10 - 12 -VUOTIAAT", (10, 12)),
            ("TYTTÖJEN UIMAKOULU, ALKEET 10 - 16 -VUOTIAAT", (10, 16)),
            ("TYTTÖJEN UIMAKOULU, ALKEET 10-16 -vuotiaat", (10, 16)),
            ("TYTTÖJEN UIMAKOULU, ALKEET 7-9 -vuotiaat", (7, 9)),
            ("TYTTÖJEN UIMAKOULU, ALKEET yli 6 -vuotiaat", (6, None)),
            ("TYTTÖJEN UIMAKOULU, JATKO", (None, None)),
            ("TYTTÖJEN UIMAKOULU, JATKO 1", (None, None)),
            ("TYTTÖJEN UIMAKOULU, JATKO 1 yli 6 -vuotiaat", (6, None)),
            (
                "TYTTÖJEN UIMAKOULU, JATKO 1 yli 6 -vuotiaat (10m uimataito vaaditaan)",
                (6, None),
            ),
            ("TYTTÖJEN UIMAKOULU, TEKNIIKKA yli 6 -vuotiaat", (6, None)),
            ("UINTITEKNIIKKA", (None, None)),
            ("Ulkokuntosalistartti", (None, None)),
            ("Ulkoliikunta Mielenterveyskuntoutujat", (None, None)),
            ("Ulkoliikunta, Länsi", (None, None)),
            ("UlkoTreeni", (None, None)),
            ("UlkoVoima", (None, None)),
            ("Uteträning för seniorer", (None, None)),
            ("Vattengymnastik D + H", (None, None)),
            ("Vattengymnastik, D", (None, None)),
            ("Vattengymnastik, Damer", (None, None)),
            ("Vattengymnastik, Krigsveteraner D +  H", (None, None)),
            ("Venyttely", (None, None)),
            ("Venyttely ja rentoutus", (None, None)),
            ("Venyttely ja rentoutus, Mielenterveyskuntoutu", (None, None)),
            ("Venyttely ja rentoutus, Mielenterveyskuntoutujat M + N", (None, None)),
            ("Venyttely M + N", (None, None)),
            ("Vesijumppa", (None, None)),
            ("Vesijumppa  M + N", (None, None)),
            ("Vesijumppa +75 ja veteraanit", (75, None)),
            ("Vesijumppa +75 ja veteraanit, M+N", (75, None)),
            ("VESIJUMPPA +75 -vuotiaat, NAISET", (75, None)),
            ("Vesijumppa M + N", (None, None)),
            ("Vesijumppa M + N, AVH", (None, None)),
            ("Vesijumppa M+N", (None, None)),
            ("Vesijumppa Miehet", (None, None)),
            ("Vesijumppa N", (None, None)),
            ("Vesijumppa N+M", (None, None)),
            ("Vesijumppa Naiset", (None, None)),
            ("Vesijumppa Naiset 75+", (75, None)),
            ("Vesijumppa syöpään sairastuneille M + N", (None, None)),
            ("Vesijumppa,  M + N", (None, None)),
            ("Vesijumppa, Aivohalvaantuneet M + N", (None, None)),
            ("Vesijumppa, Kehitysvammaiset M + N", (None, None)),
            ("Vesijumppa, Kuulovammaiset ja huonokuuloiset ", (None, None)),
            ("Vesijumppa, M + N", (None, None)),
            ("Vesijumppa, Miehet", (None, None)),
            ("VESIJUMPPA, MIEHET JA NAISET", (None, None)),
            ("Vesijumppa, Mielenterveyskuntoutujat M", (None, None)),
            ("Vesijumppa, Mielenterveyskuntoutujat M + N", (None, None)),
            ("Vesijumppa, Mielenterveyskuntoutujat Naiset", (None, None)),
            ("VESIJUMPPA, N+M", (None, None)),
            ("VESIJUMPPA, NAISET", (None, None)),
            ("Vesijumppa, Neurologiset asiakkaat M + N", (None, None)),
            ("Vesijumppa, syöpään sairastuneille, M + N", (None, None)),
            ("Vesijumppa, veteraani M + N", (None, None)),
            ("Vesijuoksu", (None, None)),
            ("Vesitreeni", (None, None)),
            ("Voima", (None, None)),
            ("Voima M + N", (None, None)),
            ("Voimajumppa", (None, None)),
            ("XXL -vesijumppa -ryhmä M + N", (None, None)),
            ("XXL -vesijumppa -ryhmä Naiset", (None, None)),
            ("XXL_kuntosaliharjoittelu M+N", (None, None)),
            ("XXL-jumppa", (None, None)),
            ("XXL-jumppa M + N", (None, None)),
            ("XXL-kuntosaliharjoittelu N+M", (None, None)),
            ("XXL-startti", (None, None)),
            ("XXL-stratti", (None, None)),
            ("XXL-vesijumppa M + N", (None, None)),
            ("XXL-vesijumppa Naiset", (None, None)),
        ],
    )
    def test_parse_age_range_returns_correct_result(
        self, test_input_descriptions, expected_ages
    ):
        assert EnkoraImporter._parse_title_age(test_input_descriptions) == expected_ages

    @pytest.mark.no_test_audit_log
    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "test_input_descriptions,expected_keywords",
        [
            ("Äijäjumppa", {EnkoraImporter.AUDIENCE_MEN, EnkoraImporter.SPORT_JUMPPA}),
            (
                "Aikuisten tekniikka uimakoulu",
                {EnkoraImporter.AUDIENCE_ADULTS, EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            (
                "Aikuisten tekniikkauimakoulu",
                {EnkoraImporter.AUDIENCE_ADULTS, EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            ("ALKEET 5-6 -VUOTIAAT", set()),
            ("ALKEET 5-6-VUOTIAAT", set()),
            ("ALKEET yli 7 -vuotiaat", set()),
            ("ALKEET YLI 7-vuotiaat", set()),
            ("ALKEET, 5-6 -vuotiaat", set()),
            ("ALKEET, naiset", {EnkoraImporter.AUDIENCE_WOMEN}),
            ("ALKEET, työikäiset", {EnkoraImporter.AUDIENCE_ADULTS}),
            ("ALKEET, yli 7 -vuotiaat", set()),
            (
                "Alkeisjatko uimakoulu, työikäiset",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES, EnkoraImporter.AUDIENCE_ADULTS},
            ),
            ("Alkeisjatko, työikäiset", {EnkoraImporter.AUDIENCE_ADULTS}),
            (
                "Alkeisjatkouimakoulu N, työikäiset",
                {
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.AUDIENCE_ADULTS,
                },
            ),
            (
                "Alkeisuimakoulu, työikäiset N+M",
                {
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                    EnkoraImporter.AUDIENCE_ADULTS,
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.AUDIENCE_MEN,
                },
            ),
            (
                "AquaPolo -kurssi M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.AUDIENCE_MEN,
                },
            ),
            (
                "AquaPoLo -kurssi Naiset",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            (
                "Balans och styrketräning D + H",
                {
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                },
            ),
            (
                "Balansgång D + H",
                {
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                },
            ),
            ("Circuit", {EnkoraImporter.SPORT_STRENGTH_TRAINING}),
            (
                "Core ja kehonhuolto",
                {
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_BALANCE,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_CARE,
                },
            ),
            ("Dancemix", {EnkoraImporter.SPORT_DANCING}),
            ("Easy Hockey", {EnkoraImporter.SPORT_ICE_HOCKEY}),
            ("EasySport jääkiekko", {EnkoraImporter.SPORT_ICE_HOCKEY}),
            ("EasySport luistelu", {EnkoraImporter.SPORT_SKATING}),
            ("EasySport -luistelukoulu 1. - 3. lk.", {EnkoraImporter.SPORT_SKATING}),
            (
                "EasySport -mailapelit 1. - 4. lk.",
                {EnkoraImporter.SPORT_MAILAPELIT, EnkoraImporter.SPORT_GAMES},
            ),
            (
                "EasySport -mailapelit 1. - 6. lk.",
                {EnkoraImporter.SPORT_MAILAPELIT, EnkoraImporter.SPORT_GAMES},
            ),
            (
                "EasySport -mailapelit 3. - 6. lk.",
                {EnkoraImporter.SPORT_MAILAPELIT, EnkoraImporter.SPORT_GAMES},
            ),
            (
                "EasySport -mailapelit 5. - 6. lk.",
                {EnkoraImporter.SPORT_MAILAPELIT, EnkoraImporter.SPORT_GAMES},
            ),
            ("EASYSPORT MELONKURSSI 12-15 -vuotiaat", {EnkoraImporter.SPORT_CANOEING}),
            ("EASYSPORT MELONKURSSI 9-12 -vuotiaat", {EnkoraImporter.SPORT_CANOEING}),
            ("EASYSPORT MELONTA 10-13 -vuotiaat", {EnkoraImporter.SPORT_CANOEING}),
            ("EASYSPORT MELONTA 12-15 -vuotiaat", {EnkoraImporter.SPORT_CANOEING}),
            ("EASYSPORT MELONTA 13-15 -vuotiaat", {EnkoraImporter.SPORT_CANOEING}),
            ("EASYSPORT MELONTA 9-12 -vuotiaat", {EnkoraImporter.SPORT_CANOEING}),
            (
                "EASYSPORT PADEL-MAILAPELIKURSSI 10-13 -vuotiaat",
                {EnkoraImporter.SPORT_PADEL},
            ),
            (
                "EasySport -Parkour, akrobatia ja sirkuslajit",
                {
                    EnkoraImporter.SPORT_PARKOUR,
                    EnkoraImporter.SPORT_ACROBATICS,
                    EnkoraImporter.SPORT_CIRCUS,
                },
            ),
            ("EasySport -sirkus", {EnkoraImporter.SPORT_CIRCUS}),
            (
                "EasySport -sulkapallo &  squash 3. - 4. lk.",
                {EnkoraImporter.SPORT_BADMINTON, EnkoraImporter.SPORT_SQUASH},
            ),
            (
                "EasySport -sulkapallo & squash 5. - 6. lk.",
                {EnkoraImporter.SPORT_BADMINTON, EnkoraImporter.SPORT_SQUASH},
            ),
            (
                "EasySport -sulkapallo ja squash 3. - 4. lk.",
                {EnkoraImporter.SPORT_BADMINTON, EnkoraImporter.SPORT_SQUASH},
            ),
            (
                "EasySport -sulkapallo ja squash 5. - 6. lk.",
                {EnkoraImporter.SPORT_BADMINTON, EnkoraImporter.SPORT_SQUASH},
            ),
            ("EasySport -tanssi 1. - 6. lk.", {EnkoraImporter.SPORT_DANCING}),
            (
                "EasySport -tanssi 1. - 6. lk. (Break dance)",
                {EnkoraImporter.SPORT_DANCING},
            ),
            (
                "EasySport -tanssi 1. - 6. lk. (Hip Hop, opetuskieli englanti)",
                {EnkoraImporter.SPORT_DANCING, EnkoraImporter.LANGUAGE_ENGLISH},
            ),
            (
                "EasySport -tanssi 1. - 6. lk. (Showtanssi)",
                {EnkoraImporter.SPORT_DANCING},
            ),
            ("EasySport Temppu ja tramppa", {EnkoraImporter.SPORT_TRAMPOLINING}),
            ("EASYSPORT TENNIS, ALKEET 10-12 -vuotiaat", {EnkoraImporter.SPORT_TENNIS}),
            (
                "EASYSPORT TENNIS, ALKEET yli 10 -vuotiaat",
                {EnkoraImporter.SPORT_TENNIS},
            ),
            ("EASYSPORT TENNIS, ALKEET,  7-9 -vuotiaat", {EnkoraImporter.SPORT_TENNIS}),
            (
                "EASYSPORT TENNIS, ALKEET, yli 10 -vuotiaat",
                {EnkoraImporter.SPORT_TENNIS},
            ),
            (
                "EASYSPORT YLEISURHEILUKOULU, 7-14 -vuotiaat",
                {EnkoraImporter.SPORT_TRACK_N_FIELD},
            ),
            (
                "ERITYISLASTEN UIMAKOULU ALKEET YLI 6 -VUOTIAAT",
                {
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "ERITYISLASTEN UIMAKOULU JATKO YLI 6 -VUOTIAAT",
                {
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "ERITYISLASTEN UIMAKOULU, ALKEET, yli 7 -vuotiaat",
                {
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Erityislasten vesiliikunta",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.SPORT_ADAPTED_PE},
            ),
            (
                "Erityislasten vesiliikunta 10-16 -vuotiaat",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.SPORT_ADAPTED_PE},
            ),
            (
                "Erityislasten vesiliikunta 6-9 -vuotiaat",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.SPORT_ADAPTED_PE},
            ),
            (
                "Erityislasten vesiseikkailu",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.SPORT_ADAPTED_PE},
            ),
            ("Foam roller", {EnkoraImporter.SPORT_BODY_CONTROL}),
            (
                "Foam roller & kehonhuolto",
                {
                    EnkoraImporter.SPORT_BODY_CONTROL,
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_MUSCLE_CARE,
                    EnkoraImporter.SPORT_BALANCE,
                },
            ),
            (
                "Fortsättningssimskola på svenska för nybörjare, 5-6 år",
                {EnkoraImporter.LANGUAGE_SWEDISH},
            ),
            ("Hallivesijumppa", {EnkoraImporter.SPORT_WATER_EXERCISE}),
            (
                "Hyvänolonjumppa",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.SPORT_WELL_BEING,
                    EnkoraImporter.SPORT_RELAXATION,
                },
            ),
            (
                "Hyväolo",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.SPORT_WELL_BEING,
                    EnkoraImporter.SPORT_RELAXATION,
                },
            ),
            (
                "Itsenäinen harjoittelu kuntosalissa ja uima-altaassa N+M",
                {EnkoraImporter.AUDIENCE_WOMEN, EnkoraImporter.AUDIENCE_MEN},
            ),
            (
                "Itsenäinen kuntosaliharjoittelu /Aktiivix",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            ("Jääkiekko", {EnkoraImporter.SPORT_ICE_HOCKEY}),
            ("JATKO", set()),
            ("JATKO 1", set()),
            ("Jatko 1 (10m uimataito vaaditaan)", set()),
            ("JATKO 1, YLI 6 -VUOTIAAT", set()),
            ("Jatko 1, yli 6 -vuotiaat (10m uimataito vaaditaan)", set()),
            ("JATKO 2", set()),
            ("JATKO 2, YLI 6 -VUOTIAAT", set()),
            ("Jatko 2, yli 6-vuotiaat (25 m uimataito vaaditaan)", set()),
            ("JATKO YLI 6 -VUOTIAAT", set()),
            ("Jatko, työikäiset", {EnkoraImporter.AUDIENCE_ADULTS}),
            (
                "JATKOUIMAKOULU, Työikäiset",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES, EnkoraImporter.AUDIENCE_ADULTS},
            ),
            (
                "Jumppakortti Seniorit kevät 2018",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.AUDIENCE_SENIORS},
            ),
            (
                "Jumppakortti Seniorit Kevät 2019",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.AUDIENCE_SENIORS},
            ),
            (
                "Jumppakortti Seniorit kevät 7.1. - 27.4.2020",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.AUDIENCE_SENIORS},
            ),
            (
                "Jumppakortti Työikäiset kevät 2018",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.AUDIENCE_ADULTS},
            ),
            (
                "Jumppakortti Työikäiset Kevät 2019",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.AUDIENCE_ADULTS},
            ),
            (
                "Jumppakortti Työikäiset kevät 7.1. - 27.4.2020",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.AUDIENCE_ADULTS},
            ),
            ("Juoksukoulu", {EnkoraImporter.SPORT_RUNNING}),
            (
                "Kahvakuula",
                {
                    EnkoraImporter.SPORT_KETTLEBELL,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "Kahvakuula M + N",
                {
                    EnkoraImporter.SPORT_KETTLEBELL,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "Kehitysvammaisten liikuntaryhmä M + N",
                {
                    EnkoraImporter.AUDIENCE_INTELLECTUAL_DISABILITY,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kehonhuolto",
                {
                    EnkoraImporter.SPORT_MUSCLE_CARE,
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_BALANCE,
                },
            ),
            (
                "Kehonhuolto M + N",
                {
                    EnkoraImporter.SPORT_MUSCLE_CARE,
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_BALANCE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("KESÄJUMPPA", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "Kesäkuntokurssi, kuulonäkövammaiset",
                {
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kesäkuntokurssi, mielenterveyskuntoutujat ja",
                {
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            ("KEVYT KESÄJUMPPA", {EnkoraImporter.SPORT_JUMPPA}),
            ("Kevytjumppa", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "Kevytjumppa M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Kevytjumppa N+M",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Kevytjumppa,  Kuulovammaiset ja huonokuuloise",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kevytjumppa,  Kuulovammaiset ja huonokuuloiset  M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Kiekkokoulu", {EnkoraImporter.SPORT_ICE_HOCKEY}),
            (
                "Kierto- ja kuntosaliharjoittelu, Kuulovammais",
                {
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                },
            ),
            (
                "Kierto- ja kuntosaliharjoittelu, Kuulovammaiset ja huonokuuloiset M + N",
                {
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.AUDIENCE_WOMEN,
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.AUDIENCE_MEN,
                },
            ),
            ("Kiinteytys", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "Konditionssal, Instruerad D + H",
                {
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Koululaisuinti", {EnkoraImporter.SPORT_SWIMMING_CLASSES}),
            (
                "Kroppsvård och stretching",
                {
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.SPORT_STRETCHING,
                },
            ),
            ("Kuntojumppa", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "Kuntokävely",
                {EnkoraImporter.SPORT_WALKING, EnkoraImporter.SPORT_JUMPPA},
            ),
            (
                "Kuntosalin starttikurssi M + N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Kuntosaliohjelman laadinta", {EnkoraImporter.SPORT_GYM}),
            ("Kuntosaliohjelmat ja testaus", {EnkoraImporter.SPORT_GYM}),
            ("Kuntosalistartti", {EnkoraImporter.SPORT_GYM}),
            (
                "Kuulovammaisten lasten Alkeet 4-5-vuotiaat",
                {
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kuulovammaisten lasten Alkeet 4-7-vuotiaat",
                {
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kuulovammaisten lasten Alkeet 5-6-vuotiaat",
                {
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kuulovammaisten lasten Alkeet 6-8-vuotiaat",
                {
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kuulovammaisten lasten Alkeet yli 7-vuotiaat",
                {
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Kuulovammaisten lasten jatko 1, yli 6 -vuotiaat",
                {
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                },
            ),
            (
                "Lapsi-aikuinen temppujumppa 2-3 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Lapsi-aikuinen temppujumppa 3-4 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            ("Lattarijumppa", {EnkoraImporter.SPORT_DANCING}),
            ("Lempeää jooga aloittelijoille", {EnkoraImporter.SPORT_YOGA}),
            ("Liikuntahulinat", set()),
            ("Liikuntakaruselli", set()),
            ("LIVcircuit", {EnkoraImporter.SPORT_STRENGTH_TRAINING}),
            (
                "LIVcore M + N",
                {
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "LIVhyväolo",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.SPORT_WELL_BEING,
                    EnkoraImporter.SPORT_RELAXATION,
                },
            ),
            (
                "LIVkahvakuula",
                {
                    EnkoraImporter.SPORT_KETTLEBELL,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "LIVkahvakuula M + N",
                {
                    EnkoraImporter.SPORT_KETTLEBELL,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("LIVkevytjumppa", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "LIVkevytjumppa M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("LIVlattarit", {EnkoraImporter.SPORT_DANCING}),
            ("LIVsyke", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "LIVSyke M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("LIVteema", set()),
            ("LIVULKOTREENI", {EnkoraImporter.SPORT_OUTDOOR_PE}),
            ("LIVvenyttely", {EnkoraImporter.SPORT_STRETCHING}),
            (
                "LIVvenyttely M + N",
                {
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("LIVvoima", {EnkoraImporter.SPORT_STRENGTH_TRAINING}),
            (
                "LIVvoima M + N",
                {
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Luistelukoulu 1. - 3. lk.", {EnkoraImporter.SPORT_SKATING}),
            ("Luistelukoulu 4-6 lk.", {EnkoraImporter.SPORT_SKATING}),
            (
                "Luovan liikkeen ryhmä, kehitysvammaiset aikuiset",
                {
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_INTELLECTUAL_DISABILITY,
                },
            ),
            (
                "Luovan liikkeen ryhmä, Mielenterveyskuntoutu",
                {
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                },
            ),
            (
                "Mailapelit 1. - 6. lk.",
                {EnkoraImporter.SPORT_MAILAPELIT, EnkoraImporter.SPORT_GAMES},
            ),
            (
                "Mailapelit 3. - 6. lk.",
                {EnkoraImporter.SPORT_MAILAPELIT, EnkoraImporter.SPORT_GAMES},
            ),
            (
                "Mammatreeni",
                {EnkoraImporter.AUDIENCE_WOMEN, EnkoraImporter.SPORT_JUMPPA},
            ),
            ("Maratonjumppa", {EnkoraImporter.SPORT_JUMPPA}),
            ("Metsäjooga", {EnkoraImporter.SPORT_YOGA}),
            ("Niska-selkähuolto", {EnkoraImporter.SPORT_JUMPPA}),
            ("Niska-selkätunti", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "NYBÖRJARSIM FÖR ÖVER 7 ÅR",
                {
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                },
            ),
            (
                "NYBÖRJARSIM PÅ SVENSKA FÖR BARN, 6-9 år",
                {
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                },
            ),
            (
                "NYBÖRJARSIM PÅ SVENSKA FÖR FLICKOR OCH POJKAR, 5-6 år",
                {
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.SPORT_SWIMMING_CLASSES,
                },
            ),
            (
                "Ohjattu kuntosaliCircuit M + N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu + 75 vuotiaat M + N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu M",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.AUDIENCE_MEN,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu M + N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu M+N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu Miehet",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.AUDIENCE_MEN,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu Naiset",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Ohjattu Kuntosaliharjoittelu, Kehitysvammaise",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_INTELLECTUAL_DISABILITY,
                },
            ),
            (
                "Ohjattu Kuntosaliharjoittelu, Kehitysvammaiset M + N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_INTELLECTUAL_DISABILITY,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Ohjattu Kuntosaliharjoittelu, Kehitysvammaiset M+N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_INTELLECTUAL_DISABILITY,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu, Mielenterveysku",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                },
            ),
            (
                "Ohjattu kuntosaliharjoittelu, Mielenterveyskuntoutujat M + N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Päiväkotiuinti, Mustikka", {EnkoraImporter.SPORT_SWIMMING_CLASSES}),
            ("Pallomylly", set()),
            ("Parkour", {EnkoraImporter.SPORT_PARKOUR}),
            (
                "Parkour, akrobatia ja sirkuslajit",
                {
                    EnkoraImporter.SPORT_PARKOUR,
                    EnkoraImporter.SPORT_ACROBATICS,
                    EnkoraImporter.SPORT_CIRCUS,
                },
            ),
            ("Perhehulinat", set()),
            ("Perheliikunta 2-3 -vuotiaat", set()),
            ("Perhepalloilu", set()),
            ("Pilates", set()),
            (
                "Porrastreeni",
                {EnkoraImporter.SPORT_WORKOUT_STAIRS, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            ("PUISTOJUMPPA", {EnkoraImporter.SPORT_OUTDOOR_PE}),
            ("PUISTOJUMPPA (Kansallismuseo)", {EnkoraImporter.SPORT_OUTDOOR_PE}),
            (
                "PUISTOJUMPPA (Mellunmäen virkistysalue)",
                {EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "Puistojumppa ja kävely",
                {EnkoraImporter.SPORT_OUTDOOR_PE, EnkoraImporter.SPORT_WALKING},
            ),
            (
                "Puistojumppa ja sauvakävely",
                {EnkoraImporter.SPORT_OUTDOOR_PE, EnkoraImporter.SPORT_NORDIC_WALKING},
            ),
            ("Redi", set()),
            (
                "Säestetty jumppa (kevyt) M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Säestetty jumppa M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Sauvakävely",
                {EnkoraImporter.SPORT_NORDIC_WALKING, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "SENIORI VESIJUMPPA, MIEHET JA NAISET",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SENIORI VESIJUMPPA, NAISET",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriCircuit",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "SenioriCircuit M + N",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriCircuit N+M",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriCore",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "SenioriCore N+M",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriCore Naiset",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriCore+Venyttely",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_STRETCHING,
                },
            ),
            (
                "SenioriJumppa Miehet",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                },
            ),
            (
                "SenioriJumppa Naiset",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriKahvakuula",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_KETTLEBELL,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "SenioriKehonhuolto",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_BALANCE,
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_MUSCLE_CARE,
                },
            ),
            (
                "SenioriKeppijumppa",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_BROOMSTICK},
            ),
            (
                "SenioriKevytjumppa N + M",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriKuntojumppa",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_JUMPPA},
            ),
            (
                "SenioriKuntojumppa Naiset",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriKuntokävely",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_WALKING,
                    EnkoraImporter.SPORT_OUTDOOR_PE,
                },
            ),
            (
                "SenioriKuntokävelyTreeni",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_WALKING,
                    EnkoraImporter.SPORT_OUTDOOR_PE,
                },
            ),
            (
                "Seniorikuntosalistartti",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "SenioriKuntotanssi",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_DANCING},
            ),
            (
                "SenioriKuntotanssi Naiset",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_DANCING,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriLattarijumppa",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_DANCING},
            ),
            (
                "Seniorilattarijumppa Naiset",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_DANCING,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriLattarijumppa, Naiset",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_DANCING,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriLattarit",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_DANCING},
            ),
            (
                "SenioriLattarit Naiset",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_DANCING,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Senioriltanssi vasta-alkajille M + N",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_DANCING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriPorrastreeni",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_WORKOUT_STAIRS,
                    EnkoraImporter.SPORT_OUTDOOR_PE,
                },
            ),
            (
                "SenioriSäestys",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_MUSICAL_EXERCISE,
                    EnkoraImporter.SPORT_JUMPPA,
                },
            ),
            (
                "SenioriSäestys N + M",
                {
                    EnkoraImporter.SPORT_MUSICAL_EXERCISE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriSäestys N+M",
                {
                    EnkoraImporter.SPORT_MUSICAL_EXERCISE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Seniorisäpinät", {EnkoraImporter.AUDIENCE_SENIORS}),
            (
                "SenioriSauvakävely",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_NORDIC_WALKING,
                    EnkoraImporter.SPORT_OUTDOOR_PE,
                },
            ),
            (
                "SenioriSyke",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.AUDIENCE_SENIORS},
            ),
            (
                "SenioriSyke M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriTanssi M + N",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_DANCING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Senioritanssi vasta-alkajille M + N",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_DANCING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriTanssillinenSyke",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_DANCING},
            ),
            ("SenioriTeema", {EnkoraImporter.AUDIENCE_SENIORS}),
            (
                "SenioriUlkojumppa",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "SenioriUlkoliikunta",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "SenioriUlkotreeni",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "SenioriUlkovoima",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "SenioriuUlkojumppa",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "SenioriuUlkoliikunta",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_OUTDOOR_PE},
            ),
            (
                "SenioriVenytely",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_STRETCHING},
            ),
            (
                "SenioriVenyttely",
                {EnkoraImporter.AUDIENCE_SENIORS, EnkoraImporter.SPORT_STRETCHING},
            ),
            (
                "SenioriVenyttely M + N",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriVenyttely N + M",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "SenioriVKehonhuolto",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_BALANCE,
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_MUSCLE_CARE,
                },
            ),
            (
                "SenioriVoima",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "SenioriVoima N+M",
                {
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Showjazz", {EnkoraImporter.SPORT_DANCING}),
            (
                "Stolgymnastik",
                {
                    EnkoraImporter.SPORT_CHAIR_PE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                },
            ),
            ("Stretching", {EnkoraImporter.SPORT_STRETCHING}),
            ("Sunnuntaijumppa", {EnkoraImporter.SPORT_JUMPPA}),
            ("Syke", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "Syke (tanssillinen)",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.SPORT_DANCING},
            ),
            (
                "Syke/Core",
                {EnkoraImporter.SPORT_STRENGTH_TRAINING, EnkoraImporter.SPORT_JUMPPA},
            ),
            (
                "SYVÄNVEDEN JUMPPA",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.SPORT_JUMPPA},
            ),
            (
                "Syvänveden jumppa M +N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Syvänveden jumppa Naiset",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Syvänvedenvesijumppa  M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Tanssillinen syke",
                {EnkoraImporter.SPORT_JUMPPA, EnkoraImporter.SPORT_DANCING},
            ),
            ("Tasapaino ja core", {EnkoraImporter.SPORT_STRENGTH_TRAINING}),
            (
                "Tasapaino- ja voimaharjoittelu",
                {EnkoraImporter.SPORT_STRENGTH_TRAINING},
            ),
            (
                "Tasapaino- ja voimaharjoittelu M + N",
                {
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Teema", set()),
            (
                "Teema M + N",
                {EnkoraImporter.AUDIENCE_MEN, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            ("TEKNIIKKA", set()),
            ("TEKNIIKKA 1, työikäiset", {EnkoraImporter.AUDIENCE_ADULTS}),
            ("TEKNIIKKA 1, yli 7 -VUOTIAAT", set()),
            ("TEKNIIKKA, Työikäiset", {EnkoraImporter.AUDIENCE_ADULTS}),
            (
                "Temppuhulinat 2-6 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Temppujumppa 3-4 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Temppujumppa 4-5 vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Temppujumppa 4-5 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Temppujumppa 5-6 vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Temppujumppa 5-6 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Temppujumppa 7-9 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Temppujumppa perheet 2-6 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "Tempputaito 5-6 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            (
                "TemppuTaito 7-8 -vuotiaat",
                {EnkoraImporter.SPORT_TEMPPUJUMPPA, EnkoraImporter.AUDIENCE_CHILDREN},
            ),
            ("testikurssi", set()),
            (
                "TUOLIJUMPPA",
                {EnkoraImporter.SPORT_CHAIR_PE, EnkoraImporter.SPORT_JUMPPA},
            ),
            (
                "Tuolijumppa M + N",
                {
                    EnkoraImporter.SPORT_CHAIR_PE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Tuolijumppa N+M",
                {
                    EnkoraImporter.SPORT_CHAIR_PE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Tuolijumppa Naiset",
                {
                    EnkoraImporter.SPORT_CHAIR_PE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "TYTTÖJEN UIMAKOULU, ALKEET 10 - 12 -VUOTIAAT",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            (
                "TYTTÖJEN UIMAKOULU, ALKEET 10 - 16 -VUOTIAAT",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            (
                "TYTTÖJEN UIMAKOULU, ALKEET 10-16 -vuotiaat",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            (
                "TYTTÖJEN UIMAKOULU, ALKEET 7-9 -vuotiaat",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            (
                "TYTTÖJEN UIMAKOULU, ALKEET yli 6 -vuotiaat",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            ("TYTTÖJEN UIMAKOULU, JATKO", {EnkoraImporter.SPORT_SWIMMING_CLASSES}),
            ("TYTTÖJEN UIMAKOULU, JATKO 1", {EnkoraImporter.SPORT_SWIMMING_CLASSES}),
            (
                "TYTTÖJEN UIMAKOULU, JATKO 1 yli 6 -vuotiaat",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            (
                "TYTTÖJEN UIMAKOULU, JATKO 1 yli 6 -vuotiaat (10m uimataito vaaditaan)",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            (
                "TYTTÖJEN UIMAKOULU, TEKNIIKKA yli 6 -vuotiaat",
                {EnkoraImporter.SPORT_SWIMMING_CLASSES},
            ),
            ("UINTITEKNIIKKA", {EnkoraImporter.SPORT_SWIMMING_CLASSES}),
            ("Ulkokuntosalistartti", {EnkoraImporter.SPORT_OUTDOOR_PE}),
            (
                "Ulkoliikunta Mielenterveyskuntoutujat",
                {
                    EnkoraImporter.SPORT_OUTDOOR_PE,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                },
            ),
            ("Ulkoliikunta, Länsi", {EnkoraImporter.SPORT_OUTDOOR_PE}),
            ("UlkoTreeni", {EnkoraImporter.SPORT_OUTDOOR_PE}),
            (
                "UlkoVoima",
                {
                    EnkoraImporter.SPORT_OUTDOOR_PE,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                },
            ),
            (
                "Uteträning för seniorer",
                {
                    EnkoraImporter.SPORT_OUTDOOR_PE,
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.AUDIENCE_SENIORS,
                },
            ),
            (
                "Vattengymnastik D + H",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vattengymnastik, D",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vattengymnastik, Damer",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vattengymnastik, Krigsveteraner D +  H",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.LANGUAGE_SWEDISH,
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Venyttely", {EnkoraImporter.SPORT_STRETCHING}),
            ("Venyttely ja rentoutus", {EnkoraImporter.SPORT_STRETCHING}),
            (
                "Venyttely ja rentoutus, Mielenterveyskuntoutu",
                {
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                },
            ),
            (
                "Venyttely ja rentoutus, Mielenterveyskuntoutujat M + N",
                {
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Venyttely M + N",
                {
                    EnkoraImporter.SPORT_STRETCHING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Vesijumppa", {EnkoraImporter.SPORT_WATER_EXERCISE}),
            (
                "Vesijumppa  M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa +75 ja veteraanit",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_SENIORS},
            ),
            (
                "Vesijumppa +75 ja veteraanit, M+N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "VESIJUMPPA +75 -vuotiaat, NAISET",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            (
                "Vesijumppa M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa M + N, AVH",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa M+N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa Miehet",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_MEN},
            ),
            (
                "Vesijumppa N",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            (
                "Vesijumppa N+M",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa Naiset",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            (
                "Vesijumppa Naiset 75+",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa syöpään sairastuneille M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa,  M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, Aivohalvaantuneet M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, Kehitysvammaiset M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_INTELLECTUAL_DISABILITY,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, Kuulovammaiset ja huonokuuloiset ",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_HEARING_IMPAIRED,
                },
            ),
            (
                "Vesijumppa, M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, Miehet",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_MEN},
            ),
            (
                "VESIJUMPPA, MIEHET JA NAISET",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, Mielenterveyskuntoutujat M",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                    EnkoraImporter.AUDIENCE_MEN,
                },
            ),
            (
                "Vesijumppa, Mielenterveyskuntoutujat M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, Mielenterveyskuntoutujat Naiset",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.SPORT_ADAPTED_PE,
                    EnkoraImporter.AUDIENCE_PSYCHIATRIC_REHAB,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "VESIJUMPPA, N+M",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "VESIJUMPPA, NAISET",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            (
                "Vesijumppa, Neurologiset asiakkaat M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, syöpään sairastuneille, M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "Vesijumppa, veteraani M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_SENIORS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Vesijuoksu", {EnkoraImporter.SPORT_WATER_EXERCISE}),
            ("Vesitreeni", {EnkoraImporter.SPORT_WATER_EXERCISE}),
            ("Voima", {EnkoraImporter.SPORT_STRENGTH_TRAINING}),
            (
                "Voima M + N",
                {
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("Voimajumppa", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "XXL -vesijumppa -ryhmä M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "XXL -vesijumppa -ryhmä Naiset",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            (
                "XXL_kuntosaliharjoittelu M+N",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("XXL-jumppa", {EnkoraImporter.SPORT_JUMPPA}),
            (
                "XXL-jumppa M + N",
                {
                    EnkoraImporter.SPORT_JUMPPA,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "XXL-kuntosaliharjoittelu N+M",
                {
                    EnkoraImporter.SPORT_GYM,
                    EnkoraImporter.SPORT_STRENGTH_TRAINING,
                    EnkoraImporter.SPORT_MUSCLE_FITNESS,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            ("XXL-startti", {EnkoraImporter.SPORT_GYM}),
            ("XXL-stratti", set()),
            (
                "XXL-vesijumppa M + N",
                {
                    EnkoraImporter.SPORT_WATER_EXERCISE,
                    EnkoraImporter.AUDIENCE_MEN,
                    EnkoraImporter.AUDIENCE_WOMEN,
                },
            ),
            (
                "XXL-vesijumppa Naiset",
                {EnkoraImporter.SPORT_WATER_EXERCISE, EnkoraImporter.AUDIENCE_WOMEN},
            ),
            ("EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", {EnkoraImporter.SPORT_TENNIS}),
        ],
    )
    @pytest.mark.no_test_audit_log
    def test_parse_keywords_returns_correct_result(
        self, test_input_descriptions, expected_keywords
    ):
        assert (
            EnkoraImporter._parse_title_keywords(test_input_descriptions)
            == expected_keywords
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "test_input_descriptions,expected_age_ranges",
        [
            ("EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", (7, 9)),
            ("Aikuisten tekniikka uimakoulu", (None, None)),
            ("ALKEET YLI 7-vuotiaat", (7, None)),
        ],
    )
    @pytest.mark.no_test_audit_log
    def test_parse_age_returns_correct_result(
        self, test_input_descriptions, expected_age_ranges
    ):
        assert (
            EnkoraImporter._parse_title_age(test_input_descriptions)
            == expected_age_ranges
        )

    @pytest.fixture
    def populate_referenced_data_to_db(self):
        """
        Add dependency data into SQL
        """
        test_input_data = [
            # Line of output is generated with:
            # from django.core import serializers
            # serializers.serialize('json', [Keyword.objects.get(id='yso:p6915'), ])
            '[{"model": "events.datasource", "pk": "tprek", "fields": {"name": "Toimipisterekisteri", "api_key": "", '
            '"owner": null, "user_editable_resources": false, "user_editable_organizations": false, "edit_past_events'
            '": false, "create_past_events": false, "private": false}}]',
            '[{"model": "django_orghierarchy.organization", "pk": "ahjo:u021600", "fields": {"data_source": "ahjo", "'
            'origin_id": "u021600", "created_time": "2023-05-31T12:51:28.663Z", "last_modified_time": "2023-05-31T12:'
            '51:28.666Z", "internal_type": "normal", "classification": null, "name": "Tietotekniikka- ja viestintäosa'
            'sto", "founding_date": null, "dissolution_date": null, "parent": null, "created_by": null, "last_modifie'
            'd_by": null, "replaced_by": null, "lft": 1, "rght": 2, "tree_id": 2, "level": 0, "admin_users": [], "reg'
            'ular_users": []}}]',
            '[{"model": "django_orghierarchy.organization", "pk": "hy:kansalliskirjasto", "fields": {"data_source": "'
            'hy", "origin_id": "kansalliskirjasto", "created_time": "2023-05-31T12:10:46.921Z", "last_modified_time":'
            ' "2023-05-31T12:10:46.924Z", "internal_type": "normal", "classification": null, "name": "Kansalliskirjas'
            'to", "founding_date": null, "dissolution_date": null, "parent": null, "created_by": null, "last_modified'
            '_by": null, "replaced_by": null, "lft": 1, "rght": 2, "tree_id": 1, "level": 0, "admin_users": [], "regu'
            'lar_users": []}}]',
            '[{"model": "events.datasource", "pk": "ahjo", "fields": {"name": "Ahjo", "api_key": "", "owner": null, "'
            'user_editable_resources": false, "user_editable_organizations": false, "edit_past_events": false, "creat'
            'e_past_events": false, "private": false}}]',
            '[{"model": "events.datasource", "pk": "yso", "fields": {"name": "Yleinen suomalainen ontologia", "api_ke'
            'y": "", "owner": null, "user_editable_resources": false, "user_editable_organizations": false, "edit_pas'
            't_events": false, "create_past_events": false, "private": false}}]',
            '[{"model": "events.datasource", "pk": "hy", "fields": {"name": "Helsingin yliopisto", "api_key": "", "ow'
            'ner": null, "user_editable_resources": false, "user_editable_organizations": false, "edit_past_events": '
            'false, "create_past_events": false, "private": false}}]',
            '[{"model": "events.place", "pk": "tprek:45650", "fields": {"custom_data": null, "image": null, "data_sou'
            'rce": "tprek", "name": "Latokartanon liikuntapuisto", "name_fi": "Latokartanon liikuntapuisto", "name_sv'
            '": "Ladugårdens idrottspark", "name_en": "Latokartano sports park", "name_zh_hans": null, "name_ru": nul'
            'l, "name_ar": null, "origin_id": "45650", "created_time": "2023-05-31T12:57:19.190Z", "last_modified_tim'
            'e": "2023-05-31T12:57:19.190Z", "created_by": null, "last_modified_by": null, "publisher": "ahjo:u021600'
            '", "info_url": null, "info_url_fi": null, "info_url_sv": null, "info_url_en": null, "info_url_zh_hans": '
            'null, "info_url_ru": null, "info_url_ar": null, "description": "Latokartanon liikuntapuistossa on jalkap'
            "allo-, koripallo-, lentopallo- ja tenniskentät sekä paikka yleisurheilulle. Lisäksi Latokartanossa on Da"
            "vid City Linen painopakkasäädettäviä ulkokuntoiluvälineitä ja eri korkuisia leuanveto- ja riipuntatankoj"
            'a.", "description_fi": "Latokartanon liikuntapuistossa on jalkapallo-, koripallo-, lentopallo- ja tennis'
            "kentät sekä paikka yleisurheilulle. Lisäksi Latokartanossa on David City Linen painopakkasäädettäviä ulk"
            'okuntoiluvälineitä ja eri korkuisia leuanveto- ja riipuntatankoja.", "description_sv": "I Ladugårdens id'
            "rottspark finns fotbolls-, basket- och volleybollplaner samt tennisbanor samt en plats för friidrott. De"
            "ssutom finns i Ladugården David City Lines viktinställbara redskap för utomhusträning och olika höga arm"
            'hävnings- och hängningsstänger.", "description_en": "Latokartano sports park has a football field, baske'
            "tball, volleyball and tennis courts, and a place for athletics. In addition, Latokartano has David City "
            "Line's weight-adjustable outdoor exercise equipment and pull-up and hanging bars at various heights.\", "
            '"description_zh_hans": null, "description_ru": null, "description_ar": null, "parent": null, "position":'
            ' "SRID=3067;POINT (391216.99082858814 6678873.1775492495)", "email": null, "telephone": "+358 9 310 8775'
            '6", "telephone_fi": "+358 9 310 87756", "telephone_sv": null, "telephone_en": null, "telephone_zh_hans":'
            ' null, "telephone_ru": null, "telephone_ar": null, "contact_type": null, "street_address": "Agronominkat'
            'u 24", "street_address_fi": "Agronominkatu 24", "street_address_sv": "Agronomgatan 24", "street_address_'
            'en": "Agronominkatu 24", "street_address_zh_hans": null, "street_address_ru": null, "street_address_ar":'
            ' null, "address_locality": "Helsinki", "address_locality_fi": "Helsinki", "address_locality_sv": "Helsin'
            'gfors", "address_locality_en": "Helsinki", "address_locality_zh_hans": null, "address_locality_ru": null'
            ', "address_locality_ar": null, "address_region": null, "postal_code": "00790", "post_office_box_num": nu'
            'll, "address_country": null, "deleted": false, "replaced_by": null, "has_upcoming_events": false, "n_eve'
            'nts": 0, "n_events_changed": true, "lft": 1, "rght": 2, "tree_id": 9015, "level": 0, "divisions": []}}]',
            # Note:
            # "image": null
            # "alt_labels": []
            # yso:p20748
            '[{"model": "events.keyword", "pk": "yso:p20748", "fields": {"image": null, "data_source": "yso", "name":'
            ' "ryhmätoiminta", "name_fi": "ryhmätoiminta", "name_sv": "gruppverksamhet", "name_en": "group activity",'
            ' "name_zh_hans": null, "name_ru": null, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T'
            '12:22:33.626Z", "last_modified_time": "2023-06-12T10:33:21.943Z", "created_by": null, "last_modified_by"'
            ': null, "publisher": "hy:kansalliskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_even'
            'ts": false, "n_events": 0, "n_events_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p6915
            '[{"model": "events.keyword", "pk": "yso:p6915", "fields": {"image": null, "data_source": "yso", "name": '
            '"leikki-ikäiset", "name_fi": "leikki-ikäiset", "name_sv": "barn i lekåldern", "name_en": "preschoolers ('
            'age group)", "name_zh_hans": null, "name_ru": null, "name_ar": null, "origin_id": null, "created_time": '
            '"2023-05-31T12:18:10.448Z", "last_modified_time": "2023-05-31T12:18:10.448Z", "created_by": null, "last_'
            'modified_by": null, "publisher": "hy:kansalliskirjasto", "aggregate": false, "deprecated": false, "has_u'
            'pcoming_events": false, "n_events": 0, "n_events_changed": true, "replaced_by": null, "alt_labels": []}}'
            "]",
            # yso:p4354
            '[{"model": "events.keyword", "pk": "yso:p4354", "fields": {"image": null, "data_source": "yso", "name": '
            '"lapset (ikäryhmät)", "name_fi": "lapset (ikäryhmät)", "name_sv": "barn (åldersgrupper)", "name_en": "ch'
            'ildren (age groups)", "name_zh_hans": null, "name_ru": null, "name_ar": null, "origin_id": null, "create'
            'd_time": "2023-05-31T12:24:01.625Z", "last_modified_time": "2023-06-12T10:33:48.230Z", "created_by": nul'
            'l, "last_modified_by": null, "publisher": "hy:kansalliskirjasto", "aggregate": false, "deprecated": fals'
            'e, "has_upcoming_events": false, "n_events": 0, "n_events_changed": true, "replaced_by": null, "alt_labe'
            'ls": []}}]',
            # yso:p26619
            '[{"model": "events.keyword", "pk": "yso:p26619", "fields": {"image": null, "data_source": "yso", "name":'
            ' "ulkoliikunta", "name_fi": "ulkoliikunta", "name_sv": "utomhusidrott", "name_en": "outdoor sports", "na'
            'me_zh_hans": null, "name_ru": null, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T12:1'
            '7:49.290Z", "last_modified_time": "2023-06-12T10:32:58.302Z", "created_by": null, "last_modified_by": nu'
            'll, "publisher": "hy:kansalliskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_events":'
            ' false, "n_events": 0, "n_events_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p4330
            '[{"model": "events.keyword", "pk": "yso:p4330", "fields": {"image": null, "data_source": "yso", "name": '
            '"uinti", "name_fi": "uinti", "name_sv": "simning", "name_en": "swimming", "name_zh_hans": null, "name_ru'
            '": null, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T12:23:48.854Z", "last_modified_'
            'time": "2023-06-12T10:33:44.205Z", "created_by": null, "last_modified_by": null, "publisher": "hy:kansal'
            'liskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_events": false, "n_events": 0, "n_e'
            'vents_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p4363
            '[{"model": "events.keyword", "pk": "yso:p4363", "fields": {"image": null, "data_source": "yso", "name": '
            '"perheet", "name_fi": "perheet", "name_sv": "familjer", "name_en": "families", "name_zh_hans": null, "na'
            'me_ru": null, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T12:23:58.750Z", "last_modi'
            'fied_time": "2023-06-12T10:33:47.063Z", "created_by": null, "last_modified_by": null, "publisher": "hy:k'
            'ansalliskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_events": false, "n_events": 0,'
            ' "n_events_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p11617
            '[{"model": "events.keyword", "pk": "yso:p11617", "fields": {"image": null, "data_source": "yso", "name":'
            ' "nuoret", "name_fi": "nuoret", "name_sv": "ungdomar", "name_en": "young people", "name_zh_hans": null, '
            '"name_ru": null, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T12:23:42.371Z", "last_m'
            'odified_time": "2023-06-12T10:33:41.234Z", "created_by": null, "last_modified_by": null, "publisher": "h'
            'y:kansalliskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_events": false, "n_events":'
            ' 0, "n_events_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p6914
            '[{"model": "events.keyword", "pk": "yso:p6914", "fields": {"image": null, "data_source": "yso", "name": '
            '"kouluikäiset", "name_fi": "kouluikäiset", "name_sv": "barn i skolåldern", "name_en": "school-age childr'
            'en", "name_zh_hans": null, "name_ru": null, "name_ar": null, "origin_id": null, "created_time": "2023-05'
            '-31T12:23:44.330Z", "last_modified_time": "2023-06-12T10:33:42.427Z", "created_by": null, "last_modified'
            '_by": null, "publisher": "hy:kansalliskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_'
            'events": false, "n_events": 0, "n_events_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p1928
            '[{"model": "events.keyword", "pk": "yso:p1928", "fields": {"image": null, "data_source": "yso", "name": '
            '"tennis", "name_fi": "tennis", "name_sv": null, "name_en": "tennis", "name_zh_hans": null, "name_ru": nu'
            'll, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T12:18:30.390Z", "last_modified_time"'
            ': "2023-05-31T12:18:30.390Z", "created_by": null, "last_modified_by": null, "publisher": "hy:kansalliski'
            'rjasto", "aggregate": false, "deprecated": false, "has_upcoming_events": false, "n_events": 0, "n_events'
            '_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p916
            '[{"model": "events.keyword", "pk": "yso:p916", "fields": {"image": null, "data_source": "yso", "name": "'
            'liikunta", "name_fi": "liikunta", "name_sv": "motion", "name_en": "physical training", "name_zh_hans": n'
            'ull, "name_ru": null, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T12:24:02.335Z", "l'
            'ast_modified_time": "2023-06-12T10:33:48.395Z", "created_by": null, "last_modified_by": null, "publisher'
            '": "hy:kansalliskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_events": false, "n_eve'
            'nts": 0, "n_events_changed": true, "replaced_by": null, "alt_labels": []}}]',
            # yso:p26740
            '[{"model": "events.keyword", "pk": "yso:p26740", "fields": {"image": null, "data_source": "yso", "name":'
            ' "ryhmäohjaus", "name_fi": "ryhmäohjaus", "name_sv": "grupphandledning", "name_en": "group guidance", "n'
            'ame_zh_hans": null, "name_ru": null, "name_ar": null, "origin_id": null, "created_time": "2023-05-31T12:'
            '15:46.275Z", "last_modified_time": "2023-05-31T12:15:46.275Z", "created_by": null, "last_modified_by": n'
            'ull, "publisher": "hy:kansalliskirjasto", "aggregate": false, "deprecated": false, "has_upcoming_events"'
            ': false, "n_events": 0, "n_events_changed": true, "replaced_by": null, "alt_labels": []}}]',
        ]
        save_cnt = 0
        for test_data in test_input_data:
            for deserialized_object in serializers.deserialize("json", test_data):
                deserialized_object.save()
                save_cnt += 1
                print(
                    "{}) Saved one data: {}".format(
                        save_cnt, deserialized_object.object.id
                    )
                )

        return save_cnt

    @pytest.mark.no_test_audit_log
    @pytest.mark.django_db
    @patch("events.importer.enkora.Enkora._request_json")
    @patch("events.importer.enkora.EnkoraImporter._get_timestamps")
    def test_importing_returns_correct_result(
        self, mock_get_timestamps, mock_request, populate_referenced_data_to_db
    ):
        # Some courses
        response_str = (
            '{"errors": [], "result": {"course_events_count": 5, "courses_count": 3, "courses": [{"reserva'
            'tion_event_group_id": "50148", "reservation_event_group_name": "EASYSPORT TENNIS, ALKEET, 7-9'
            ' -vuotiaat", "created_timestamp": "2023-03-14 12:16:37", "created_user_id": "322433", "reserv'
            'ation_group_id": "256", "reservation_group_name": "Tennis", "description": "Tenniskursseille '
            'voi ottaa oman mailan mukaan. Mailoja saa lainaan my\\u00f6s kurssilta.", "description_long":'
            ' null, "description_form": null, "season_id": "37", "season_name": "Touko- ja kes\\u00e4toimi'
            'nta 2023", "public_reservation_start": "2023-04-12 16:00:00", "public_reservation_end": "2023'
            '-06-16 00:00:00", "public_visibility_start": "2023-03-27 00:00:00", "public_visibility_end": '
            '"2023-06-16 00:00:00", "instructor_visibility_start": null, "instructor_visibility_end": null'
            ', "is_course": "1", "reservation_event_count": "100", "first_event_date": "2023-06-05 10:00:0'
            '0", "last_event_date": "2023-06-16 10:00:00", "capacity": "8", "queue_capacity": "5", "servic'
            'e_id": "99", "service_name": "Ryhm\\u00e4liikunta", "service_at_area_id": "1137", "service_at'
            '_area_name": "Ryhm\\u00e4liikunta at Latokartanon liikuntapuisto", "location_id": "62", "loca'
            'tion_name": "Latokartanon liikuntapuisto", "region_id": "2", "region_name": "Pohjoinen", "res'
            'erved_count": "5", "queue_count": "", "reservation_events": [{"reservation_event_id": "247110'
            '8", "reservation_event_name": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", "time_start": "2023-'
            '06-05 10:00:00", "time_end": "2023-06-05 11:00:00", "instructors": [{"account_id": "4629979",'
            ' "name": "H\\u00e4pp\\u00f6l\\u00e4 Tomi"}], "quantity_attended": "0"}, {"reservation_event_i'
            'd": "2471109", "reservation_event_name": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", "time_sta'
            'rt": "2023-06-06 10:00:00", "time_end": "2023-06-06 11:00:00", "instructors": [{"account_id":'
            ' "4629979", "name": "H\\u00e4pp\\u00f6l\\u00e4 Tomi"}], "quantity_attended": "0"}, {"reservat'
            'ion_event_id": "2471110", "reservation_event_name": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat"'
            ', "time_start": "2023-06-07 10:00:00", "time_end": "2023-06-07 11:00:00", "instructors": [{"a'
            'ccount_id": "4629979", "name": "H\\u00e4pp\\u00f6l\\u00e4 Tomi"}], "quantity_attended": "0"},'
            ' {"reservation_event_id": "2471111", "reservation_event_name": "EASYSPORT TENNIS, ALKEET, 7-9'
            ' -vuotiaat", "time_start": "2023-06-08 10:00:00", "time_end": "2023-06-08 11:00:00", "instruc'
            'tors": [{"account_id": "4629979", "name": "H\\u00e4pp\\u00f6l\\u00e4 Tomi"}], "quantity_atten'
            'ded": "0"}, {"reservation_event_id": "2471112", "reservation_event_name": "EASYSPORT TENNIS, '
            'ALKEET, 7-9 -vuotiaat", "time_start": "2023-06-09 10:00:00", "time_end": "2023-06-09 11:00:00'
            '", "instructors": [{"account_id": "4629979", "name": "H\\u00e4pp\\u00f6l\\u00e4 Tomi"}], "qua'
            'ntity_attended": "0"}, {"reservation_event_id": "2471113", "reservation_event_name": "EASYSPO'
            'RT TENNIS, ALKEET, 7-9 -vuotiaat", "time_start": "2023-06-12 10:00:00", "time_end": "2023-06-'
            '12 11:00:00", "instructors": [{"account_id": "4629979", "name": "H\\u00e4pp\\u00f6l\\u00e4 To'
            'mi"}], "quantity_attended": "0"}, {"reservation_event_id": "2471114", "reservation_event_name'
            '": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", "time_start": "2023-06-13 10:00:00", "time_end"'
            ': "2023-06-13 11:00:00", "instructors": [{"account_id": "4629979", "name": "H\\u00e4pp\\u00f6'
            'l\\u00e4 Tomi"}], "quantity_attended": "0"}, {"reservation_event_id": "2471115", "reservation'
            '_event_name": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", "time_start": "2023-06-14 10:00:00",'
            ' "time_end": "2023-06-14 11:00:00", "instructors": [{"account_id": "4629979", "name": "H\\u00'
            'e4pp\\u00f6l\\u00e4 Tomi"}], "quantity_attended": "0"}, {"reservation_event_id": "2471116", "'
            'reservation_event_name": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", "time_start": "2023-06-15'
            ' 10:00:00", "time_end": "2023-06-15 11:00:00", "instructors": [{"account_id": "4629979", "nam'
            'e": "H\\u00e4pp\\u00f6l\\u00e4 Tomi"}], "quantity_attended": "0"}, {"reservation_event_id": "'
            '2471117", "reservation_event_name": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat", "time_start": '
            '"2023-06-16 10:00:00", "time_end": "2023-06-16 11:00:00", "instructors": [{"account_id": "462'
            '9979", "name": "H\\u00e4pp\\u00f6l\\u00e4 Tomi"}], "quantity_attended": "0"}], "reservations"'
            ': [{"reservation_id": "5545077", "reservation_account_id": "2693748", "reservation_timestamp"'
            ': "2023-04-12 16:02:10", "reservation_status_id": "2", "reservation_status_name": "Reserved",'
            ' "reserving_user_id": "405876", "sale_event_id": "259182551"}, {"reservation_id": "5694061", '
            '"reservation_account_id": "3846275", "reservation_timestamp": "2023-05-31 12:41:31", "reserva'
            'tion_status_id": "2", "reservation_status_name": "Reserved", "reserving_user_id": "470687", "'
            'sale_event_id": "263503722"}, {"reservation_id": "5639160", "reservation_account_id": "454251'
            '3", "reservation_timestamp": "2023-05-07 11:26:06", "reservation_status_id": "2", "reservatio'
            'n_status_name": "Reserved", "reserving_user_id": "482987", "sale_event_id": "261393743"}, {"r'
            'eservation_id": "5620721", "reservation_account_id": "4985312", "reservation_timestamp": "202'
            '3-04-27 23:16:15", "reservation_status_id": "6", "reservation_status_name": "Cancelled", "res'
            'erving_user_id": "507666", "sale_event_id": "260647231"}, {"reservation_id": "5545658", "rese'
            'rvation_account_id": "5407320", "reservation_timestamp": "2023-04-12 16:03:08", "reservation_'
            'status_id": "2", "reservation_status_name": "Reserved", "reserving_user_id": "4", "sale_event'
            '_id": "259185798"}, {"reservation_id": "5545025", "reservation_account_id": "5407354", "reser'
            'vation_timestamp": "2023-04-12 16:04:45", "reservation_status_id": "6", "reservation_status_n'
            'ame": "Cancelled", "reserving_user_id": "4", "sale_event_id": "259187047"}, {"reservation_id"'
            ': "5547519", "reservation_account_id": "5407752", "reservation_timestamp": "2023-04-12 16:17:'
            '12", "reservation_status_id": "7", "reservation_status_name": "Unconfirmed", "reserving_user_'
            'id": "507611", "sale_event_id": null}, {"reservation_id": "5548021", "reservation_account_id"'
            ': "5407895", "reservation_timestamp": "2023-04-12 16:26:03", "reservation_status_id": "7", "r'
            'eservation_status_name": "Unconfirmed", "reserving_user_id": "450856", "sale_event_id": null}'
            ', {"reservation_id": "5670842", "reservation_account_id": "5461736", "reservation_timestamp":'
            ' "2023-05-21 11:34:36", "reservation_status_id": "6", "reservation_status_name": "Cancelled",'
            ' "reserving_user_id": "4", "sale_event_id": null}, {"reservation_id": "5670832", "reservation'
            '_account_id": "5461740", "reservation_timestamp": "2023-05-21 09:20:41", "reservation_status_'
            'id": "2", "reservation_status_name": "Reserved", "reserving_user_id": "4", "sale_event_id": "'
            '262588703"}, {"reservation_id": "5721399", "reservation_account_id": "5487953", "reservation_'
            'timestamp": "2023-06-12 12:43:49", "reservation_status_id": "6", "reservation_status_name": "'
            'Cancelled", "reserving_user_id": "524142", "sale_event_id": null}, {"reservation_id": "572140'
            '9", "reservation_account_id": "5487954", "reservation_timestamp": "2023-06-12 12:43:49", "res'
            'ervation_status_id": "6", "reservation_status_name": "Cancelled", "reserving_user_id": "52414'
            '2", "sale_event_id": null}, {"reservation_id": "5721419", "reservation_account_id": "5487955"'
            ', "reservation_timestamp": "2023-06-12 12:43:49", "reservation_status_id": "6", "reservation_'
            'status_name": "Cancelled", "reserving_user_id": "524142", "sale_event_id": null}, {"reservati'
            'on_id": "5721429", "reservation_account_id": "5487959", "reservation_timestamp": "2023-06-12 '
            '12:47:07", "reservation_status_id": "6", "reservation_status_name": "Cancelled", "reserving_u'
            'ser_id": "524142", "sale_event_id": null}, {"reservation_id": "5721439", "reservation_account'
            '_id": "5487960", "reservation_timestamp": "2023-06-12 12:47:24", "reservation_status_id": "6"'
            ', "reservation_status_name": "Cancelled", "reserving_user_id": "492408", "sale_event_id": nul'
            'l}, {"reservation_id": "5721449", "reservation_account_id": "5487961", "reservation_timestamp'
            '": "2023-06-12 12:48:08", "reservation_status_id": "6", "reservation_status_name": "Cancelled'
            '", "reserving_user_id": "524142", "sale_event_id": null}, {"reservation_id": "5721459", "rese'
            'rvation_account_id": "5487962", "reservation_timestamp": "2023-06-12 12:48:06", "reservation_'
            'status_id": "6", "reservation_status_name": "Cancelled", "reserving_user_id": "492408", "sale'
            '_event_id": null}, {"reservation_id": "5721469", "reservation_account_id": "5487963", "reserv'
            'ation_timestamp": "2023-06-12 12:48:15", "reservation_status_id": "6", "reservation_status_na'
            'me": "Cancelled", "reserving_user_id": "492408", "sale_event_id": null}, {"reservation_id": "'
            '5731258", "reservation_account_id": "5492160", "reservation_timestamp": "2023-06-15 15:22:23"'
            ', "reservation_status_id": "6", "reservation_status_name": "Cancelled", "reserving_user_id": '
            '"524142", "sale_event_id": null}], "fare_products": [{"fare_product_id": "3605", "fare_produc'
            't_name": "Pohjoinen Ryhm\\u00e4liikunta Lapsi 7-9 -vuotiaat", "fare_product_name_customer": "'
            'Ryhm\\u00e4liikunta", "price": "3000.0000", "vat_percentage": "10", "min_age": "6", "max_age"'
            ': "10"}], "tags": [{"tag_id": "1", "tag_name": "Lapset, nuoret ja perheet"}]}]}}'
        )
        mock_request.return_value = json.loads(response_str)

        # Time
        mock_get_timestamps.return_value = (
            datetime(2023, 6, 1, 13, 58, 20, 691641),
            timezone.now(),
        )

        # Test importing and syncing fixed set of events
        importer_options = {"single": False}
        importer = EnkoraImporter(importer_options)
        importer.import_courses()

        # Prepare for assertion
        # Get events from DB and make their modification dates fixed.
        db_events = Event.objects.all()
        for event in db_events:
            created = datetime(
                2023, 6, 16, 11, 32, 23, microsecond=1
            )  # Note: will transform into .000Z
            event.created_time = timezone.make_aware(
                created, timezone=pytz.timezone("UTC")
            )
            event.last_modified_time = timezone.make_aware(
                created, timezone=pytz.timezone("UTC")
            )

        # Expect 1 event with 10 sub-events
        assert len(db_events) == 11

        expected_fields = {
            "custom_data": None,
            "data_source": "enkora",
            "name": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat [ma, ti, ke, to, pe klo 10:00 - 11:00]",
            "name_fi": "EASYSPORT TENNIS, ALKEET, 7-9 -vuotiaat [ma, ti, ke, to, pe klo 10:00 - 11:00]",
            "name_sv": None,
            "name_en": None,
            "name_zh_hans": None,
            "name_ru": None,
            "name_ar": None,
            "origin_id": "50148",
            "created_time": datetime(2023, 6, 16, 11, 32, 23, 1, tzinfo=pytz.UTC),
            "last_modified_time": datetime(2023, 6, 16, 11, 32, 23, 1, tzinfo=pytz.UTC),
            "created_by": None,
            "last_modified_by": None,
            "user_name": None,
            "user_email": None,
            "user_phone_number": None,
            "user_organization": None,
            "user_consent": False,
            "info_url": None,
            "info_url_fi": None,
            "info_url_sv": None,
            "info_url_en": None,
            "info_url_zh_hans": None,
            "info_url_ru": None,
            "info_url_ar": None,
            "description": "<p>Tenniskursseille voi ottaa oman mailan mukaan. Mailoja saa lainaan myös "
            "kurssilta.</p><p><b>Kurssin lisätiedot</b></p>\n"
            "<p><a "
            'href="https://www.hel.fi/fi/paatoksenteko-ja-hallinto/liikuntaluuri">Liikuntaluuri</a>: '
            '<a href="tel:+358 9 310 32623">+358 9 310 32623</a></p>',
            "description_fi": "<p>Tenniskursseille voi ottaa oman mailan mukaan. Mailoja saa lainaan myös "
            "kurssilta.</p><p><b>Kurssin lisätiedot</b></p>\n"
            "<p><a "
            'href="https://www.hel.fi/fi/paatoksenteko-ja-hallinto/liikuntaluuri">Liikuntaluuri</a>: '
            '<a href="tel:+358 9 310 32623">+358 9 310 32623</a></p>',
            "description_sv": None,
            "description_en": None,
            "description_zh_hans": None,
            "description_ru": None,
            "description_ar": None,
            "short_description": None,
            "short_description_fi": None,
            "short_description_sv": None,
            "short_description_en": None,
            "short_description_zh_hans": None,
            "short_description_ru": None,
            "short_description_ar": None,
            "date_published": datetime(2023, 3, 26, 21, 0, tzinfo=pytz.UTC),
            "headline": None,
            "headline_fi": None,
            "headline_sv": None,
            "headline_en": None,
            "headline_zh_hans": None,
            "headline_ru": None,
            "headline_ar": None,
            "secondary_headline": None,
            "secondary_headline_fi": None,
            "secondary_headline_sv": None,
            "secondary_headline_en": None,
            "secondary_headline_zh_hans": None,
            "secondary_headline_ru": None,
            "secondary_headline_ar": None,
            "provider": EnkoraImporter.PROVIDER,
            "provider_fi": EnkoraImporter.PROVIDER,
            "provider_sv": None,
            "provider_en": None,
            "provider_zh_hans": None,
            "provider_ru": None,
            "provider_ar": None,
            "provider_contact_info": "Helsingin Kaupunki - Liikuntaluuri, Avoinna ma-to 13-15",
            "provider_contact_info_fi": "Helsingin Kaupunki - Liikuntaluuri, Avoinna ma-to 13-15",
            "provider_contact_info_sv": None,
            "provider_contact_info_en": None,
            "provider_contact_info_zh_hans": None,
            "provider_contact_info_ru": None,
            "provider_contact_info_ar": None,
            "publisher": EnkoraImporter.ORGANIZATION,
            "environmental_certificate": None,
            "event_status": 1,
            "publication_status": 1,
            "location": "tprek:45650",
            "location_extra_info": None,
            "location_extra_info_fi": None,
            "location_extra_info_sv": None,
            "location_extra_info_en": None,
            "location_extra_info_zh_hans": None,
            "location_extra_info_ru": None,
            "location_extra_info_ar": None,
            "environment": None,
            "start_time": datetime(2023, 6, 5, 7, 0, tzinfo=pytz.UTC),
            "end_time": datetime(2023, 6, 16, 7, 0, tzinfo=pytz.UTC),
            "has_start_time": True,
            "has_end_time": True,
            "audience_min_age": 7,
            "audience_max_age": 9,
            "super_event": None,
            "super_event_type": "recurring",
            "type_id": 2,
            "deleted": False,
            "replaced_by": None,
            "maximum_attendee_capacity": 8,
            "minimum_attendee_capacity": None,
            "enrolment_start_time": datetime(2023, 4, 12, 13, 0, tzinfo=pytz.UTC),
            "enrolment_end_time": datetime(2023, 6, 15, 21, 0, tzinfo=pytz.UTC),
            "local": False,
            "keywords": list(EnkoraImporter.ALL_COURSES_KEYWORDS)
            + [
                EnkoraImporter.SPORT_TENNIS,
                EnkoraImporter.SPORT_GROUP_EXERCISE,
            ],
            "audience": [
                "yso:p4354",  # AUDIENCE_CHILDREN
                "yso:p6914",  # AUDIENCE_SHCOOL_AGE
            ],
        }

        db_event_dict = serializers.serialize("python", db_events)[0]["fields"]
        for field_name, field_value in db_event_dict.items():
            if field_name not in expected_fields:
                continue
            if field_name in ("keywords", "audience"):
                assert sorted(field_value) == sorted(
                    expected_fields[field_name]
                ), f"Field '{field_name}' mismatch!"
            else:
                assert (
                    field_value == expected_fields[field_name]
                ), f"Field {field_name} mismatch!"
