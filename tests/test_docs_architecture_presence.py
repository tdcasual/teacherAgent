from pathlib import Path


def test_architecture_docs_exist() -> None:
  assert Path('docs/architecture/module-boundaries.md').exists()
  assert Path('docs/architecture/ownership-map.md').exists()
