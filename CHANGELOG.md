# Changelog

## [3.14.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.13.1...linkedevents-v3.14.0) (2025-06-09)


### Features

* Add all supported languages to search ([675953e](https://github.com/City-of-Helsinki/linkedevents/commit/675953ea7412341fb295d37073b0ea46db60a488))
* Add event audience to search index ([30ed8a7](https://github.com/City-of-Helsinki/linkedevents/commit/30ed8a7fe0fb6240c71f3b06389dff03c0154abd))
* Add more Sentry configuration options ([74c9b0d](https://github.com/City-of-Helsinki/linkedevents/commit/74c9b0dee7dc92212966365f08397ace4eeffa22))
* Add support for Voikko stopword classes ([ab104da](https://github.com/City-of-Helsinki/linkedevents/commit/ab104da999e17b4fceb8b6704ca007f818d61045))
* Add time limit to event search index rebuild ([82c008f](https://github.com/City-of-Helsinki/linkedevents/commit/82c008f4ac17a6271a74ee62948a5146a059731e))
* Convert numbers to words for fi-index ([dd9cec8](https://github.com/City-of-Helsinki/linkedevents/commit/dd9cec845e72806aece405fc0e4c484cc2b895fe))
* Convert numbers to words in other languages ([984c3d2](https://github.com/City-of-Helsinki/linkedevents/commit/984c3d274fe55d086c1a8dcd7937d0a0130a8144))
* Delete EventSearchIndex in batches ([3088d48](https://github.com/City-of-Helsinki/linkedevents/commit/3088d48e52818206366c088b45fdca1008f86235))
* Enhance index creation input ([78fb391](https://github.com/City-of-Helsinki/linkedevents/commit/78fb39152fdec113b37716afc9d6444fb3f7828c))
* **events:** Command for adding kasko related keywords ([68bf0a1](https://github.com/City-of-Helsinki/linkedevents/commit/68bf0a167fab37353f5b7df9e9bae049359e03c8))
* Improve index special character handling ([97cbd54](https://github.com/City-of-Helsinki/linkedevents/commit/97cbd5416e803bdadeeccd8b604ee1a39910b4b8))
* Remove html tags and newlines from index ([0fa2b10](https://github.com/City-of-Helsinki/linkedevents/commit/0fa2b104d12a5ebe35c14d8133a7b073676557df))
* Replace non-word characters with space ([46b765f](https://github.com/City-of-Helsinki/linkedevents/commit/46b765f51f09a83322d07a416349bc5466235af9))
* Use weighted words fields ([a93483d](https://github.com/City-of-Helsinki/linkedevents/commit/a93483d1ab61fe63f6cc4f25bada790389752222))


### Bug Fixes

* Audit log production urls ([898e37d](https://github.com/City-of-Helsinki/linkedevents/commit/898e37d7e9018a188acadd42a704e678e4997a2e))
* **events:** Make EventSearchIndex modified times nullable ([1662bc2](https://github.com/City-of-Helsinki/linkedevents/commit/1662bc2b7dcc7e5ee8835d2161d08ea1895a0254))


### Dependencies

* Add num2words package ([b973528](https://github.com/City-of-Helsinki/linkedevents/commit/b9735289fd2a18f0538adc8ea7e1b6405fb503fc))
* Bump django from 4.2.20 to 4.2.21 ([5afdb4d](https://github.com/City-of-Helsinki/linkedevents/commit/5afdb4de51b18e282fa1e3939e968f6bc19810a8))
* Bump django from 4.2.21 to 4.2.22 ([219a059](https://github.com/City-of-Helsinki/linkedevents/commit/219a0594a86656f7581497ce94909f79dd10d8c3))

## [3.13.1](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.13.0...linkedevents-v3.13.1) (2025-04-16)


### Performance Improvements

* Rebuild event search index in batches ([302da48](https://github.com/City-of-Helsinki/linkedevents/commit/302da48627861c96e87823e46ef8606a4685f943))

## [3.13.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.12.0...linkedevents-v3.13.0) (2025-04-14)


### Features

* Add feature-flag for event search signals ([d3940dd](https://github.com/City-of-Helsinki/linkedevents/commit/d3940dd3d97b3e6f5f083b8635be7e08ff55e9b1))
* Auto-sync event search index on event save ([a09f96d](https://github.com/City-of-Helsinki/linkedevents/commit/a09f96d055c17d5b13c5af012e5bef059f23b86e))
* Cache Voikko analysis ([fcb8c3f](https://github.com/City-of-Helsinki/linkedevents/commit/fcb8c3f15fd7802abaa9c1a9ab49642b2ee606e4))
* Do a harakiri faster if every process has at least one waiting job ([9671a48](https://github.com/City-of-Helsinki/linkedevents/commit/9671a48c569fe7d4baa46bf0a6084da9c1aa3b51))
* **events:** Add filter param to hide super events ([595da7a](https://github.com/City-of-Helsinki/linkedevents/commit/595da7aa6ab6e5b4f6548c534aa482c41253e43b))
* **events:** Add weekday filter for events ([0259370](https://github.com/City-of-Helsinki/linkedevents/commit/02593706452f48a807deba1c747008a21a2e6835))
* **full-text-search:** Add support for clean ([14e826d](https://github.com/City-of-Helsinki/linkedevents/commit/14e826de08aaf8688a7c6ced6718ce6a2b2016bc))
* **full-text-search:** Replace ".,:;" with space ([4d817ef](https://github.com/City-of-Helsinki/linkedevents/commit/4d817ef6784e5cfbc3cfd9c7e644a970274111fe))
* **full-text-search:** Replace search model ([45623ce](https://github.com/City-of-Helsinki/linkedevents/commit/45623cec2b43a4287ffbb0ba58a3be8d303300f4))
* **full-text-search:** Update on delete-rules ([d0c7c55](https://github.com/City-of-Helsinki/linkedevents/commit/d0c7c55bc17efa3cdc7da47acc1851ddb99b69f4))
* **full-text-search:** Update search vector data ([8840646](https://github.com/City-of-Helsinki/linkedevents/commit/8840646638dfcb7e2cfb84ad748c96695a9941a0))
* **full-text-search:** Use explicit config path ([222b7a6](https://github.com/City-of-Helsinki/linkedevents/commit/222b7a65856df148fd63e47f5625a3bae471d253))
* **full-text-search:** Use morpho-dict in Voikko ([29df570](https://github.com/City-of-Helsinki/linkedevents/commit/29df570cb669988e3df653913963b7fdd27a3f65))
* Improve uwsgi options ([61d7e26](https://github.com/City-of-Helsinki/linkedevents/commit/61d7e26347bff22c12a79274b0a3204c42af9c01))
* Use simple search config ([fb6626a](https://github.com/City-of-Helsinki/linkedevents/commit/fb6626a675aa7e785eba54b378a54dc50d4bf58f))
* Use word bases instead of syllables ([6ca75d0](https://github.com/City-of-Helsinki/linkedevents/commit/6ca75d0db2535fa933181e4e9ef0f96b8b27284c))


### Bug Fixes

* Utilize GDAL/GEOS env variables in settings ([cf14b45](https://github.com/City-of-Helsinki/linkedevents/commit/cf14b457df57bcb2a054518407b5a3a1d6cb399c))


### Dependencies

* Add libvoikko and update requirements ([e356795](https://github.com/City-of-Helsinki/linkedevents/commit/e356795a1c90fd79f77a5ae258341cdbcc077b85))
* Bump uwsgi ([f2372c0](https://github.com/City-of-Helsinki/linkedevents/commit/f2372c0c8251314d057790c8b4f795ce731a90ef))


### Documentation

* **full-text-search:** Add Voikko instructions ([fe7c6c3](https://github.com/City-of-Helsinki/linkedevents/commit/fe7c6c39b42a96ef9f79d738788f7d7fbe808cce))

## [3.12.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.11.1...linkedevents-v3.12.0) (2025-03-25)


### Features

* **registration:** Add command for sending payment required with link ([f74b8be](https://github.com/City-of-Helsinki/linkedevents/commit/f74b8beca0e4fa35e037505ea5e7749523a91376))
* **registration:** Add expiry_notification_sent_at to SignUpPayment ([8da67d6](https://github.com/City-of-Helsinki/linkedevents/commit/8da67d614ad93b6af692a532fc02540740140361))
* **registration:** Do not send singup payment notification on creation ([562906d](https://github.com/City-of-Helsinki/linkedevents/commit/562906de9951155feb7a98394e034f933150bf00))


### Bug Fixes

* **events:** Prefetch images__data_source ([dbba01f](https://github.com/City-of-Helsinki/linkedevents/commit/dbba01ffe05c5e8a3049b4a8f9dd58073dac8e94))
* **events:** Prefetch images__license ([086d153](https://github.com/City-of-Helsinki/linkedevents/commit/086d1536ec76a8c966a6ecb192ad566828c8970e))

## [3.11.1](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.11.0...linkedevents-v3.11.1) (2025-03-07)


### Dependencies

* Bump cryptography from 43.0.1 to 44.0.1 ([7f840a5](https://github.com/City-of-Helsinki/linkedevents/commit/7f840a5ac4bd4e8b065020220ef7a680eaeea8b4))
* Bump django from 4.2.18 to 4.2.20 ([080658f](https://github.com/City-of-Helsinki/linkedevents/commit/080658fe3ebc1a51579af3140f3e7b8a7fdb8306))
* Bump jinja2 from 3.1.5 to 3.1.6 ([cfe16de](https://github.com/City-of-Helsinki/linkedevents/commit/cfe16de8e1a87e3372985651d527294d212afe70))

## [3.11.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.10.3...linkedevents-v3.11.0) (2025-03-05)


### Features

* **events:** Add image's license_url to api ([7128b94](https://github.com/City-of-Helsinki/linkedevents/commit/7128b94c64fc3a165e3d77938a7006a91e5f3507))

## [3.10.3](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.10.2...linkedevents-v3.10.3) (2025-02-17)


### Bug Fixes

* Lippupiste importer ([c78048f](https://github.com/City-of-Helsinki/linkedevents/commit/c78048f5a4270c56bf219e66d90b7da917296968))


### Documentation

* Improve Offer.is_free description ([75ea578](https://github.com/City-of-Helsinki/linkedevents/commit/75ea578a80546c976b0d4eed8d1e0adc7a36982f))

## [3.10.2](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.10.1...linkedevents-v3.10.2) (2025-02-04)


### Bug Fixes

* Add grace period to seat reservations expiration ([ea8ee57](https://github.com/City-of-Helsinki/linkedevents/commit/ea8ee57087ac0a8b58b39bb1373c0183e62a63ff))
* **registration:** Reapply allow customer groups with zero price ([9725673](https://github.com/City-of-Helsinki/linkedevents/commit/97256732cb546b0fd3fe4db11f319ab82cdbf938))


### Miscellaneous Chores

* Switch to City of Helsinki's ubi gdal image ([e2f504b](https://github.com/City-of-Helsinki/linkedevents/commit/e2f504b78d0f137abd59a714536e4c40ab558cab))

## [3.10.1](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.10.0...linkedevents-v3.10.1) (2025-01-15)


### Bug Fixes

* **events:** Use espoo api days back conf as int ([35abc25](https://github.com/City-of-Helsinki/linkedevents/commit/35abc251b3982a1d569643a4babe1ee5e4326e56))
* Gaierror when attempting to resolve unresolvable hostname in DEBUG ([189864c](https://github.com/City-of-Helsinki/linkedevents/commit/189864cfb90ec1a395f58feebe39b511eb9479f2))


### Dependencies

* Bump django to 4.2.18 ([3ca0b0a](https://github.com/City-of-Helsinki/linkedevents/commit/3ca0b0a3273dd7579cbb49a1295cfc35b2f3f46a))
* Bump jinja2 from 3.1.4 to 3.1.5 ([408ba97](https://github.com/City-of-Helsinki/linkedevents/commit/408ba97a63266203cdb4a381a7e05d161aedd6ba))

## [3.10.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.9.2...linkedevents-v3.10.0) (2025-01-08)


### Features

* **registrations:** Add ordering for registrations view ([36d8a0b](https://github.com/City-of-Helsinki/linkedevents/commit/36d8a0bffe78b8c7cec47b1b8c89527152ba27a9))
* Remove GDPR_DISABLE_API_DELETION setting ([4432550](https://github.com/City-of-Helsinki/linkedevents/commit/44325501e2468d783e2a837077fea5e92bd8103e))


### Bug Fixes

* Always update offer info_url when creating new registration ([6eef8ec](https://github.com/City-of-Helsinki/linkedevents/commit/6eef8ecc745918815f1f327cb45001d2b9656118))
* **registration:** Order signups by signup order in excel ([122d6cf](https://github.com/City-of-Helsinki/linkedevents/commit/122d6cf02d2308824c1e285c41fa686737fc3179))


### Reverts

* "fix(registrations): order signups in descending order" ([2f7abe8](https://github.com/City-of-Helsinki/linkedevents/commit/2f7abe85fcc279f7c17edff747228217bba3949e))

## [3.9.2](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.9.1...linkedevents-v3.9.2) (2024-12-11)


### Bug Fixes

* **registrations:** Order signups in descending order ([7b8c47f](https://github.com/City-of-Helsinki/linkedevents/commit/7b8c47ff5af05fcd2ca255f8e401ba83551d13ce))


### Dependencies

* Bump django from 4.2.16 to 4.2.17 ([ed18f6a](https://github.com/City-of-Helsinki/linkedevents/commit/ed18f6a7080bc9c3da30e439b1219ccc0a6e311c))

## [3.9.1](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.9.0...linkedevents-v3.9.1) (2024-11-05)


### Bug Fixes

* **events:** Use django qs functions in max_* and min_duration filters ([07b27b3](https://github.com/City-of-Helsinki/linkedevents/commit/07b27b38a2a1b31090b749efe2dbffdc19131c80))
* Use django's static root in swagger schema url config ([ea21c23](https://github.com/City-of-Helsinki/linkedevents/commit/ea21c231d76e3506b1b1a2af6c38e3bafc57215a))


### Dependencies

* Bump werkzeug from 3.0.4 to 3.0.6 ([c1f7909](https://github.com/City-of-Helsinki/linkedevents/commit/c1f7909e4b28f7ee3098dc2672d8b5e55fcafc18))

## [3.9.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.8.0...linkedevents-v3.9.0) (2024-10-10)


### Features

* **gdpr-api:** In deletion check for upcoming signups ([50b4e48](https://github.com/City-of-Helsinki/linkedevents/commit/50b4e4802218da13578895dd7a4ab3588608a370))
* **gdpr-api:** Prevent deletion when payments ongoing ([ac27878](https://github.com/City-of-Helsinki/linkedevents/commit/ac27878fb4de1280ff5316e8073f7ba6b6834c1e))


### Bug Fixes

* **registration:** Order signups by id ([3058608](https://github.com/City-of-Helsinki/linkedevents/commit/3058608d9c7a14bb394a7221ea5725dfeabef057))
* Remove matko importer ([4efdee9](https://github.com/City-of-Helsinki/linkedevents/commit/4efdee928eb3e29612b030455277cda6214aa432))

## [3.8.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.7.1...linkedevents-v3.8.0) (2024-09-25)


### Features

* **espoo-importer:** Restrict importing old espoo events ([5b6364d](https://github.com/City-of-Helsinki/linkedevents/commit/5b6364d357803c009fbf3410d2da72529bfadd0b))
* **events:** Add has_user_editable_resources to API ([d802de2](https://github.com/City-of-Helsinki/linkedevents/commit/d802de2ebabefd37f2358df945dd29378d06ca0c))
* **events:** Only superusers can edit org users ([eae9327](https://github.com/City-of-Helsinki/linkedevents/commit/eae9327a97bfc2e8fded58a884f850d25cd53c7d))
* **events:** Use noreply address for feedback ([40cdd77](https://github.com/City-of-Helsinki/linkedevents/commit/40cdd773132e0cd73d17f28b4f0a5a760ea7981f))
* **registration:** Add lang attr to email base template ([6bc7b3c](https://github.com/City-of-Helsinki/linkedevents/commit/6bc7b3c9baae0d8fcce5e4fc88583356e853a6ff))
* **registration:** Add title elem to email templates ([77c488e](https://github.com/City-of-Helsinki/linkedevents/commit/77c488ec6b130207d1d109845cff2a102cfb8d8e))
* **registration:** Authentication for web store webhooks ([f53ddf6](https://github.com/City-of-Helsinki/linkedevents/commit/f53ddf6e1c568c46aa81f9c17d220944ad1df9c1))
* **registration:** Check refund status from a new endpoint ([77000ed](https://github.com/City-of-Helsinki/linkedevents/commit/77000ed33cab1c97566f5a0bf0a416dde345659a))
* **registration:** Only admins can delete signup after event start_time ([9d2cdcd](https://github.com/City-of-Helsinki/linkedevents/commit/9d2cdcd39e87eb343b32422f9abeba74fc558b4b))
* **registration:** Order XLSX primarily by attendee_status ([bc345aa](https://github.com/City-of-Helsinki/linkedevents/commit/bc345aa9878245f89862d787771f5c1aa95a93c8))
* **registration:** Replace general VAT percentage with 25,5 ([73a4cf8](https://github.com/City-of-Helsinki/linkedevents/commit/73a4cf87a7f183f8b6bcbbeba6c3cc6468aa9e68))
* **registration:** Suomi.fi info text to invitation email ([4cc3610](https://github.com/City-of-Helsinki/linkedevents/commit/4cc36106d5c334b111f8d7bba36929f9e5ae4d0d))
* **registration:** User-friendlier web store API error message ([69da441](https://github.com/City-of-Helsinki/linkedevents/commit/69da441a99a8f3da2076eb2e4b46ed861dd5dcbb))


### Bug Fixes

* Allow to patch presence_status regardless of price groups ([0d7a4c0](https://github.com/City-of-Helsinki/linkedevents/commit/0d7a4c02a70563acf04d05d5474edd3e6cf993bb))
* **analytics:** Properly use the swappable knox token model ([8452c85](https://github.com/City-of-Helsinki/linkedevents/commit/8452c858ef7f7d7b90382d92d089dbd0a3c8853e))
* **analytics:** Unregister knox.AuthToken from admin site ([bae087f](https://github.com/City-of-Helsinki/linkedevents/commit/bae087f6f5becda8eeefa478e8601d999d150836))
* Change logger error to info ([bacec67](https://github.com/City-of-Helsinki/linkedevents/commit/bacec67dd46cb7c765eaf855607d42de1431c422))
* Clean all html tags from non-allowed fields ([cd2c469](https://github.com/City-of-Helsinki/linkedevents/commit/cd2c469a7ffd11b9829aff1953660e522e9d2851))
* Disable GDPR feature not working as intended ([cdfaaa5](https://github.com/City-of-Helsinki/linkedevents/commit/cdfaaa545f33754b39009e240d297ebfd8e90a4e))
* **docs:** Generate OpenAPI schema in staticbuilder ([ebc2794](https://github.com/City-of-Helsinki/linkedevents/commit/ebc2794d5a365f9a74fbac86168fb2e99c1cc340))
* **docs:** Remove unnecessary description parentheses ([b1e0a13](https://github.com/City-of-Helsinki/linkedevents/commit/b1e0a13da3741f09e311076ec701161d8bc9ba86))
* Enkora course expiry check and service image urls ([4155efe](https://github.com/City-of-Helsinki/linkedevents/commit/4155efeabacf236ed9001cb78c5ca61c44610312))
* **espoo:** Sanitize html from incoming texts ([91fca34](https://github.com/City-of-Helsinki/linkedevents/commit/91fca345b13175ad14922e4b2b8340eec70241dc))
* **events:** Fix error with x_ongoing_OR_set ([1453144](https://github.com/City-of-Helsinki/linkedevents/commit/14531444d9ffd3922a06219b844914e98dc3b5c3))
* **events:** Modeltranslation field reference fixes ([dde1994](https://github.com/City-of-Helsinki/linkedevents/commit/dde1994452c27451f87dfa987fe40aef5f3b1d1a))
* **events:** Proper ValidationError for invalid image id ([3fb28db](https://github.com/City-of-Helsinki/linkedevents/commit/3fb28dbfeac4b2093a2090554284e1d8d5a775de))
* **events:** Validation for duplicate event links ([8df7b1b](https://github.com/City-of-Helsinki/linkedevents/commit/8df7b1b201c43e052e159b663cac2bfc8be803ef))
* **regisration:** Check ancestor perms for accounts and merchants ([0510fcd](https://github.com/City-of-Helsinki/linkedevents/commit/0510fcd109aab37fba4c109d63cade3e1c0e4b6b))
* **registration:** Allow customer groups with zero price ([9a3e035](https://github.com/City-of-Helsinki/linkedevents/commit/9a3e03527b28777069591fe85d713dc5adba4808))
* **registration:** Safer mandatory field validation ([85a152d](https://github.com/City-of-Helsinki/linkedevents/commit/85a152d0ff2d68f3ea387f2962c9899289d74ef6))
* **registration:** Send VAT as decimal to Talpa ([854941b](https://github.com/City-of-Helsinki/linkedevents/commit/854941bc9fbbed7046dcc87f86c787717c8ee053))
* Terms_to_regex outputs correct regex for OR operator ([4e39021](https://github.com/City-of-Helsinki/linkedevents/commit/4e390218f46eb505ecd430a5acf51d3d0c90c6ef))


### Performance Improvements

* **registration:** Fix a couple of slow tests ([5bd124e](https://github.com/City-of-Helsinki/linkedevents/commit/5bd124e4e802e786390cfadb5c8e3f50fa2b3cd0))


### Dependencies

* Bump dependencies ([de365c1](https://github.com/City-of-Helsinki/linkedevents/commit/de365c198a7bee0b5f8bc2251e4a7fafe420f636))


### Documentation

* Add missing example for show_all_places parameter ([a7ab109](https://github.com/City-of-Helsinki/linkedevents/commit/a7ab1094269be3d2bdec70ae7235e84f9639f60e))
* **espoo:** Add docstrings, typehints, comments ([776fa83](https://github.com/City-of-Helsinki/linkedevents/commit/776fa8343ffff703fcfec459ee650535e712532a))
* Integrated swagger documentation ([834c7b3](https://github.com/City-of-Helsinki/linkedevents/commit/834c7b3fc4b7151d487d8919a1858bef1e8545d0))
* Remove links for trying out the filters in swagger docs ([0555ecb](https://github.com/City-of-Helsinki/linkedevents/commit/0555ecbac5379b8e86c7f1a6abb063071f1de23f))
* Static OpenAPI yaml generation ([c74cf99](https://github.com/City-of-Helsinki/linkedevents/commit/c74cf99eea9ab82a3331a7d98ab7e3375daa40fa))

## [3.7.1](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.7.0...linkedevents-v3.7.1) (2024-06-26)


### Bug Fixes

* Changes to Enkora place_map and error logging ([bb4328d](https://github.com/City-of-Helsinki/linkedevents/commit/bb4328d9eff713417cd7406de0d9dab32c13e744))
* Handle uncaught expection while processing Enkora event timestamps ([430522b](https://github.com/City-of-Helsinki/linkedevents/commit/430522b328bd7bcf06526b84ef6fad141d28f93d))
* **registration:** Allow large remaining capacities ([4a841e3](https://github.com/City-of-Helsinki/linkedevents/commit/4a841e399c8ff9a95c38d58174b0b71f10c05b03))

## [3.7.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.6.0...linkedevents-v3.7.0) (2024-06-24)


### Features

* **analytics:** Data_source endpoint to analytics api ([2e513f4](https://github.com/City-of-Helsinki/linkedevents/commit/2e513f4ed771a9af8f67bcf71a7b39feb59e2629))
* **registration:** Ics support for recurring events ([b355998](https://github.com/City-of-Helsinki/linkedevents/commit/b35599815a6712b4ba50b882107c0ddcddd6e94b))
* **registration:** Mandatory maximum attendee capacity ([b5e7fc2](https://github.com/City-of-Helsinki/linkedevents/commit/b5e7fc259c327c674d66360da6cf354e12f6e429))
* Scrub sensitive data through sentry_sdk ([7658f0e](https://github.com/City-of-Helsinki/linkedevents/commit/7658f0e322abe67383a6c175ef980b5b9e6ccaff))


### Bug Fixes

* Ensure correct default for checkout language ([6d388b2](https://github.com/City-of-Helsinki/linkedevents/commit/6d388b27ffa7a42ac9887762c8009a09fa059723))
* Ensure correct default for order language ([a8ce79f](https://github.com/City-of-Helsinki/linkedevents/commit/a8ce79ff60fabf12ecdca44ea314ee1c008c9de9))
* **registration:** Validate PriceGroup description max_length ([c03ccd4](https://github.com/City-of-Helsinki/linkedevents/commit/c03ccd47a4f6891d5094e189d454bec14e014f14))
* Use correct timezone for lastValidPurchaseDateTime ([2531a92](https://github.com/City-of-Helsinki/linkedevents/commit/2531a921918c4d4c908acf7b2b8c8a100640050b))
* Use geomodelserializer in analytics api ([6e2e6f0](https://github.com/City-of-Helsinki/linkedevents/commit/6e2e6f09388b79a3f54cd52815e8707f441b1901))

## [3.6.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.5.0...linkedevents-v3.6.0) (2024-06-11)


### Features

* Action endpoints for getting merchants and accounts ([4722c52](https://github.com/City-of-Helsinki/linkedevents/commit/4722c5206ec33f4c17d472a43c3a040e7d44bf2c))
* Add lang parameter to checkout URLs ([dd4da32](https://github.com/City-of-Helsinki/linkedevents/commit/dd4da325623f2a6f556b68b0294913996f73a5dc))
* Add name and address_locality fields to analytics API ([507287b](https://github.com/City-of-Helsinki/linkedevents/commit/507287bf65cfd26d2afc28e863c70a62009d1850))
* Allow multiple accounts per organization ([90e13e2](https://github.com/City-of-Helsinki/linkedevents/commit/90e13e2bc23be6d9710568eb4a701a3198a5ec91))
* Allow multiple merchants per organization ([99bbece](https://github.com/City-of-Helsinki/linkedevents/commit/99bbece707740e490182c7cfa7c67ba0b30562fd))
* Always use the partial refund Talpa endpoint ([42835c6](https://github.com/City-of-Helsinki/linkedevents/commit/42835c69d6082372c950f73daf51598172369afb))
* Check order and payment before refunds ([3da4bcb](https://github.com/City-of-Helsinki/linkedevents/commit/3da4bcb31045c177abbf78c64058dd61d7ca8ff3))
* Command for removing expired admin permissions ([244db58](https://github.com/City-of-Helsinki/linkedevents/commit/244db5837fa44762a0e91d0283eed0c776c10f88))
* Don't allow cancelling event with payments ([afa6b2b](https://github.com/City-of-Helsinki/linkedevents/commit/afa6b2bd8fa0a0ba58602645b73c496274295ab9))
* **events-api:** Match audience in keyword_* filters ([0b42f0b](https://github.com/City-of-Helsinki/linkedevents/commit/0b42f0b5e671202379b28b092181188a6a981be6))
* Filtering by modified time to data analytics api ([4c2fd93](https://github.com/City-of-Helsinki/linkedevents/commit/4c2fd935efe6d68351a1735ead206c46565b299d))
* **gdpr-api:** Add translations to gdpr data ([95120f9](https://github.com/City-of-Helsinki/linkedevents/commit/95120f984b8a1a8f48a9274f7f355dbe592cb277))
* Merchant and account selections for registration ([5bfd796](https://github.com/City-of-Helsinki/linkedevents/commit/5bfd796824cc68df175c5b50aa2b270808275bd8))
* Prevent deleting signup with refund or cancellation ([2c17cb3](https://github.com/City-of-Helsinki/linkedevents/commit/2c17cb385b2d7ccf4cdd39c4c9e28e85fcabf453))
* Refund and cancel payment through webhooks ([8ab3d92](https://github.com/City-of-Helsinki/linkedevents/commit/8ab3d920c8c25e7411a75f448bb874d6c9c38790))
* Remove webhook attendee_status update ([34420ed](https://github.com/City-of-Helsinki/linkedevents/commit/34420edd1856d9092049b162583f72fb74b557ff))
* Rest api for data analytics ([6559870](https://github.com/City-of-Helsinki/linkedevents/commit/655987048d2fd75529759fa8507d934f4cb16b55))
* Use new enkora api translations endpoint ([55c8c6f](https://github.com/City-of-Helsinki/linkedevents/commit/55c8c6f3c6db7573fc99ccd1c74fd577e21492f3))
* Vat code mapping for vat percentage ([16b67bb](https://github.com/City-of-Helsinki/linkedevents/commit/16b67bb759be5b52db4add44c21beffdaa4009d0))


### Bug Fixes

* Catch GDALException when receiving a bad srid in query params ([66a19eb](https://github.com/City-of-Helsinki/linkedevents/commit/66a19eb782ee9ca756d1ea73aaacd0b5c2b425ea))
* Don't always include all translated fields ([79051b7](https://github.com/City-of-Helsinki/linkedevents/commit/79051b716b26f07432931d815a22db06dd64f062))

## [3.5.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.4.1...linkedevents-v3.5.0) (2024-05-28)


### Features

* Add create_instant_refunds method to WebStoreOrderAPIClient ([1c9842c](https://github.com/City-of-Helsinki/linkedevents/commit/1c9842c6c66c4d22e311a91afbb88fd93814b73c))
* Add readiness and healthz endpoints ([5a6a229](https://github.com/City-of-Helsinki/linkedevents/commit/5a6a2297ad4785ab409e91890ecbb31ff3a8aa02))
* Allow partial signup payment refunds ([2e4c25a](https://github.com/City-of-Helsinki/linkedevents/commit/2e4c25a498c8de8ef4d526cb1115377b94087ecb))
* Allow registration admin to signup to closed enrolment ([56fb1ab](https://github.com/City-of-Helsinki/linkedevents/commit/56fb1ab6c509d4ede092abc0333ad8d98d28883c))
* Cancel signups on event deletion or cancellation ([a898459](https://github.com/City-of-Helsinki/linkedevents/commit/a898459ae1f0ccf08adda11389dbbc1af88ebbd5))
* Create new merchant in Talpa if Paytrail merchant ID changed ([17b31af](https://github.com/City-of-Helsinki/linkedevents/commit/17b31af63a150015311ca8161c1dc6d01aced474))
* Create product mapping if missing during signup ([ff52b15](https://github.com/City-of-Helsinki/linkedevents/commit/ff52b154f2d97d20ce5d7bfcd807702e47c50638))
* Don't require organization membership from superusers ([23ea303](https://github.com/City-of-Helsinki/linkedevents/commit/23ea3035ffb39af0a6f436ca942c85264ed080f3))
* Improve payment refund and cancellation processing ([d1b0a17](https://github.com/City-of-Helsinki/linkedevents/commit/d1b0a177f849e9f9b088ddd1ef59b7b0fc24a157))
* Move signups to attending on capacity increase ([5fd2ded](https://github.com/City-of-Helsinki/linkedevents/commit/5fd2deda47a8e97577799231693c9cf2e20dfbb2))
* Remove apikey auth from web store webhooks ([6a712f5](https://github.com/City-of-Helsinki/linkedevents/commit/6a712f5e06512daf6464a4d6a87edf6879712765))
* Remove helmet importer ([473c7bd](https://github.com/City-of-Helsinki/linkedevents/commit/473c7bd121e4e2e1dcad8115df60fcd2cb17b3f5))
* Sentry returns git commit hash ([5b7b4b4](https://github.com/City-of-Helsinki/linkedevents/commit/5b7b4b4e03205be5d4ca6b3c1e535c474dc9370a))
* Store orderItemId from web store response ([d59dbee](https://github.com/City-of-Helsinki/linkedevents/commit/d59dbee24d89835ff729138f53528548adac8977))
* Update product mapping if Talpa merchant ID is changed ([5e91cec](https://github.com/City-of-Helsinki/linkedevents/commit/5e91cecb7c8cf0e43ae2279db658989ef6013910))
* Use LINKED_EVENTS_UI_URL as merchant.url ([5e885c0](https://github.com/City-of-Helsinki/linkedevents/commit/5e885c0113b5e2ca7e0e843f4f6d7b9f33e60ecc))


### Bug Fixes

* Change Enkora importer date interval and yso mappings ([46b7e4a](https://github.com/City-of-Helsinki/linkedevents/commit/46b7e4a368bf62cf1bfdd24364ffbd789d23ce6b))


### Dependencies

* Upgrade dependencies ([2949084](https://github.com/City-of-Helsinki/linkedevents/commit/2949084a37cdf81577733d86aab59224d6c16601))


### Documentation

* Update importer documentation ([d0e8dc0](https://github.com/City-of-Helsinki/linkedevents/commit/d0e8dc05c03dd3e5a1f23be9e22aa916c3dbd249))

## [3.4.1](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.4.0...linkedevents-v3.4.1) (2024-05-02)


### Bug Fixes

* Broken graph.preferredLabel call in YSO importer ([a7c012b](https://github.com/City-of-Helsinki/linkedevents/commit/a7c012b4ca16622f09c116832a057c9e9d5dbd48))
* Use https for importing yso keywords ([1f95b42](https://github.com/City-of-Helsinki/linkedevents/commit/1f95b424e865d46428f6ffcbe44c9a679eea689e))
* Use https for tprek importer ([d0c5f42](https://github.com/City-of-Helsinki/linkedevents/commit/d0c5f429554bcf9860d8ba14d7d9cf5abe9570d4))

## [3.4.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.3.1...linkedevents-v3.4.0) (2024-04-23)


### Features

* Accounts to API ([7cf83a7](https://github.com/City-of-Helsinki/linkedevents/commit/7cf83a73722058bfe8058c4a7398f9b3b1d66bac))
* Add client for the Talpa Product Experience API ([196b278](https://github.com/City-of-Helsinki/linkedevents/commit/196b278a3be8a875912a996712c98c4bc1182981))
* Add refund request to WebStorePaymentAPIClient ([fcd6073](https://github.com/City-of-Helsinki/linkedevents/commit/fcd60736d0332a08868c908c0778deba76691dae))
* Add Talpa accounts to Django admin ([2258030](https://github.com/City-of-Helsinki/linkedevents/commit/2258030b16497f51a9236b8bd16f1380422d7ca9))
* Create Talpa product mapping and accounting for paid registrations ([4988630](https://github.com/City-of-Helsinki/linkedevents/commit/4988630b30c51e11243838610cc7eaa238f88441))
* Don't update merchant in Talpa if data has not changed ([f2cd537](https://github.com/City-of-Helsinki/linkedevents/commit/f2cd537df410f598cf4ad23892ae8512985e3c65))
* Further Enkora importer improvements as agreed with KUVA/Liikunta ([4579fdd](https://github.com/City-of-Helsinki/linkedevents/commit/4579fddc3cabf54a0f25c13e3d79fa432378e0bd))
* Refund cancelled paid signups ([0fc3431](https://github.com/City-of-Helsinki/linkedevents/commit/0fc34311f4134cdacce2bbe9996a8def02e605d8))


### Bug Fixes

* Add missing recurring event cancellation and refund texts ([dfd24c2](https://github.com/City-of-Helsinki/linkedevents/commit/dfd24c2f4b9a6d1a95673cf6055443a502ede1cb))
* Add missing recurring event payment expiration texts ([5fec021](https://github.com/City-of-Helsinki/linkedevents/commit/5fec021454a5256ee4b290865427773a1bbfb0d1))
* Allow multiple product mappings for merchants and accounts ([fc37fe7](https://github.com/City-of-Helsinki/linkedevents/commit/fc37fe73a094aa535b076b8f4aeeb11e1907bc02))
* Financial admin with admin role can POST or PUT organization data ([ea035a5](https://github.com/City-of-Helsinki/linkedevents/commit/ea035a5ea0a705f1acd8aa71943fe64a1c027f88))
* Flaky notification date and time format tests ([cac3f3d](https://github.com/City-of-Helsinki/linkedevents/commit/cac3f3d88201eebca6a9fa3839024a715a79dda8))
* Improve Swedish translations ([45d3e49](https://github.com/City-of-Helsinki/linkedevents/commit/45d3e49e81ef157fd54c12c717449f6e6e523144))
* Make merchant_id a read_only field in API ([dec1438](https://github.com/City-of-Helsinki/linkedevents/commit/dec1438487a7a4d5a7c05706fda6bc578838e39b))
* Mark transferred signup with payment as attending ([360ac2d](https://github.com/City-of-Helsinki/linkedevents/commit/360ac2dc8378003cd688c1a6fad4dd0cfd2334e7))
* Signup unpaid order cancellation ([234f917](https://github.com/City-of-Helsinki/linkedevents/commit/234f917a7cc386c2c4bd6823e8d7ec7c9305c40d))


### Dependencies

* Upgrade dependencies to newer versions ([0816f1f](https://github.com/City-of-Helsinki/linkedevents/commit/0816f1fc7656c0f3b273aae72caf6bb401bf9d6a))

## [3.3.1](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.3.0...linkedevents-v3.3.1) (2024-03-27)


### Bug Fixes

* Use sort in error log ([5adbb7d](https://github.com/City-of-Helsinki/linkedevents/commit/5adbb7d05990069d14db2fc589641d5b12ac7fe9))

## [3.3.0](https://github.com/City-of-Helsinki/linkedevents/compare/linkedevents-v3.2.0...linkedevents-v3.3.0) (2024-03-26)


### Features

* Allow only same VAT percentage for registration price groups ([f715b0c](https://github.com/City-of-Helsinki/linkedevents/commit/f715b0c09ca675f1f874c22a19024406f724365c))
* Use the same VAT percentage in registration price group admin ([845a705](https://github.com/City-of-Helsinki/linkedevents/commit/845a705ca0927cde50db989aa270cef632d50852))


### Bug Fixes

* Make espoo importer ignore orphaned events ([e06238c](https://github.com/City-of-Helsinki/linkedevents/commit/e06238c03b81e23e49182d2934fa35d791ec36d5))
