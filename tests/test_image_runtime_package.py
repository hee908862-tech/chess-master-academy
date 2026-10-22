"""Docker COPY payload checks without Docker; not an image build/PG validation."""
import ast
import fnmatch
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def staged_copy(root, target):
    # Fail closed if Dockerfile switches to syntax this deliberately small reader
    # cannot represent. All current COPY sources are explicit, context-local paths.
    patterns = [p.strip() for p in (root / '.dockerignore').read_text().splitlines()
                if p.strip() and not p.lstrip().startswith('#')]
    assert not any(p.startswith('!') for p in patterns), 'Extend ignore handling for negation'

    def ignored(path):
        rel = path.relative_to(root).as_posix()
        parts = rel.split('/')
        return any(fnmatch.fnmatch(rel, p.rstrip('/')) or
                   any(fnmatch.fnmatch(part, p.rstrip('/')) for part in parts)
                   for p in patterns)

    for line in (root / 'Dockerfile').read_text().splitlines():
        if not line.startswith('COPY '):
            continue
        args = shlex.split(line)[1:]
        assert args and not any(x.startswith('--') or x.startswith('[') for x in args)
        sources, destination = args[:-1], args[-1]
        assert not destination.startswith('/') and '..' not in Path(destination).parts
        dest = target / destination
        for source in sources:
            assert not any(c in source for c in '*?['), 'Extend reader for COPY glob'
            src = root / source
            assert src.exists(), source
            assert not ignored(src), f'COPY source excluded by .dockerignore: {source}'
            if src.is_dir():
                for file in src.rglob('*'):
                    if file.is_file() and not ignored(file):
                        out = dest / file.relative_to(src)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file, out)
            else:
                out = dest / src.name if destination in ('.', './') or destination.endswith('/') else dest
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out)


@pytest.fixture(scope='module')
def package(tmp_path_factory):
    stage = tmp_path_factory.mktemp('image-copy')
    staged_copy(ROOT, stage)
    return stage


def test_copy_covers_local_runtime_imports(package):
    local = {p.stem for p in ROOT.glob('*.py')}
    missing = set()
    for file in package.glob('*.py'):
        for node in ast.walk(ast.parse(file.read_text())):
            imports = ([x.name.split('.')[0] for x in node.names] if isinstance(node, ast.Import)
                       else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            missing.update((file.name, name) for name in imports if name in local and not (package / (name + '.py')).is_file())
    assert not missing, f'Local runtime imports absent from Docker COPY: {sorted(missing)}'


def test_server_import_from_copy_payload_only(package):
    env = {**os.environ, 'DATABASE_URL': '', 'SQLITE_FILE': str(package / 'smoke.sqlite3'),
           'CMA_JOURNEY_INDEX': str(package / 'journey-index.json.gz'), 'PYTHONPATH': ''}
    # Execute the actual index-generation RUN command in this isolated payload.
    built = subprocess.run([sys.executable, 'build_journey_index.py'], cwd=package, env=env,
                           capture_output=True, text=True, timeout=90)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([sys.executable, '-c',
        "from pathlib import Path; import server, board_facts; "
        "assert Path(server.__file__).parent == Path.cwd(); "
        "assert Path(board_facts.__file__).parent == Path.cwd(); "
        "assert callable(server.app); print('COPY payload server import PASS')"],
        cwd=package, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_missing_module_regression_is_detected(tmp_path):
    staged_copy(ROOT, tmp_path)
    (tmp_path / 'board_facts.py').unlink()  # Only this test's disposable payload.
    result = subprocess.run([sys.executable, '-c', 'import learning_server'], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': ''}, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "No module named 'board_facts'" in result.stderr


def test_focus_assets_are_in_copy_payload(package):
    import re
    html=(package/'public/index.html').read_text()
    for asset in ['focus-layout.js','focus-layout.css','guest-practice.js','info-layout.js','academy-upgrade.js','academy-upgrade.css','diagnostic-replay.js','clarity-layout.js','clarity-layout.css']:
        assert '/assets/'+asset in html
        assert (package/'public'/asset).is_file()
    guest=(package/'public/guest-practice.js').read_text()
    for path in re.findall(r"['\"](/assets/[^'\"]+)['\"]",guest):
        assert (package/'public'/path.removeprefix('/assets/')).is_file(),path


def test_piece_license_in_package(package):
    assert (package/"public/assets/pieces/chessnut-source/LICENSE.txt").is_file()
    assert (package/"public/assets/pieces/chessnut-source/SOURCE.txt").is_file()
