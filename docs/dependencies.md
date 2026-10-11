# Foundation dependency inventory

## Frontend design-system addition — 2026-10-11

Authorized D19 justification before installation: Instrument Sans for compact,
readable interface labels and JetBrains Mono for distinguishable numeric data.
These self-hosted Latin variable fonts replace network font services/system-only
typography; they add no JavaScript runtime. Both npm manifests report OFL-1.1.
Only normal Latin WOFF2 files ship; sans alone is preloaded. Both installed
LICENSE files were read and copied to frontend/public/fonts for distribution.
Measured installed file totals are below (excluding filesystem allocation).
TanStack Query5.104.1 is already installed; no additional fetching, UI, icon,
motion, map or accessibility package is needed for this foundation.

| Added package | Exact version | License | Purpose | Registry unpacked bytes | Measured installed bytes | Selected Latin WOFF2 bytes |
|---|---|---|---|---:|---:|---:|
| @fontsource-variable/instrument-sans |5.3.0|OFL-1.1|Interface variable sans|424,093|424,093|30,092|
| @fontsource-variable/jetbrains-mono |5.3.0|OFL-1.1|Tabular numeric/technical variable mono|203,866|203,866|40,404|

Selected font payload: **70,496 bytes**, within the 90,000-byte cap; no font
JavaScript or unused language/style subsets are imported. The production build
checks its emitted font files and preload path. npm registry audit on 2026-10-11
reported **0 vulnerabilities** across 218 dependencies; this is an advisory
snapshot, not a guarantee. No other dependency was installed for this task.

D19 justification before installation: use only the approved D14-D16/D19 groups.
MapLibre and other map packages are deferred. No global packages are installed.
Python dependencies live in backend/.venv; npm dependencies in frontend/node_modules;
caches and browser binaries stay in this project.

- Django 5.2 LTS and DRF provide the required backend/API foundation.
- HTTPX and django-cors-headers are the approved transport/CORS components; HTTPX
  is installed for later adapters and performs no provider calls here.
- Gunicorn/WhiteNoise are approved Linux hosting/static components; Gunicorn is
  not used as the local Windows server.
- pytest/pytest-django, Ruff, mypy/django-stubs provide tests/lint/format/types.
- React/React DOM, strict TypeScript, Vite/plugin-react and TanStack Query are the
  approved frontend stack; Query manages the bounded, explicit health request.
- ESLint, @eslint/js, typescript-eslint and globals supply the approved ESLint
  tooling for TypeScript; core ESLint formatting rules avoid another formatter.
- @types/react, @types/react-dom and @types/node supply compile-time types.
- Vitest, Testing Library/react/DOM and jsdom are the approved test/DOM group.
- @playwright/test supplies the approved real browser test. Browser binaries are
  local dev artifacts; no CLI or global package is added.
- Python auditing uses a standard-library OSV query tool; npm audit is built
  into npm. No additional audit dependency is installed.
- The project-venv bootstrap pip25.0.1 had published OSV advisories; updated the
  existing project-local installer to pip26.2.1 (MIT), not a global install or
  new application dependency. The exact lock includes this installer version.


## Recorded locks and methodology

Measured on Windows, 2026-10-10. backend/requirements.in pins approved direct roots; backend/requirements.lock pins all 32 installed Python distributions including pip. frontend/package-lock.json locks the npm tree; all 191 installed npm packages are listed below. Optional packages for other operating systems remain in the npm lock and are not falsely counted as installed on Windows. No map package is installed.

Licenses come from installed distribution metadata/license files and npm package manifests (including license expressions). BSD classifiers for asgiref, colorama, HTTPX, pytest-django and sqlparse were resolved to BSD-3-Clause by inspecting their three-clause license files. Parent project licenses do not replace bundled third-party notices. License files stay with the installed packages; bundled notices remain in the packages.

Sizes below are actual uncompressed bytes on disk, not download size or per-package bundle estimates. Python uses installed RECORD files located within the project venv (including recorded bytecode/scripts); npm recursively sums each installed package excluding nested node_modules to avoid double counting. Folder totals include interpreter/metadata/generated cache files and can change after use. The build size is measured separately because tree shaking/transitives prevent accurate attribution of bundle bytes to individual packages.

Django 5.2 LTS was chosen with matching django-stubs5.2. TypeScript5.9.3 is compatible with the installed typescript-eslint range; choosing a newer incompatible major was avoided. ESLint10 replaces the unsupported9 bootstrap selection. No application dependency outside approved D14-D16/D19 groups was introduced.

## Python

| Name | Exact version | License | Purpose / approved relationship | Installed bytes |
|---|---|---|---|---:|
| anyio | 4.15.1 | MIT | transitive: httpcore, httpx | 1,283,253 |
| asgiref | 3.12.1 | BSD-3-Clause | transitive: Django, django-cors-headers | 156,527 |
| ast_serialize | 0.12.1 | MIT | transitive: mypy | 2,712,395 |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | transitive: httpcore, httpx | 253,951 |
| colorama | 0.4.6 | BSD-3-Clause | transitive: Pygments, pytest | 169,090 |
| Django | 5.2.18 | BSD-3-Clause | required backend/config/runtime; no custom framework | 30,435,728 |
| django-cors-headers | 4.9.0 | MIT | explicit CORS middleware; avoids custom middleware | 53,684 |
| django-stubs | 5.2.9 | MIT | Django-aware static types/plugin | 1,571,615 |
| django-stubs-ext | 6.1.2 | MIT | transitive: django-stubs | 37,520 |
| djangorestframework | 3.18.3 | BSD-3-Clause | approved future API validation/serialization; avoids manual schemas | 3,382,483 |
| gunicorn | 26.2.0 | MIT | Linux WSGI hosting; replaces production runserver | 2,052,710 |
| h11 | 0.16.0 | MIT License | transitive: httpcore | 185,611 |
| httpcore | 1.0.9 | BSD-3-Clause | transitive: httpx | 626,603 |
| httpx | 0.28.1 | BSD-3-Clause | approved future provider transport; avoids custom HTTP code | 743,478 |
| idna | 3.20 | BSD-3-Clause | transitive: anyio, httpx | 626,232 |
| iniconfig | 2.3.1 | MIT | transitive: pytest | 36,832 |
| librt | 0.16.0 | MIT | transitive: mypy | 331,915 |
| mypy | 2.4.0 | MIT | strict Python type checking | 42,525,037 |
| mypy_extensions | 1.1.0 | MIT | transitive: mypy | 20,975 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | transitive: gunicorn, pytest | 995,308 |
| pathspec | 1.1.1 | Mozilla Public License 2.0 (MPL 2.0) | transitive: mypy | 305,264 |
| pip | 26.2.1 | MIT | existing venv installer, upgraded to remediate known advisories | 11,020,651 |
| pluggy | 1.6.0 | MIT License | transitive: pytest | 137,210 |
| Pygments | 2.21.0 | BSD-2-Clause | transitive: httpx, pytest | 8,639,538 |
| pytest | 9.1.1 | MIT | backend test runner; replaces custom runner | 3,218,088 |
| pytest-django | 4.14.0 | BSD-3-Clause | Django integration fixtures | 162,674 |
| ruff | 0.17.0 | MIT | Python lint and format; avoids separate formatter | 26,761,957 |
| sqlparse | 0.6.0 | BSD-3-Clause | transitive: Django | 474,511 |
| types-PyYAML | 6.0.12.20260906 | Apache-2.0 | transitive: django-stubs | 70,576 |
| typing_extensions | 4.16.0 | PSF-2.0 | transitive: anyio, asgiref, django-stubs, django-stubs-ext, mypy, pathspec | 349,457 |
| tzdata | 2026.5 | Apache-2.0 | transitive: Django | 588,336 |
| whitenoise | 6.12.0 | MIT | production static serving; avoids separate static server | 121,175 |


## npm (installed Windows packages)

| Name | Exact version | License | Purpose / approved relationship | Installed bytes |
|---|---|---|---|---:|
| @asamuzakjp/css-color | 7.1.4 | MIT | transitive of approved frontend/runtime/tooling | 395,240 |
| @asamuzakjp/dom-selector | 9.2.4 | MIT | transitive of approved frontend/runtime/tooling | 306,232 |
| @babel/code-frame | 7.29.7 | MIT | transitive of approved frontend/runtime/tooling | 34,632 |
| @babel/helper-validator-identifier | 7.29.7 | MIT | transitive of approved frontend/runtime/tooling | 48,813 |
| @babel/runtime | 7.29.10 | MIT | transitive of approved frontend/runtime/tooling | 247,215 |
| @bramus/specificity | 2.4.3 | MIT | transitive of approved frontend/runtime/tooling | 802,282 |
| @cacheable/memory | 2.2.0 | MIT | transitive of approved frontend/runtime/tooling | 118,851 |
| @cacheable/utils | 2.5.0 | MIT | transitive of approved frontend/runtime/tooling | 208,385 |
| @csstools/color-helpers | 6.1.2 | MIT-0 | transitive of approved frontend/runtime/tooling | 59,270 |
| @csstools/css-calc | 3.4.3 | MIT | transitive of approved frontend/runtime/tooling | 46,678 |
| @csstools/css-color-parser | 4.2.6 | MIT | transitive of approved frontend/runtime/tooling | 65,145 |
| @csstools/css-parser-algorithms | 4.0.2 | MIT | transitive of approved frontend/runtime/tooling | 35,880 |
| @csstools/css-syntax-patches-for-csstree | 1.1.15 | MIT-0 | transitive of approved frontend/runtime/tooling | 85,690 |
| @csstools/css-tokenizer | 4.0.2 | MIT | transitive of approved frontend/runtime/tooling | 41,172 |
| @eslint-community/eslint-utils | 4.10.1 | MIT | transitive of approved frontend/runtime/tooling | 506,119 |
| eslint-visitor-keys | 3.4.3 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 32,278 |
| @eslint-community/regexpp | 4.12.2 | MIT | transitive of approved frontend/runtime/tooling | 473,994 |
| @eslint/config-array | 0.23.5 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 328,752 |
| @eslint/config-helpers | 0.7.0 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 80,219 |
| @eslint/core | 1.2.1 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 92,054 |
| @eslint/js | 10.0.1 | MIT | ESLint recommended rules | 15,687 |
| @eslint/object-schema | 3.0.5 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 67,104 |
| @eslint/plugin-kit | 0.7.3 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 110,535 |
| @exodus/bytes | 1.16.0 | MIT | transitive of approved frontend/runtime/tooling | 435,337 |
| @humanfs/core | 0.19.2 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 72,759 |
| @humanfs/node | 0.16.8 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 44,472 |
| @humanfs/types | 0.15.0 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 15,241 |
| @humanwhocodes/module-importer | 1.0.1 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 21,177 |
| @humanwhocodes/retry | 0.4.3 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 65,711 |
| @jridgewell/resolve-uri | 3.1.2 | MIT | transitive of approved frontend/runtime/tooling | 53,153 |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT | transitive of approved frontend/runtime/tooling | 96,626 |
| @jridgewell/trace-mapping | 0.3.31 | MIT | transitive of approved frontend/runtime/tooling | 146,724 |
| @keyv/bigmap | 1.3.1 | MIT | transitive of approved frontend/runtime/tooling | 45,279 |
| @keyv/serialize | 1.1.1 | MIT | transitive of approved frontend/runtime/tooling | 8,107 |
| @oxc-project/types | 0.153.0 | MIT | transitive of approved frontend/runtime/tooling | 44,596 |
| @playwright/test | 1.64.0 | Apache-2.0 | real Chromium smoke runner; no global CLI | 28,542 |
| @rolldown/binding-win32-x64-msvc | 1.2.13 | MIT | transitive of approved frontend/runtime/tooling | 21,404,614 |
| @rolldown/pluginutils | 1.0.1 | MIT | transitive of approved frontend/runtime/tooling | 25,693 |
| @tanstack/query-core | 5.104.1 | MIT | transitive of approved frontend/runtime/tooling | 3,193,597 |
| @tanstack/react-query | 5.104.1 | MIT | bounded health request lifecycle; avoids hand-built state/cache | 1,731,356 |
| @testing-library/dom | 10.4.2 | MIT | DOM queries used by React tests | 2,467,302 |
| @testing-library/react | 16.3.3 | MIT | observable React component testing | 339,581 |
| @types/aria-query | 5.0.4 | MIT | transitive of approved frontend/runtime/tooling | 11,983 |
| @types/chai | 5.2.3 | MIT | transitive of approved frontend/runtime/tooling | 92,011 |
| @types/deep-eql | 4.0.2 | MIT | transitive of approved frontend/runtime/tooling | 4,762 |
| @types/esrecurse | 4.3.1 | MIT | transitive of approved frontend/runtime/tooling | 5,347 |
| @types/estree | 1.0.9 | MIT | transitive of approved frontend/runtime/tooling | 26,153 |
| @types/json-schema | 7.0.15 | MIT | transitive of approved frontend/runtime/tooling | 31,748 |
| @types/node | 24.9.1 | MIT | Node/tool configuration types | 2,512,945 |
| @types/react | 19.3.0 | MIT | React component types | 408,108 |
| @types/react-dom | 19.3.0 | MIT | React DOM types | 32,862 |
| @typescript-eslint/eslint-plugin | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 2,177,312 |
| ignore | 7.0.12 | MIT | transitive of approved frontend/runtime/tooling | 120,949 |
| @typescript-eslint/parser | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 16,172 |
| @typescript-eslint/project-service | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 16,188 |
| @typescript-eslint/scope-manager | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 421,823 |
| @typescript-eslint/tsconfig-utils | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 9,460 |
| @typescript-eslint/type-utils | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 93,730 |
| @typescript-eslint/types | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 114,548 |
| @typescript-eslint/typescript-estree | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 391,764 |
| @typescript-eslint/utils | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 200,310 |
| @typescript-eslint/visitor-keys | 8.71.1 | MIT | transitive of approved frontend/runtime/tooling | 13,508 |
| @vitejs/plugin-react | 6.1.2 | MIT | React Vite transforms/Fast Refresh | 46,296 |
| @vitest/mocker | 5.0.3 | MIT | transitive of approved frontend/runtime/tooling | 196,289 |
| @vitest/spy | 5.0.3 | MIT | transitive of approved frontend/runtime/tooling | 40,721 |
| acorn | 8.19.0 | MIT | transitive of approved frontend/runtime/tooling | 568,532 |
| acorn-jsx | 5.3.2 | MIT | transitive of approved frontend/runtime/tooling | 24,385 |
| ajv | 6.15.0 | MIT | transitive of approved frontend/runtime/tooling | 938,206 |
| ansi-regex | 5.0.1 | MIT | transitive of approved frontend/runtime/tooling | 5,609 |
| aria-query | 5.3.0 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 192,147 |
| assertion-error | 2.0.1 | MIT | transitive of approved frontend/runtime/tooling | 5,832 |
| balanced-match | 4.0.4 | MIT | transitive of approved frontend/runtime/tooling | 17,584 |
| bidi-js | 1.1.0 | MIT | transitive of approved frontend/runtime/tooling | 171,249 |
| brace-expansion | 5.0.12 | MIT | transitive of approved frontend/runtime/tooling | 84,997 |
| cacheable | 2.5.0 | MIT | transitive of approved frontend/runtime/tooling | 229,831 |
| chai | 6.3.0 | MIT | transitive of approved frontend/runtime/tooling | 149,545 |
| cross-spawn | 7.0.6 | MIT | transitive of approved frontend/runtime/tooling | 16,094 |
| css-tree | 3.2.1 | MIT | transitive of approved frontend/runtime/tooling | 1,362,649 |
| csstype | 3.2.3 | MIT | transitive of approved frontend/runtime/tooling | 1,253,449 |
| data-urls | 8.0.0 | MIT | transitive of approved frontend/runtime/tooling | 8,329 |
| debug | 4.4.3 | MIT | transitive of approved frontend/runtime/tooling | 42,793 |
| decimal.js | 10.6.0 | MIT | transitive of approved frontend/runtime/tooling | 284,347 |
| deep-is | 0.1.4 | MIT | transitive of approved frontend/runtime/tooling | 8,114 |
| dequal | 2.0.3 | MIT | transitive of approved frontend/runtime/tooling | 14,229 |
| detect-libc | 2.1.2 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 26,437 |
| dom-accessibility-api | 0.5.16 | MIT | transitive of approved frontend/runtime/tooling | 257,340 |
| entities | 8.1.0 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 330,191 |
| es-module-lexer | 2.3.2 | MIT | transitive of approved frontend/runtime/tooling | 175,452 |
| escape-string-regexp | 4.0.0 | MIT | transitive of approved frontend/runtime/tooling | 3,790 |
| eslint | 10.12.0 | MIT | lint and format rules; no extra formatter | 2,947,964 |
| eslint-scope | 9.1.2 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 173,495 |
| eslint-visitor-keys | 5.0.1 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 31,942 |
| espree | 11.2.0 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 95,658 |
| esquery | 1.7.0 | BSD-3-Clause | transitive of approved frontend/runtime/tooling | 1,097,084 |
| esrecurse | 4.3.0 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 13,527 |
| estraverse | 5.3.0 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 37,094 |
| estree-walker | 3.0.3 | MIT | transitive of approved frontend/runtime/tooling | 17,599 |
| esutils | 2.0.3 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 50,582 |
| expect-type | 1.4.0 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 138,163 |
| fast-deep-equal | 3.1.3 | MIT | transitive of approved frontend/runtime/tooling | 12,966 |
| fast-json-stable-stringify | 2.1.0 | MIT | transitive of approved frontend/runtime/tooling | 16,959 |
| fast-levenshtein | 2.0.6 | MIT | transitive of approved frontend/runtime/tooling | 9,444 |
| fdir | 6.5.0 | MIT | transitive of approved frontend/runtime/tooling | 53,291 |
| file-entry-cache | 11.1.5 | MIT | transitive of approved frontend/runtime/tooling | 89,300 |
| find-up | 5.0.0 | MIT | transitive of approved frontend/runtime/tooling | 11,761 |
| flat-cache | 6.1.23 | MIT | transitive of approved frontend/runtime/tooling | 56,568 |
| flatted | 3.4.4 | ISC | transitive of approved frontend/runtime/tooling | 38,501 |
| glob-parent | 6.0.2 | ISC | transitive of approved frontend/runtime/tooling | 7,719 |
| globals | 17.13.0 | MIT | ESLint browser/Node global definitions | 257,100 |
| hashery | 1.5.1 | MIT | transitive of approved frontend/runtime/tooling | 335,985 |
| hookified | 1.15.1 | MIT | transitive of approved frontend/runtime/tooling | 239,514 |
| html-encoding-sniffer | 7.0.0 | MIT | transitive of approved frontend/runtime/tooling | 16,940 |
| ignore | 5.3.2 | MIT | transitive of approved frontend/runtime/tooling | 53,630 |
| imurmurhash | 0.1.4 | MIT | transitive of approved frontend/runtime/tooling | 11,887 |
| is-extglob | 2.1.1 | MIT | transitive of approved frontend/runtime/tooling | 6,217 |
| is-glob | 4.0.3 | MIT | transitive of approved frontend/runtime/tooling | 13,609 |
| is-potential-custom-element-name | 1.0.1 | MIT | transitive of approved frontend/runtime/tooling | 3,918 |
| isexe | 2.0.0 | ISC | transitive of approved frontend/runtime/tooling | 10,956 |
| js-tokens | 4.0.0 | MIT | transitive of approved frontend/runtime/tooling | 15,069 |
| jsdom | 30.1.2 | MIT | browser DOM environment for Vitest | 5,533,799 |
| json-schema-traverse | 0.4.1 | MIT | transitive of approved frontend/runtime/tooling | 19,564 |
| json-stable-stringify-without-jsonify | 1.0.1 | MIT | transitive of approved frontend/runtime/tooling | 14,224 |
| keyv | 5.6.0 | MIT | transitive of approved frontend/runtime/tooling | 117,340 |
| levn | 0.4.1 | MIT | transitive of approved frontend/runtime/tooling | 24,947 |
| lightningcss | 1.33.0 | MPL-2.0 | transitive of approved frontend/runtime/tooling | 513,814 |
| lightningcss-win32-x64-msvc | 1.33.0 | MPL-2.0 | transitive of approved frontend/runtime/tooling | 9,501,288 |
| locate-path | 6.0.0 | MIT | transitive of approved frontend/runtime/tooling | 7,017 |
| lru-cache | 11.5.3 | BlueOak-1.0.0 | transitive of approved frontend/runtime/tooling | 3,334,485 |
| lz-string | 1.5.0 | MIT | transitive of approved frontend/runtime/tooling | 175,825 |
| magic-string | 1.4.3 | MIT | transitive of approved frontend/runtime/tooling | 94,290 |
| mdn-data | 2.27.1 | CC0-1.0 | transitive of approved frontend/runtime/tooling | 732,388 |
| minimatch | 10.2.6 | BlueOak-1.0.0 | transitive of approved frontend/runtime/tooling | 536,122 |
| ms | 2.1.3 | MIT | transitive of approved frontend/runtime/tooling | 6,721 |
| nanoid | 3.3.20 | MIT | transitive of approved frontend/runtime/tooling | 26,808 |
| natural-compare | 1.4.0 | MIT | transitive of approved frontend/runtime/tooling | 5,647 |
| obug | 2.2.1 | MIT | transitive of approved frontend/runtime/tooling | 29,669 |
| optionator | 0.9.4 | MIT | transitive of approved frontend/runtime/tooling | 50,157 |
| p-limit | 3.1.0 | MIT | transitive of approved frontend/runtime/tooling | 7,754 |
| p-locate | 5.0.0 | MIT | transitive of approved frontend/runtime/tooling | 7,240 |
| parse5 | 8.0.1 | MIT | transitive of approved frontend/runtime/tooling | 337,099 |
| path-exists | 4.0.0 | MIT | transitive of approved frontend/runtime/tooling | 3,919 |
| path-key | 3.1.1 | MIT | transitive of approved frontend/runtime/tooling | 4,553 |
| picocolors | 1.1.1 | ISC | transitive of approved frontend/runtime/tooling | 6,373 |
| picomatch | 4.0.7 | MIT | transitive of approved frontend/runtime/tooling | 93,759 |
| playwright | 1.64.0 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 5,033,957 |
| playwright-core | 1.64.0 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 13,655,528 |
| postcss | 8.5.29 | MIT | transitive of approved frontend/runtime/tooling | 220,365 |
| prelude-ls | 1.2.1 | MIT | transitive of approved frontend/runtime/tooling | 36,741 |
| pretty-format | 27.5.1 | MIT | transitive of approved frontend/runtime/tooling | 70,072 |
| ansi-styles | 5.2.0 | MIT | transitive of approved frontend/runtime/tooling | 13,596 |
| punycode | 2.3.1 | MIT | transitive of approved frontend/runtime/tooling | 33,514 |
| qified | 0.10.1 | MIT | transitive of approved frontend/runtime/tooling | 108,244 |
| hookified | 2.2.0 | MIT | transitive of approved frontend/runtime/tooling | 345,861 |
| react | 19.3.0 | MIT | required presentation runtime | 178,663 |
| react-dom | 19.3.0 | MIT | required React browser renderer | 8,063,782 |
| react-is | 17.0.2 | MIT | transitive of approved frontend/runtime/tooling | 24,767 |
| require-from-string | 2.0.2 | MIT | transitive of approved frontend/runtime/tooling | 3,422 |
| rolldown | 1.2.13 | MIT | transitive of approved frontend/runtime/tooling | 878,776 |
| saxes | 6.0.0 | ISC | transitive of approved frontend/runtime/tooling | 163,774 |
| scheduler | 0.28.0 | MIT | transitive of approved frontend/runtime/tooling | 82,659 |
| semver | 7.8.5 | ISC | transitive of approved frontend/runtime/tooling | 101,065 |
| shebang-command | 2.0.0 | MIT | transitive of approved frontend/runtime/tooling | 2,556 |
| shebang-regex | 3.0.0 | MIT | transitive of approved frontend/runtime/tooling | 2,828 |
| source-map-js | 1.2.2 | BSD-3-Clause | transitive of approved frontend/runtime/tooling | 142,723 |
| std-env | 4.3.0 | MIT | transitive of approved frontend/runtime/tooling | 18,175 |
| tinybench | 6.2.1 | MIT | transitive of approved frontend/runtime/tooling | 86,831 |
| tinyexec | 1.3.1 | MIT | transitive of approved frontend/runtime/tooling | 26,969 |
| tinyglobby | 0.2.17 | MIT | transitive of approved frontend/runtime/tooling | 39,288 |
| tldts | 7.4.18 | MIT | transitive of approved frontend/runtime/tooling | 2,921,911 |
| tldts-core | 7.4.18 | MIT | transitive of approved frontend/runtime/tooling | 371,083 |
| tough-cookie | 6.0.2 | BSD-3-Clause | transitive of approved frontend/runtime/tooling | 759,679 |
| tr46 | 7.0.0 | MIT | transitive of approved frontend/runtime/tooling | 231,811 |
| ts-api-utils | 2.5.0 | MIT | transitive of approved frontend/runtime/tooling | 352,842 |
| type-check | 0.4.0 | MIT | transitive of approved frontend/runtime/tooling | 21,167 |
| typescript | 5.9.3 | Apache-2.0 | strict compile-time API safety | 23,625,066 |
| typescript-eslint | 8.71.1 | MIT | ESLint TypeScript parser/rules | 42,688 |
| undici | 8.11.2 | MIT | transitive of approved frontend/runtime/tooling | 1,927,456 |
| undici-types | 7.16.0 | MIT | transitive of approved frontend/runtime/tooling | 110,131 |
| uri-js | 4.4.1 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 469,879 |
| vite | 8.3.4 | MIT | dev server and production bundle; replaces custom bundler | 2,376,813 |
| vitest | 5.0.3 | MIT | non-watch unit/component runner | 2,759,444 |
| w3c-xmlserializer | 6.0.0 | MIT | transitive of approved frontend/runtime/tooling | 18,139 |
| webidl-conversions | 8.0.1 | BSD-2-Clause | transitive of approved frontend/runtime/tooling | 23,494 |
| whatwg-mimetype | 5.0.0 | MIT | transitive of approved frontend/runtime/tooling | 42,618 |
| whatwg-url | 17.2.0 | MIT | transitive of approved frontend/runtime/tooling | 120,000 |
| which | 2.0.2 | ISC | transitive of approved frontend/runtime/tooling | 9,975 |
| why-is-node-running | 3.2.1 | MIT | transitive of approved frontend/runtime/tooling | 8,564 |
| word-wrap | 1.2.5 | MIT | transitive of approved frontend/runtime/tooling | 11,845 |
| xml-name-validator | 5.0.0 | Apache-2.0 | transitive of approved frontend/runtime/tooling | 13,574 |
| xmlchars | 2.2.0 | MIT | transitive of approved frontend/runtime/tooling | 58,957 |
| yocto-queue | 0.1.0 | MIT | transitive of approved frontend/runtime/tooling | 6,027 |


## Local browser artifacts

The approved Playwright tool downloaded these dev-only artifacts into .cache/ms-playwright; none is an application dependency or committed binary. Exact revisions are from installed playwright-core/browsers.json.
| Artifact | Exact version/revision | License / evidence | Purpose | Installed bytes |
|---|---|---|---|---:|
| Chrome for Testing | 156.0.8078.4 / 1248 | Google Chrome executable terms plus third-party open-source notices | Optional headed Chromium test browser | 457,625,672 |
| Chrome Headless Shell | 156.0.8078.4 / 1248 | Chromium BSD-3-Clause plus bundled third-party licenses in LICENSE.headless_shell | Actual health smoke browser | 290,917,991 |
| FFmpeg | Playwright revision1013 | LGPL-2.1, bundled COPYING.LGPLv2.1 | Playwright media helper | 4,025,246 |
| Winldd | Playwright revision1007 | MIT and Apache-2.0 headers in upstream PrintDeps.cpp | Windows browser DLL validation helper | 258,560 |

[Chrome terms](https://www.google.com/chrome/terms/) govern the executable separately from its open-source components. [Winldd source](https://github.com/microsoft/playwright/blob/main/browser_patches/winldd/PrintDeps.cpp) carries both source license headers. Local browser notices were inspected.

## Measured environment and build totals

| Path/artifact | Actual bytes |
|---|---:|
| backend/.venv | 141,213,284 |
| frontend/node_modules | 143,633,255 |
| frontend/dist | 254,860 |
| backend/staticfiles | 3,746,584 |
| .cache/ms-playwright (four artifact directories) | 752,827,469 |
| frontend/dist/assets/index-CBmlUaUZ.js gzip (Python gzip default compression) | 77,683 |
| frontend/dist/assets/index-D90qzfyQ.css gzip (Python gzip default compression) | 222 |
| frontend/dist/index.html gzip (Python gzip default compression) | 266 |

Vite reports JS254.17kB (gzip78.72kB), CSS0.29kB (gzip0.22kB), HTML0.39kB (gzip0.26kB). These are foundation-shell numbers; the future lazy map and analysis payload still require D23 measurement. Environments/caches/build/browser artifacts are ignored and never staged.

## Advisory audit evidence

2026-10-10: project-local dev.py audit ran the standard-library OSV PyPI query-batch checker and npm audit. Final results: **32 PyPI packages checked, 0 affected packages; npm found 0 vulnerabilities**, both exit0. OSV covers published indexed PyPI advisories, not an exhaustive security review; npm uses its registry advisory database. Raw Python response is the ignored .cache/python-audit.json; npm printed its actual result.
Initial OSV detected pip25.0.1 (12 advisory records, some aliases may describe the same issue). Updated only the existing project venv installer to pip26.2.1 (MIT), recorded it in the lock, and reran the audit successfully. No pip-audit, additional audit library, global npm/Python package or provider/map package was installed.

## MapLibre GL JS — map task, 2026-10-12

D13/D19 approved direct addition: **maplibre-gl 6.14.0**, **BSD-3-Clause**,
exactly pinned in package.json/package-lock.json. It replaces the development SVG
map placeholder with the real vector-map engine. No React wrapper or other direct
package was added. Registry metadata and installed LICENSE.txt were inspected.
Installed MapLibre package size: **28,028,509 bytes** (recursive file sum).
The install added one direct package and 22 required transitive packages below;
these support vector decoding, tiling, triangulation, spatial lookup and style validation.

Production measurement uses Node zlib.gzipSync defaults (level 6), not an estimate:
engine lazy JS **286,023 bytes gzip**, separate lazy worker **144,614 bytes gzip**,
combined lazy JS **430,637 bytes gzip**; initial JS **108,852 bytes gzip**.
Map CSS is lazy-loaded too. Vite emits its normal >500 kB uncompressed chunk warning;
the map remains excluded from the 200 kB initial-JS budget. No claim of a lazy-map
size budget pass is made. The build guard verifies the E2E hook is absent in production.
One registry runtime audit (`npm audit --omit=dev`) returned **0 vulnerabilities**;
dev-only advisories and the unchanged backend environment were not re-audited here.

| Required transitive package | Exact locked version | Installed license | Measured package bytes |
|---|---|---|---:|
| @mapbox/jsonlint-lines-primitives | 2.0.3 | MIT | 59,337 |
| @mapbox/point-geometry | 1.1.0 | ISC | 24,180 |
| @mapbox/tiny-sdf | 2.3.0 | BSD-2-Clause | 12,970 |
| @mapbox/unitbezier | 1.0.0 | BSD-3-Clause | 4,479 |
| @mapbox/vector-tile | 3.0.0 | BSD-3-Clause | 17,650 |
| @maplibre/geojson-vt | 6.1.2 | ISC | 487,867 |
| @maplibre/maplibre-gl-style-spec | 26.4.4 | ISC | 9,753,063 |
| @maplibre/mlt | 1.3.0 | MIT OR Apache-2.0 | 1,256,616 |
| @maplibre/vt-pbf | 4.3.2 | MIT | 27,760 |
| @types/geojson | 7946.0.16 | MIT | 9,514 |
| earcut | 3.2.4 | ISC | 109,815 |
| gl-matrix | 3.4.4 | MIT | 780,912 |
| json-stringify-pretty-compact | 4.0.0 | MIT | 7,412 |
| kdbush | 4.1.0 | ISC | 39,122 |
| minimist | 1.2.8 | MIT | 54,477 |
| murmurhash-js | 1.0.0 | MIT | 6,344 |
| pbf | 5.1.2 | BSD-3-Clause | 90,141 |
| potpack | 2.1.0 | ISC | 8,467 |
| protocol-buffers-schema | 3.6.1 | MIT | 68,888 |
| quickselect | 3.0.0 | ISC | 5,287 |
| resolve-protobuf-schema | 2.1.0 | MIT | 5,243 |
| tinyqueue | 3.0.0 | ISC | 4,937 |

