# Changelog

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
