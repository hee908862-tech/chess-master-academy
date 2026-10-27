# eMudhra CA maintenance (2026-10-27)

This change preserves application behavior, accounts, scores, content and the existing automatic Render deployment. It does not modify Render environment variables, secrets, database TLS settings or the host trust store. No application HTTP client or runtime Certifi dependency is added.

## Evidence before the change

- Render's [official advisory](https://render.com/docs/advisory-emudhra) distinguishes Docker system trust from libraries that bundle roots, and specifies Certifi >=2026.10.19 where applicable. Only a test originating in the running service with its client can demonstrate deployed certificate rejection.
- The live PR54 build, commit `7e59f2a96fd5c15360cc57659c064f14ce2d7b74`, resolved `python:3.12-slim` to `sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704`. Render reused its apt and pip layers. An unchanged Dockerfile alone is not evidence of vulnerability.
- An isolated read-only container using that exact public base digest reports Python 3.12.15, pip 25.0.1, pip-vendored Certifi 2024.08.30, ca-certificates 20250419+deb13u1, and OpenSSL 3.5.7-1~deb13u3. The [Debian DSA-6572-1 tracker](https://security-tracker.debian.org/tracker/DSA-6572-1) identifies that CA package as fixed. The system bundle excludes the two removed roots, while pip's old bundled Certifi includes them.
- A newly pulled base digest `sha256:e70237b264442328526ff29d6b3c43bd8abcf6cbab78a949322fb69b7d91d6b6` has Python 3.12.16 but still pip 25.0.1 / bundled Certifi 2024.08.30. Updating the base alone is insufficient for pip.
- [pip documentation](https://pip.pypa.io/en/stable/topics/https-certificates/) states that modern pip combines system roots with its bundled Certifi. Installing a separate application Certifi does not replace pip's vendored copy. [pip 26.2.2 release notes](https://pip.pypa.io/en/stable/news/) explicitly update the vendored Certifi to 2026.10.19.
- Application requirements have no Requests/HTTPX/Certifi dependency. Reviewed application Python and top-level browser assets contain no outbound application HTTP client; browser API requests are same-origin. Optional PostgreSQL uses psycopg/libpq and may use separately configured database TLS. Connection secrets and effective DB TLS policy were not inspected or changed.
- CI separately installs HTTPX/Playwright. A local fresh resolution gave HTTPX 0.28.1, Certifi 2026.10.23, Playwright 1.64.1 and its bundled Node v24.19.0. CI therefore explicitly uses advisory-patched Node 24.22.1 for Playwright's HTTPS downloads. GitHub-managed action runtimes and the user's browser trust store are outside this repository's attestation.

## Remediation and verification

1. Explicitly install/upgrade Debian ca-certificates and enforce its known patched minimum. This invalidates the old apt layer without changing trusted roots manually.
2. Bootstrap pip 26.2.2 with a pinned wheel hash from [PyPI release metadata](https://pypi.org/pypi/pip/26.2.2/json), requiring hashes, a binary wheel and no dependencies. The hash check also protects the initial download made by the old pip. Maintain this pin and hash together for future updates.
3. Before application dependency downloads, inspect the patched pip's actual vendored bundle. Repeat the inventory after installation, including optional installed Certifi and resolved dependency versions. Check the system bundle and the two removed root SHA-256 fingerprints. Checks fail closed for stale versions, forbidden roots, empty or malformed bundles. They do not make network requests.
4. Preserve the existing BuildKit `pip_ca_bundle` secret interface. Neither its contents nor any override value is printed or read for inspection. The audit reports only whether a CA override exists and explicitly excludes it from its attestation. An operator supplying custom trust must validate that bundle separately; this check cannot certify it.
5. CI bootstraps the same pip, requires patched Certifi for HTTPX, selects patched Node for Playwright, and verifies the actually selected versions. An additional job builds the production Dockerfile and audits its resulting image with networking disabled. Existing full regression assertions remain intact.

`tests/fixtures/removed_ca_roots.pem` contains only the two public CA certificates from Certifi 2026.7.22 (Mozilla CA data), no private keys. Its SHA-256 fingerprints match the two entries in the verifier. It is a negative regression fixture and is not copied into the production image or installed into any trust store.

## Observed checks and limits

- Local offline trust/version checks and Docker COPY/import tests: 20 passed.
- Local production-image build: not completed. BuildKit could not resolve `deb.debian.org`; apt then could not locate Stockfish. No DNS/network bypass was attempted. CI's actual image build is the independent build check.
- Local baseline public-base probes to both advisory test endpoints returned proxy `403` errors, not TLS certificate rejection. The positive-control `pypi.org` probe failed because that container did not trust the environment's proxy certificate. These results are inconclusive and are not counted as security success. No insecure flag, trusted-host exception, proxy bypass, extra trust injection or secret read was used.
- No live-service shell/exec capability is exposed by the available Render connector. Build inventories and final deploy identity can be verified, but production-origin rejection at the advisory endpoints, runtime custom CA overrides, and effective PostgreSQL certificate verification cannot be certified by these offline checks.
- Final CI counts, actual resolved image inventory, merged/deployed commits and rollout state are recorded in the PR body after completion. Do not equate a successful build or missing roots with a live endpoint handshake test.
