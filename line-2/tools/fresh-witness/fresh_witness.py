#!/usr/bin/env python3
"""Verify a historical Ethereum proof and an explicit caller-time age bound."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('anchor_for_fresh_witness',
                                           HERE.parent / 'header-anchor/anchor.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
w = a.w
MAX_TIME = (1 << 64) - 1


def seconds(value):
    """Canonical decimal CLI seconds, bounded before integer conversion."""
    if not isinstance(value, str) or len(value) > 20 or not re.fullmatch(r'0|[1-9][0-9]*', value):
        raise argparse.ArgumentTypeError('seconds must be canonical unsigned decimal uint64')
    number = int(value)
    if number > MAX_TIME:
        raise argparse.ArgumentTypeError('seconds exceed uint64')
    return number


def evaluate(header, witness, block_hash, address, slots, at, max_age):
    for label, value in (('at', at), ('max_age', max_age)):
        w.require(type(value) is int and 0 <= value <= MAX_TIME,
                  label + ' must be an unsigned uint64 integer')
    # Verify before reporting age: neither witness metadata nor an unverified
    # header timestamp can establish freshness.
    result = a.verify(header, witness, block_hash, address, slots)
    timestamp = int(result['anchor']['timestamp'], 16)
    age = at - timestamp
    accepted = 0 <= age <= max_age
    return {
        'format': 'fresh-witness/1', 'verified': True, 'accepted': accepted,
        'atUnixSeconds': at, 'maxAgeSeconds': max_age,
        'headerUnixSeconds': timestamp, 'ageSeconds': age,
        'reason': 'within-window' if accepted else ('future-header' if age < 0 else 'stale-header'),
        'evidence': result,
        'trust': 'Authenticate the block hash and reference time independently. '
                 'Age measures the authenticated header timestamp, not proof capture time. '
                 'This does not prove consensus, finality, current state, or that a newer block exists.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    demo = sub.add_parser('demo', help='real historical ZTO proof, simulated reference time')
    demo.add_argument('--reject', action='store_true', help='advance reference time one second beyond age limit')
    check = sub.add_parser('check', help='verify with explicit independently trusted inputs')
    check.add_argument('header')
    check.add_argument('witness')
    check.add_argument('--block-hash', required=True)
    check.add_argument('--address', required=True)
    check.add_argument('--slot', action='append', default=[])
    check.add_argument('--at', required=True, type=seconds, help='trusted reference Unix seconds')
    check.add_argument('--max-age', required=True, type=seconds, help='inclusive age limit in seconds')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            header = a.load_header(HERE.parent / 'header-anchor/examples/zto-header-mainnet.json')
            witness = w.load_bundle(HERE.parent / 'state-witness/examples/zto-mainnet.json')
            timestamp = w.quantity(header['timestamp'])
            output = evaluate(header, witness, a.DEMO_HASH, w.ZTO, ['0x0', '0x1'],
                              timestamp + 60 + int(args.reject), 60)
            output['demo'] = ('Real historical ZTO evidence; reference time is simulated at header time +60 '
                              '(+61 with --reject). This is not a claim of present freshness; '
                              'the bundled hash is an RPC observation, not a consensus checkpoint.')
        else:
            output = evaluate(a.load_header(args.header), w.load_bundle(args.witness),
                              args.block_hash, args.address, args.slot, args.at, args.max_age)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if output['accepted'] else 3
    except w.Invalid as error:
        print(json.dumps({'verified': False, 'accepted': False, 'error': str(error)}), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({'verified': False, 'accepted': False, 'error': 'Unreadable or malformed input.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
