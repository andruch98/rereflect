"""Build a portable diagnostic from a verified application commit/tree (no local secrets)."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED


def build(destination, application_commit=None, application_tree=None):
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    application_commit = application_commit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo).decode().strip()
    application_tree = application_tree or subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=repo).decode().strip()
    prefix = 'services/backend-api/'
    destination.mkdir(parents=True, exist_ok=False)
    tracked = subprocess.check_output(['git', 'ls-tree', '-rz', '--name-only', application_tree,
                                      prefix + 'src'], cwd=repo).decode().split('\0')
    provenance = {'repository': 'andruch98/rereflect', 'pr': 12,
                  'application_commit': application_commit, 'application_tree': application_tree,
                  'mode': 'isolated four-submission diagnostic', 'files': {}}
    source_files = {}
    for path in filter(None, tracked):
        data = subprocess.check_output(['git', 'show', application_tree + ':' + path], cwd=repo)
        relative = path[len(prefix):]
        source_files[relative] = data
        provenance['files'][relative] = hashlib.sha256(data).hexdigest()
    for name in ('runner.py', 'bootstrap.py', 'run-local.py'):
        provenance['files'][name] = hashlib.sha256((here / name).read_bytes()).hexdigest()
    tree = ast.parse((here / 'runner.py').read_text())
    questions = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'QUESTIONS' for t in node.targets))
    metadata = json.dumps(provenance, indent=2).encode()
    with ZipFile(destination / 'pr12-source.zip', 'w', ZIP_DEFLATED) as archive:
        for name, data in sorted(source_files.items()):
            archive.writestr(name, data)
        archive.writestr('runner.py', (here / 'runner.py').read_bytes())
        archive.writestr('source.json', metadata)
    (destination / 'source.json').write_bytes(metadata)
    (destination / 'questions.json').write_text(json.dumps(questions, indent=2))
    for name in ('bootstrap.py', 'run-local.py', 'README.txt', 'survey-email-test.py'):
        (destination / name).write_bytes((here / name).read_bytes())
    hashes = {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
              for name in ('bootstrap.py', 'run-local.py', 'pr12-source.zip', 'questions.json', 'source.json')}
    (destination / 'checksums.json').write_text(json.dumps(hashes, indent=2))
    final = destination.with_suffix('.zip')
    with ZipFile(final, 'x', ZIP_DEFLATED) as archive:
        for path in sorted(destination.iterdir()):
            archive.write(path, destination.name + '/' + path.name)
    return final


if __name__ == '__main__':
    print(build(Path(sys.argv[1]).resolve(), *(sys.argv[2:4])))
