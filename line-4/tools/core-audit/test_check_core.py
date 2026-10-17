import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('check_core', Path(__file__).with_name('check_core.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
spec = importlib.util.spec_from_file_location('generate_core', m.BASE / 'conflict-core/core.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.data = m.fmt.load(m.BASE / 'conflict-core/examples/requests-conflict.json')
        self.report = m.fmt.load(Path(__file__).parent / 'examples/requests-report.json')

    def test_real_and_no_mutation(self):
        before = copy.deepcopy((self.data, self.report))
        result = m.audit(self.data, self.report)
        self.assertEqual(result['status'], 'verified')
        self.assertTrue(result['irreducible_verified'])
        self.assertEqual(result['exhaustion']['checked_assignments'], 108)
        self.assertEqual((self.data, self.report), before)

    def test_budget_boundary(self):
        self.assertEqual(m.audit(self.data, self.report, 107)['status'], 'inconclusive')
        self.assertEqual(m.audit(self.data, self.report, 108)['status'], 'verified')
        for value in (True, 0, -1, 1000001, '1'):
            with self.assertRaises(m.fmt.Invalid):
                m.audit(self.data, self.report, value)

    def test_independent_of_original_search_and_predicate(self):
        with patch.object(m.fmt, 'solve', side_effect=AssertionError), patch.object(m.fmt, 'accepts', side_effect=AssertionError):
            self.assertEqual(m.audit(self.data, self.report)['status'], 'verified')

    def test_binding_and_structure(self):
        changes = [('catalog_sha256', 'wrong'), ('roots', {}), ('schema', True),
                   ('core', {}), ('core', {'requests': '*'}), ('dropped_roots', {}),
                   ('minimality', 'minimum'), ('status', 'resolved'),
                   ('removal_witnesses', {}), ('removal_witnesses', {'unknown': {}})]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises(m.fmt.Invalid):
                m.audit(self.data, dict(self.report, **{key: value}))

    def test_invalid_witnesses(self):
        for selected in (None, [], {'idna': 3}, {'idna': '2.10'},
                         {'idna': '3.11', 'certifi': '2025.10.5'}, {'IDNA': '3.11'}):
            report = copy.deepcopy(self.report)
            report['removal_witnesses']['requests'] = selected
            with self.subTest(selected=selected), self.assertRaises(m.fmt.Invalid):
                m.audit(self.data, report)

    def test_partial_minimality(self):
        report = dict(self.report, minimality='inconclusive', removal_witnesses={})
        result = m.audit(self.data, report)
        self.assertEqual(result['status'], 'verified')
        self.assertFalse(result['irreducible_verified'])

    def test_false_impossibility(self):
        report = dict(self.report, core={'idna': '>=3.10'},
                      dropped_roots={p: s for p, s in self.data['roots'].items() if p != 'idna'},
                      removal_witnesses={'idna': {}})
        result = m.audit(self.data, report)
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('idna', result['counterexample'])

    def test_single_missing_root_empty_witness(self):
        data = {'packages': {}, 'roots': {'missing': '*'}}
        report = generator.analyze(data)
        self.assertEqual(report['removal_witnesses'], {'missing': {}})
        self.assertTrue(m.audit(data, report)['irreducible_verified'])

    def test_cycles_and_abandoned_branches(self):
        data = {'packages': {'a': {'1': {'b': '*'}, '2': {'missing': '*'}},
                             'b': {'1': {'a': '==1'}}},
                'roots': {'a': '*', 'b': '==2'}}
        self.assertEqual(m.audit(data, generator.analyze(data))['status'], 'verified')

    def test_seeded_reports(self):
        rng = random.Random(2904)
        count = 0
        for _ in range(300):
            packages = {p: {v: {q: rng.choice(['*', '==1', '==2']) for q in 'abc'
                               if rng.random() < .22} for v in ('1', '2')} for p in 'abc'}
            roots = {p: rng.choice(['*', '==1', '==2', '==3']) for p in 'abc' if rng.random() < .7}
            if not roots:
                roots = {'a': '*'}
            data = {'packages': packages, 'roots': roots}
            report = generator.analyze(data)
            if report['status'] == 'unsatisfiable':
                count += 1
                result = m.audit(data, report)
                self.assertEqual(result['status'], 'verified')
                self.assertTrue(result['irreducible_verified'])
        self.assertGreater(count, 100)


if __name__ == '__main__':
    unittest.main()
