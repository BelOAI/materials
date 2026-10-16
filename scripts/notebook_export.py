"""Общий экспорт ноутбуков занятий и учебника без выполнения ячеек."""
import shutil
import subprocess
import sys
from pathlib import Path


def export_notebook(path: Path) -> bool:
    destination = path.with_suffix('.html')
    destination.unlink(missing_ok=True)
    jupyter = shutil.which('jupyter')
    if not jupyter:
        print(f'Warning: jupyter not found; skipped HTML for {path.name}', file=sys.stderr)
        return False
    result = subprocess.run([
        jupyter, 'nbconvert', '--to', 'html', '--output', destination.name,
        '--output-dir', str(path.parent), str(path),
    ], stdout=subprocess.DEVNULL)
    if result.returncode:
        destination.unlink(missing_ok=True)
        print(f'Warning: notebook HTML export failed: {path.name}', file=sys.stderr)
        return False
    return True


if __name__ == '__main__':
    export_notebook(Path(sys.argv[1]))
