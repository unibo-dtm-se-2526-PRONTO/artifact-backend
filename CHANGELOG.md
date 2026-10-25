## [1.0.1](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/compare/1.0.0...1.0.1) (2026-10-25)

### Bug Fixes

* **booking:** lock the appointment when cancelling it ([b15524a](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/b15524a68d00a7f142dfa4f1a1be4e36ebce0c8c))
* **deps:** update django, djangorestframework and sqlparse for known vulnerabilities ([401deae](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/401deae779573ecc366c0251e1b356bd241a9643))
* **docker:** keep nested caches, env variants and local data out of the build context ([4231a03](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/4231a036065f9f99029ababc66cc1aa7bb5e2434))
* **faq:** keep english questions translated in the admin on re-import ([2a94e7a](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/2a94e7a6cfb312685e58983d35489e67fe3c0d00))
* **i18n:** keep the default language a plain string for mypy ([a95995f](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/a95995fa9efb6905578ededd0cba7aec1488cc42))

### Documentation

* **faq:** clarify what a re-import keeps of the English texts ([d35c17e](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d35c17ed9c110ad13e3f1103c610bdc79bc22155))

### Tests

* **booking:** assert the second booking of a full slot is refused ([6301aa4](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/6301aa4da2c80fc2531e4f445f805ec7277a8dc7))

### General maintenance

* clean README ([9c6a5e7](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/9c6a5e705f823306f2bb49cce6abfc3687c2ff26))
* **docker:** ignore ruff cache and coverage data in the build context ([e160ee7](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/e160ee7c3c69b4b8328990c22b7d27ae0aa263eb))
* **docker:** publish the backend port on localhost only ([2b1ef7c](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/2b1ef7c3d74f44a6586dd40d7b6ca5dbf08d4291))
* **docker:** publish the frontend port on localhost only ([783b7f9](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/783b7f9da99b731d915ced8d2675e4727b31672f))
* remove leftover tutorial comments ([d3f872a](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d3f872af995e8c0238c3a45ef4e0853b9913eaaa))
* **renovate:** open dependency PRs against develop ([96529bb](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/96529bbe8846e82f004de7f606c6aa491cfc79a4))

### Style improvements

* **tests:** merge nested with statements ([bb38fe4](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/bb38fe4de3ba572eaca56f909d2d78c7c1fd2b64))

### Refactoring

* **booking:** reuse the weekday labels in the e-mails ([7c028b4](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/7c028b4e92548e0dec2457cdd95e175e810fec75))
* define the supported languages once ([a00ae81](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/a00ae81af38686b771decc1407c714113382d494))
* **faq:** drop the unused matcher parameter of find_best_match ([db64c03](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/db64c03ac8372f993f8c2585041237e97e7a6e38))
* read the supported languages from the enum outside the API layer ([a408121](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/a408121d5bb890eabfe209159bc25aafea2cc206))
* **settings:** compute the test-run flag once ([0247326](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/02473268cdfc4fb757cef10b6b9bd738a757c2da))

## 1.0.0 (2026-10-15)

### Features

* **accounts:** activate accounts on registration ([4a02681](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/4a02681ad4d010285107eddfd8e852b71e98c781))
* **accounts:** add ADMIN role and shared enums ([b38c4d2](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/b38c4d216f927a1c4c3553aacdf4fc7f4fb83974))
* **accounts:** record matricola and degree programme for students ([37ab15e](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/37ab15e05412d5bb62810e77fd16438e5cff17e4))
* **accounts:** record the last login on token login ([a1ed9e9](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/a1ed9e9ba49e984dfcec903f261514779da80631))
* **accounts:** require email verification before login ([2569ef9](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/2569ef9aad6a17440da257cde8ca0e2f85dc48e9))
* **accounts:** require first and last name ([32acc23](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/32acc239f062d8d920e86a29d34c909743ccfc21))
* **accounts:** require names for every user ([763b2d0](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/763b2d0bf7ec758b2d2b45ffbf2cda99b9692e5d))
* **booking:** add email for appointment booking and cancellation ([b139c95](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/b139c951df38543c73dd894c5a69729f3ff8ba56))
* **booking:** add Office, EmployeeProfile and Appointment ([c5536dd](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/c5536ddd6cae27f79e4782698c5418e6ac52aeb8))
* **booking:** add tests on concurrency ([d402f2f](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d402f2f55bcb2eeea920a4a51009b98d8f59c9f8))
* **booking:** add the seed_offices command ([3925fd2](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/3925fd2a18e26556ed67c4977fe1abcf225f75ed))
* **booking:** let the assigned employee complete an appointment ([d3fe0ce](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d3fe0cef99509fb997d1806e6e5ec2428bc49afd))
* **booking:** record the faq that was not satisfactory to the student ([428047b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/428047bb527287cb70c77c9c1fc9082b58c25c16))
* bootstrap Django project and set up Postgres connection ([d00fa5b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d00fa5b0eb1dd2f75a764212ed05ea8121834e6b))
* containerize backend with Docker and docker-compose ([1938784](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/193878450c2ef820cc801e9e49d4b5c60a03a155))
* **docker:** run the frontend in docker compose ([a9ddd93](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/a9ddd93ac56070a9a31a07bf9c7df71d18f7be4b))
* **faq:** add bilingual FAQ model ([ca3a8bb](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/ca3a8bbf42e708cf4be64662dfe02a695646682f))
* **faq:** add the import_faqs command ([f9f8cf6](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/f9f8cf68c805532841ffb328d67d81af93067a23))
* **faq:** allow faq questions longer than 255 characters ([b56431c](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/b56431ce750d2b20b01996580932334be8fd9032))
* **faq:** anonymise personal data before import ([62c9387](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/62c93876ddc62abac3e2082125d1759ad5f54481))
* **faq:** expose the questions api ([61f4722](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/61f472264a21337e25353af57ec454d903fce438))
* **faq:** match questions semantically when full-text search finds nothing ([495d1f4](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/495d1f40f6df242989e318ef698da80acb5fc4d6))
* **faq:** match questions with postgres full-text search ([d85cb2a](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d85cb2a580148503e338ed4740a7911e563fbd74))
* **faq:** record the questions students ask ([c8158f0](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/c8158f0d1faa17804af504f8a57a38846025ed8e))
* **health:** report the running version ([28865bc](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/28865bc7d9553a8f437e2d7b794eba5ca00f3ea7))

### Bug Fixes

* **accounts:** base the admin add form on the one that sets usable passwords ([52fe7c9](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/52fe7c9683d01d3458dd5b17a09e980d6884e709))
* added tests ([0322e98](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/0322e98a0af13069ed8d7a7db036d1ff3cda8260))
* **booking:** lock the employee when booking and when withdrawing a shift ([5b34130](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/5b3413091c8959d5e7e9a997a5c55bf75f2f6b3d))
* **faq:** import the english answers from the spreadsheet ([2135f2b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/2135f2b7b70aeade299ef6820be1504f74a8b07a))
* **faq:** keep the vector index when a rebuild fails halfway ([a5873ae](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/a5873ae2d6dac88d6ddfa27c3e84940dd61d960d))
* finish setup to publish the package to TestPyPI or PyPI ([7c4b78f](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/7c4b78f00fda66b0b03c4526253631549f91c55c))
* publish the package to TestPyPI or PyPI ([aeb0b7a](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/aeb0b7a9cc383d2b60677ec485bc42a406cd0bca))
* read DEBUG and ALLOWED_HOST fromt the enviroment ([6776ac6](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/6776ac6b7cc1bad7fa7761db191f2726bb46edd3))
* remove choice of office when asking a question ([ab7045d](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/ab7045df390a45c8258f4c305523aa7122aa26c5))
* set the booking timetable in Europe/Rome ([6159c25](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/6159c25b0d5faa80045c898d7337894fa3e5b39d))
* **settings:** read the version from the package metadata when installed ([844a09b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/844a09b56fc148906605019f11ca1157e41dd156))
* type-check and compile the faq app in CI ([75d4103](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/75d4103fe0d13b2513565b68820d12d37f241563))
* update readme ([b7abfb4](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/b7abfb44916fa2cf0dab6f1550e9b02a4ef1606c))

### Documentation

* add chromadb and fastembed ([1bdce53](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/1bdce53f86ebdd5484a50287854bddcff4ec1733))
* **ci:** explain what triggers the deploy workflow ([2ca9148](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/2ca9148122f13045e9a6f7742491ffa48d47005c))
* describe how the booking rules hold under simultaneous requests ([c53469f](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/c53469f7c2ffea25ee268a6b2c4fdb0a5bf9d357))
* describe how the package is published ([66b890b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/66b890b6956c764e4b68329919593d45d6844ccf))
* describe semantic faq matching ([4f3b48b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/4f3b48b9bc421db3f97edbd51a72ff754537db1d))
* describe the faq import and its anonymisation rules ([e38686d](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/e38686dc3803ceca5d3c4c3fb7f9f2414c1ee6d7))
* describe the frontend service of docker compose ([d8bb3fa](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d8bb3fa33f3f876732b8dcccd346bd626b1b34dd))
* describe the offices app and the office relation ([f406c4d](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/f406c4deeaa9fe74a58c6d9d405a439df81e629e))
* describe the student profile and the user data model ([2a27dbb](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/2a27dbbc982fd62fdbd1bca0a6b5eff393f88e05))
* document the booking and FAQ endpoints ([134712e](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/134712ec1da5180146f0689e036cdbdc179397c3))
* document the personal data of accounts and how passwords and tokens are handled ([e6abf12](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/e6abf12338d895256300c28c9bdba8a9b1209afc))
* document the questions api and the faq matching ([f13d069](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/f13d0691f6b1318f3e1c8c95888797086175df2f))
* explain how the offices are created ([78709d8](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/78709d8e91082d61ae4241e93f443e9decd18d7b))
* replace the template readme with the pronto setup, tests and ci ([fdd6cf7](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/fdd6cf7a76bd4b4067dbc4f5dd5e439d6228eed5))
* update readme ([ecb05c1](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/ecb05c1289ecb69c932740484606d10a058a66cf))
* update readme ([408a6b6](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/408a6b64b51e68093885bc1f4641192b2c042248))
* updated deploy configuration ([de58667](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/de586670c8fb7ca97f29f58310672332e23921c5))

### Tests

* **accounts:** cover how passwords are validated, stored and kept out of responses ([213ffbf](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/213ffbf4575ca84fde0f708c569aace7685f235a))
* **booking:** run the booking and shift races on postgres ([072eda1](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/072eda16c7d5747627101977f61c6899c10a20a1))
* **faq:** add test for english answers ([ec080b8](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/ec080b8a9983338e72490d02b1f568c4a23c818e))
* **faq:** backdate the first timestamp so the update test is deterministic ([8829508](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/88295081f4c1c2555e215f4a7d2ef7c6b468c98f))
* remove the database example test of the template ([75f2805](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/75f28058b2b9d2976c3318d08674668fc72e0029))
* set up TDD layout and health-check ([4cc26ba](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/4cc26ba4a246e4dddc2056e0d25d72e6aa6c603a))

### Build and continuous integration

* check that commit messages are Conventional Commits ([dca43bc](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/dca43bc8b9058f692cebdba64ec84b4fd4f8df16))
* **commitlint:** skip the release pull request from develop ([6f3b97e](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/6f3b97ef4955adc621f07e00555538313363fa8b))
* **deploy:** author release commits as the owner of RELEASE_TOKEN ([17d9e8a](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/17d9e8a5b1cb4441603a459b920f53db17aed3af))
* measure coverage on the postgres run, the only one that reaches the matching ([727d2b7](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/727d2b7bfb2deca56bea510d3d963086e06b908a))
* migrate the neon database when a change lands on develop ([3a6e50b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/3a6e50b4b1deea68445bc3b4d6bd2c42a520491b))
* package the project and its apps for PyPI ([e050152](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/e050152316d80e19ee9810a63f15f32c35800795))
* **release:** release as the GitHub Actions bot instead of a personal token ([7cda70e](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/7cda70eb29a5d92a4ff559bfc92be0382911456d))
* run chroma in docker compose ([d9796ae](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/d9796ae3f13f5d7f60db99a8d02cd63e53a53b70))

### General maintenance

* add .env.example ([bbf722b](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/bbf722b8561f509ef480fc8c0b902ed9ea36b3de))
* align tooling with Django layout ([8bfe0ab](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/8bfe0abd713150cdda08d6612372c2e8403c8170))
* **build:** pin a single poetry version in the dockerfile ([c29d2fe](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/c29d2fe8d25236b6de14d56bbc2bba48d80fc47e))
* **ci:** run the tests against postgres on python 3.12 only ([5c3929a](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/5c3929a978f7bcd72042e4ff3ccd3fc66b18c8fc))
* **docker:** add a postgres db service to compose ([e4c9266](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/e4c926640302f2aa713a780106ebecf6fe13fe65))
* initialise repository renaming files and removing init workflow [skip ci] ([e3dbd38](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/e3dbd383bc0140d205c2f828886d55ff567f0fc3))
* name the project pronto-helpdesk ([a4a4c11](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/a4a4c113abb84d379cc4314e042e7f1e3d636bfb))
* **release:** stop publishing to pypi ([761b648](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/761b648d4503ae8b017c941348a5335cdc5560ca))
* reset the version and changelog inherited from the template ([0fd69ee](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/0fd69ee0649c707ee3b9078b5c1d11bf1a1f091b))
* **settings:** choose the test database from the environment ([3343d89](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/3343d89e04f14c0b945bc42eef809f8ce1465fcd))

### Refactoring

* **accounts:** move student data to a student profile ([c1cd90c](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/c1cd90c5411fb991548f06f9024312be6c9ccdf0))
* **accounts:** remove the email verification ([f7eb024](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/f7eb0247bb2cdaae445ece5337cef6eb23694697))
* **faq:** link faqs and questions to their office ([59567b1](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/59567b157649e93c88aea5bc1940c9d122726402))
* move the role permissions to pronto so faq can use them ([96cb1fa](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/96cb1fab3725693f57d8d3872c8f0d9b67a770f2))
* **offices:** move the office model to its own app ([525838e](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/525838e28e94b1922e702c542d25f01b430fc0b6))
* **test:** share the accounts and faq fixtures ([cf0249d](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend/commit/cf0249ddba2feb32a86c29d74124a02463667865))
