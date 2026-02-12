import json
from pathlib import Path


def test_frontend_has_lint_script() -> None:
    pkg = json.loads(Path('frontend/package.json').read_text(encoding='utf-8'))
    scripts = pkg.get('scripts', {})
    assert 'lint' in scripts
    assert 'format:check' in scripts
