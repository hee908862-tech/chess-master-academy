"""Offline trust-anchor/version guards, not deployed TLS endpoint tests."""
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys

import certifi
import pytest

from scripts.verify_ca_trust import check_bundle, check_roots, require_node_version, require_version

ROOT = Path(__file__).resolve().parents[1]


def test_removed_public_roots_are_rejected():
    # Public certificates from certifi 2026.7.22, not private keys or secrets.
    with pytest.raises(ValueError, match='Removed trust anchors still present'):
        check_bundle(ROOT / 'tests/fixtures/removed_ca_roots.pem')


def test_current_certifi_is_nonempty_and_excludes_removed_roots():
    assert check_bundle(certifi.where()) > 50


def test_empty_store_is_not_success():
    with pytest.raises(ValueError, match='Empty trust store'):
        check_roots([])


def test_invalid_pem_is_not_success(tmp_path):
    path = tmp_path / 'invalid.pem'
    path.write_text('not a certificate')
    with pytest.raises(ssl.SSLError):
        check_bundle(path)


@pytest.mark.parametrize('version', ['2024.8.30', '2026.7.22', '2026.10.18'])
def test_old_certifi_is_rejected(version):
    with pytest.raises(ValueError, match='below required'):
        require_version('certifi', version, '2026.10.19')


@pytest.mark.parametrize('version', ['v20.20.0', 'v22.23.3', 'v24.19.0', 'v26.12.0'])
def test_unpatched_playwright_node_is_rejected(version):
    with pytest.raises(ValueError):
        require_node_version(version)


@pytest.mark.parametrize('version', ['v22.23.4', 'v24.22.1', 'v26.12.1'])
def test_advisory_node_baselines_are_accepted(version):
    require_node_version(version)


def test_inventory_does_not_open_or_expose_override_secrets(tmp_path):
    secret = tmp_path / 'private-ca-sentinel'
    secret.write_text('PRIVATE CONTENT MUST NOT BE READ AS A CA OR PRINTED')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_ca_trust.py')],
                            env={**os.environ, 'PIP_CERT': str(secret), 'SSL_CERT_FILE': str(secret)},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['custom_ca_override_present'] is True
    assert str(secret) not in result.stdout and 'PRIVATE CONTENT' not in result.stdout
    assert report['pip_vendored_certifi'] >= '2026.10.19'
