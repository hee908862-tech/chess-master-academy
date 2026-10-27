"""Offline inventory and eMudhra trust-anchor regression guard; no network probes.

Only packaged public bundles are inspected. Custom CA overrides are reported as
present/absent, never opened or printed. This does not prove live TLS rejection.
"""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import ssl
import subprocess
import sys

MIN_CERTIFI = '2026.10.19'
MIN_PIP = '26.2.2'
# The two roots removed by the upstream certifi/Debian emergency update.
REMOVED_ROOTS = {
    'd7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4': 'AAA Certificate Services',
    '86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b': 'emSign ECC Root CA - G3',
}


def require_version(name, value, minimum):
    from pip._vendor.packaging.version import Version
    if Version(value) < Version(minimum):
        raise ValueError(f'{name} {value} is below required {minimum}')


def require_node_version(value):
    minimum = {22: '22.23.4', 24: '24.22.1', 26: '26.12.1'}
    version = value.lstrip('v').strip()
    major = int(version.split('.')[0])
    if major not in minimum:
        raise ValueError('Review advisory baseline before changing CI Node major')
    require_version('Playwright Node', version, minimum[major])


def check_roots(certificates):
    fingerprints = {hashlib.sha256(cert).hexdigest() for cert in certificates}
    if not fingerprints:
        raise ValueError('Empty trust store')
    blocked = fingerprints & REMOVED_ROOTS.keys()
    if blocked:
        raise ValueError('Removed trust anchors still present: ' + ', '.join(REMOVED_ROOTS[x] for x in sorted(blocked)))
    return len(fingerprints)


def check_bundle(path):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=str(path))
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise ValueError('TLS peer/hostname verification is not enabled')
    return check_roots(context.get_ca_certs(binary_form=True))


def inventory(system=False, ci=False):
    import pip
    from pip._vendor import certifi as bundled
    require_version('pip', pip.__version__, MIN_PIP)
    require_version('pip vendored certifi', bundled.__version__, MIN_CERTIFI)
    report = {
        'python': sys.version.split()[0], 'openssl': ssl.OPENSSL_VERSION,
        'pip': pip.__version__, 'pip_vendored_certifi': bundled.__version__,
        'pip_bundle_roots': check_bundle(bundled.where()),
        'packages': {},
        'custom_ca_override_present': any(os.environ.get(k) for k in (
            'PIP_CERT', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR')),
        'scope': 'packaged public bundles only; no live TLS or secret override validation',
    }
    for name in ('certifi', 'requests', 'httpx', 'urllib3', 'psycopg', 'psycopg-binary', 'playwright'):
        try:
            report['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report['packages'][name] = None
    if report['packages']['certifi']:
        require_version('certifi', report['packages']['certifi'], MIN_CERTIFI)
        report['certifi_bundle_roots'] = check_bundle(importlib.import_module('certifi').where())
    if system:
        report['debian_ca_certificates'] = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${Version}', 'ca-certificates'], text=True).strip()
        subprocess.run(['dpkg', '--compare-versions', report['debian_ca_certificates'],
                        'ge', '20250419+deb13u1'], check=True)
        report['system_bundle_roots'] = check_bundle('/etc/ssl/certs/ca-certificates.crt')
    if ci:
        from playwright._impl._driver import compute_driver_executable
        driver = compute_driver_executable()[0]
        report['playwright_node'] = subprocess.check_output([driver, '--version'], text=True).strip()
        require_node_version(report['playwright_node'])
        report['node_custom_ca_override_present'] = bool(os.environ.get('NODE_EXTRA_CA_CERTS'))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system', action='store_true', help='also inspect the Debian image public CA store')
    parser.add_argument('--ci', action='store_true', help='also verify the Node used for Playwright downloads')
    args = parser.parse_args()
    print(json.dumps(inventory(system=args.system, ci=args.ci), sort_keys=True), flush=True)
