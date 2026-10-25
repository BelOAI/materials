"""Изолированная проверка ноутбуков в отдельных процессах и ядрах."""
import os
import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def execute_notebook(arguments):
    try:
        return _execute_notebook(arguments)
    except Exception as error:
        return str(arguments[0]), str(error)


def _execute_notebook(arguments):
    path, data = map(Path, arguments[:2])
    timeout = arguments[2] if len(arguments) > 2 else 120
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import AsyncKernelManager
    from jupyter_core.utils import run_sync

    with tempfile.TemporaryDirectory() as folder:
        shutil.copyfile(data, Path(folder) / data.name)
        document = nbformat.read(path, as_version=4)
        nbformat.validate(document)
        manager = AsyncKernelManager(kernel_name='python3')
        manager.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
        client = NotebookClient(document, km=manager, timeout=timeout,
                                resources={'metadata': {'path': folder}})
        try:
            client.execute(cleanup_kc=True)
            if any(o.output_type == 'error' for c in document.cells
                   if c.cell_type == 'code' for o in c.outputs):
                raise AssertionError('Ошибка в выводе ячейки')
        except Exception as error:
            return str(path), str(error)
        finally:
            if manager.has_kernel:
                run_sync(manager.shutdown_kernel)(now=True)
    return str(path), None


def check_notebooks(paths, data):
    workers = max(1, int(os.environ.get('NOTEBOOK_TEST_WORKERS', '1')))
    arguments = [(str(path), str(data)) for path in sorted(paths)]
    if workers == 1:
        return list(map(execute_notebook, arguments))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(execute_notebook, arguments))
