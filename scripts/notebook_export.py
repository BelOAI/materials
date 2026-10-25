"""Общий экспорт ноутбуков занятий и учебника без выполнения ячеек."""
import shutil
import subprocess
import sys
from pathlib import Path

from build_cache import Cache, fingerprint


def export_notebook(path: Path) -> bool:
    destination = path.with_suffix('.html')
    destination.unlink(missing_ok=True)
    jupyter = shutil.which('jupyter')
    if not jupyter:
        print(f'Warning: jupyter not found; skipped HTML for {path.name}', file=sys.stderr)
        return False
    cache = Cache('notebooks', fingerprint([path, Path(__file__)], path.name))
    if cache.restore(path.parent):
        return True
    result = subprocess.run([
        jupyter, 'nbconvert', '--to', 'html', '--output', destination.name,
        '--output-dir', str(path.parent), str(path),
    ], stdout=subprocess.DEVNULL)
    if result.returncode:
        destination.unlink(missing_ok=True)
        print(f'Warning: notebook HTML export failed: {path.name}', file=sys.stderr)
        return False
    if not destination.is_file():
        return False
    cache.save(path.parent, [destination])
    return True


if __name__ == '__main__':
    export_notebook(Path(sys.argv[1]))
