# Changelog

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
