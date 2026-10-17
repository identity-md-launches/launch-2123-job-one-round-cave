"""Trial on copies of the inherited merger's actual six files; no source writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

SPEC = importlib.util.spec_from_file_location('trial_interfaces', Path(__file__).with_name('interfaces.py'))
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


def run():
    origin = Path(__file__).resolve().parents[1] / 'threeway'
    names = ['merge.py', 'test_merge.py', 'README.md', 'examples/base.txt',
             'examples/ours.txt', 'examples/theirs.txt']
    originals = {name: (origin / name).read_bytes() for name in names}
    scratch = Path('test/scratch')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        roots = [Path(folder) / side for side in api.tree.SIDES]
        for root in roots:
            for name, data in originals.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        edits = [('def section(text):', 'def section(text, *, ensure_newline=True):'),
                 ('def edits(base, changed, side):', 'def edits(base, changed, side, *, matcher=None):')]
        for root, (old, new) in zip(roots[1:], edits):
            path = root / 'merge.py'
            text = path.read_bytes().decode('utf-8')
            assert text.count(old) == 1
            path.write_bytes(text.replace(old, new).encode('utf-8'))
        before = [{name: (root / name).read_bytes() for name in names} for root in roots]
        report = api.from_directories(roots)
        assert report['text_merge_clean'] and report['review_required']
        changes = next(item for item in report['files'] if item['path'] == 'merge.py')['changes']
        assert {item['symbol'] for item in changes} == {'edits', 'section'}
        assert all(len(item['differs_from']) == 1 for item in changes)
        assert all(contents == {name: (root / name).read_bytes() for name in names}
                   for root, contents in zip(roots, before))
    assert originals == {name: (origin / name).read_bytes() for name in names}
    return {'schema': 'interface-review-trial/v1', 'source_files': len(names),
            'text_merge_clean': report['text_merge_clean'],
            'review_required': report['review_required'],
            'changed_symbols': [{'symbol': c['symbol'], 'differs_from': c['differs_from']} for c in changes],
            'source_and_trial_inputs_unchanged': True,
            'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in originals.items()},
            'note': 'Independent illustrative signature edits on copies of real merger files; no candidate executed.'}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
