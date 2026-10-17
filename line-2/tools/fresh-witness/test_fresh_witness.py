import argparse
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fresh', HERE / 'fresh_witness.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class FreshWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.header = f.a.load_header(HERE.parent / 'header-anchor/examples/zto-header-mainnet.json')
        cls.witness = f.w.load_bundle(HERE.parent / 'state-witness/examples/zto-mainnet.json')
        cls.timestamp = int(cls.header['timestamp'], 16)

    def check(self, offset=60, max_age=60, header=None, witness=None, block_hash=None, slots=None):
        return f.evaluate(self.header if header is None else header,
                          self.witness if witness is None else witness,
                          f.a.DEMO_HASH if block_hash is None else block_hash,
                          f.w.ZTO, ['0x0', '0x1'] if slots is None else slots,
                          self.timestamp + offset, max_age)

    def test_real_zto_inclusive_boundary(self):
        result = self.check()
        self.assertTrue(result['accepted'])
        self.assertTrue(result['evidence']['state']['accountExists'])
        self.assertEqual(result['ageSeconds'], 60)

    def test_stale_verified_but_rejected(self):
        result = self.check(61)
        self.assertTrue(result['verified'])
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], 'stale-header')

    def test_future_rejected(self):
        result = self.check(-1)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], 'future-header')

    def test_zero_window(self):
        self.assertTrue(self.check(0, 0)['accepted'])
        self.assertFalse(self.check(1, 0)['accepted'])

    def test_timestamp_tampering(self):
        header = copy.deepcopy(self.header)
        header['timestamp'] = hex(self.timestamp + 60)
        with self.assertRaises(f.w.Invalid):
            self.check(header=header)

    def test_bad_proof_even_if_stale(self):
        witness = copy.deepcopy(self.witness)
        witness['proof']['accountProof'] = []
        with self.assertRaises(f.w.Invalid):
            self.check(offset=61, witness=witness)

    def test_wrong_anchor(self):
        with self.assertRaises(f.w.Invalid):
            self.check(block_hash='0x' + '11' * 32)

    def test_expected_slots_required(self):
        with self.assertRaises(f.w.Invalid):
            self.check(slots=[])

    def test_metadata_cannot_change_time(self):
        witness = copy.deepcopy(self.witness)
        witness['block']['timestamp'] = hex(self.timestamp + 10000)
        self.assertEqual(self.check(witness=witness)['ageSeconds'], 60)

    def test_api_rejects_invalid_times(self):
        for value in (-1, True, 1.5, '60', 1 << 64):
            for at, age in ((value, 60), (self.timestamp, value)):
                with self.assertRaises(f.w.Invalid):
                    f.evaluate(self.header, self.witness, f.a.DEMO_HASH, f.w.ZTO,
                               ['0x0', '0x1'], at, age)

    def test_cli_seconds(self):
        self.assertEqual(f.seconds('0'), 0)
        self.assertEqual(f.seconds(str(f.MAX_TIME)), f.MAX_TIME)
        for value in ('-1', '01', '+1', ' 1', '1.0', '1e2', str(1 << 64), '9' * 5000):
            with self.assertRaises(argparse.ArgumentTypeError):
                f.seconds(value)

    def test_cli_demos_and_immutability(self):
        before = copy.deepcopy((self.header, self.witness))
        for args, code in ((['demo'], 0), (['demo', '--reject'], 3)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(f.main(args), code)
            self.assertEqual(json.loads(out.getvalue())['accepted'], code == 0)
        self.check()
        self.assertEqual((self.header, self.witness), before)


if __name__ == '__main__':
    unittest.main()
