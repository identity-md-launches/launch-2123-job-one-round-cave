"""Offline interface and real-filesystem checks; standard library only."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('interfaces', Path(__file__).with_name('interfaces.py'))
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


def source(files, directories=()):
    return {'files': files, 'directories': set(directories)}


def compare(*texts):
    return api.inspect([source({'a.py': text} if text is not None else {}) for text in texts])


class InterfaceTests(unittest.TestCase):
    def test_hybrid_demo(self):
        report = api.demo()
        self.assertTrue(report['text_merge_clean'])
        self.assertTrue(report['review_required'])
        self.assertEqual(report['files'][0]['changes'][0]['differs_from'], ['ours', 'theirs'])

    def test_line_numbers_comments_and_bodies_do_not_change_signature(self):
        base = 'def f(a):\n    return a\n'
        result = compare(base, '# comment\n' + base, base.replace('return a', 'return a + 1'))
        self.assertFalse(result['review_required'])

    def test_all_parameter_kinds(self):
        text = 'def f(a, /, b=None, *args, c, d=False, **kwargs): pass\n'
        args = api.inventory(text)['symbols']['f']['signature']['parameters']
        self.assertEqual([p['kind'] for p in args], ['positional-only', 'positional-or-keyword',
                         'var-positional', 'keyword-only', 'keyword-only', 'var-keyword'])
        self.assertEqual([p['required'] for p in args], [True, False, False, True, False, False])
        self.assertIsNotNone(args[1]['default_ast_sha256'])  # None is an actual default.

    def test_annotation_default_decorator_and_async_changes(self):
        base = '@wrap\ndef f(a: int = 1) -> str: pass\n'
        for other in (base.replace('int', 'float'), base.replace('= 1', '= 2'),
                      base.replace('wrap', 'other'), base.replace('str', 'bytes'),
                      base.replace('def f', 'async def f'), base.replace('a:', 'value:')):
            with self.subTest(other=other):
                report = compare(base, other, base)
                self.assertTrue(report['review_required'])
                self.assertEqual(report['files'][0]['changes'][0]['differs_from'], ['theirs'])

    def test_default_formatting_normalized_by_ast(self):
        base = 'def f(a=(1 + 2)): pass\n'
        self.assertFalse(compare(base, base.replace('(1 + 2)', '1+2'), base)['review_required'])

    def test_class_and_nested_class_methods(self):
        text = 'class C:\n    def f(self): pass\n    class N:\n        async def g(self): pass\n'
        self.assertEqual(set(api.inventory(text)['symbols']), {'C.f', 'C.N.g'})

    def test_locals_ignored(self):
        text = 'def f():\n    def local(a): pass\n    return local\n'
        result = api.inventory(text)
        self.assertTrue(result['complete'])
        self.assertEqual(set(result['symbols']), {'f'})

    def test_conditional_and_duplicate_definitions_are_incomplete(self):
        for text in ('if True:\n    def f(): pass\n',
                     'try:\n    class C: pass\nexcept Exception: pass\n',
                     'def f(): pass\ndef f(a): pass\n',
                     'class C:\n    def f(self): pass\n    def f(self, a): pass\n',
                     'class C: pass\ndef C(): pass\n'):
            with self.subTest(text=text):
                self.assertFalse(api.inventory(text)['complete'])
                report = compare(text, text, text)
                self.assertTrue(report['review_required'])
                self.assertEqual(report['files'][0]['status'], 'incomplete')

    def test_invalid_python_is_incomplete(self):
        for text in ('return 1\n', 'def f(a, a): pass\n', 'def (:\n'):
            report = compare(text, text, text)
            self.assertEqual(report['files'][0]['status'], 'incomplete')

    def test_source_not_executed_or_imported(self):
        text = 'raise RuntimeError("DO NOT RUN")\nimport absent_module\n@absent_decorator\ndef f(a=missing()): pass\n'
        self.assertTrue(api.inventory(text)['complete'])

    def test_added_and_removed_functions(self):
        base = 'def f(): pass\n'
        removed = compare(base, '', base)['files'][0]['changes'][0]
        self.assertEqual(removed['kind'], 'removed')
        added = compare('', base, '')['files'][0]['changes'][0]
        self.assertEqual(added['kind'], 'added')
        self.assertEqual(added['differs_from'], ['theirs'])

    def test_whole_file_delete_is_not_silently_skipped(self):
        base = 'def f(): pass\n'
        result = compare(base, None, base)
        self.assertEqual(result['files'][0]['changes'][0]['kind'], 'removed')
        self.assertTrue(result['review_required'])

    def test_agreed_changes(self):
        base, other = 'def f(): pass\n', 'def f(a): pass\n'
        result = compare(base, other, other)
        self.assertFalse(result['review_required'])

    def test_conflicts_and_path_collision_block_even_non_python(self):
        result = compare('def f(a): pass\n', 'def f(b): pass\n', 'def f(c): pass\n')
        self.assertEqual(result['files'][0]['status'], 'blocked')
        collision = api.inspect([source({'a': ''}), source({}, ['a']), source({'a': ''})])
        self.assertTrue(collision['review_required'])

    def test_non_python_explicitly_skipped(self):
        result = api.inspect([source({'a.txt': 'prose'})] * 3)
        self.assertEqual(result['counts']['skipped'], 1)
        self.assertFalse(result['review_required'])

    def test_unicode_crlf_pyi(self):
        text = 'def café(a: str = "é"): ...\r\n'
        result = api.inspect([source({'a.pyi': text})] * 3)
        self.assertEqual(result['counts']['same'], 1)

    def test_expression_content_not_printed(self):
        base = 'def f(a="DO_NOT_ECHO_VALUE"): pass\n'
        result = compare(base, base.replace('VALUE', 'NEW_VALUE'), base)
        self.assertNotIn('DO_NOT_ECHO', json.dumps(result))

    def test_input_bounds(self):
        for text in ('a\x00b', 'x\n' * 4001, 'x' * (1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                api.inventory(text)

    def test_filesystem_cli_and_immutability(self):
        scratch = Path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            roots = [Path(folder) / side for side in api.tree.SIDES]
            before = {}
            for root in roots:
                root.mkdir()
                p = root / 'a.py'
                p.write_bytes(b'def f(a): pass\r\n')
                before[p] = hashlib.sha256(p.read_bytes()).hexdigest()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(api.main([str(p) for p in roots]), 0)
            self.assertFalse(json.loads(output.getvalue())['review_required'])
            self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})
            (roots[1] / 'a.py').write_text('def f(b): pass\n')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(api.main([str(p) for p in roots]), 1)
            (roots[1] / 'link.py').symlink_to('a.py')
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(api.main([str(p) for p in roots]), 2)
                self.assertEqual(out.getvalue(), '')

    def test_workspace_escape(self):
        for path in ('../outside', '/outside-workspace'):
            with self.assertRaises(ValueError):
                api.from_directories([path] * 3)

    def test_cli_demo_and_bad_arity(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(api.main(['--demo']), 1)
        self.assertTrue(json.loads(out.getvalue())['review_required'])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            api.main(['one'])
        self.assertEqual(caught.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
