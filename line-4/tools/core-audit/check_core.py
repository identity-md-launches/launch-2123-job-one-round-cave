#!/usr/bin/env python3
"""Audit conflict-core binding, removal witnesses and exhaustive impossibility."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
if not BASE.is_relative_to(Path.cwd().resolve()):
    raise RuntimeError('run from the workspace containing the tools')
spec = importlib.util.spec_from_file_location('core_audit_edges', BASE / 'exhaustive-audit/audit.py')
edges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edges)
fmt = edges.fmt


def audit(data, report, max_assignments=10000):
    if type(max_assignments) is not int or not 1 <= max_assignments <= 1000000:
        raise fmt.Invalid('max_assignments must be an integer from 1 to 1000000')
    packages, roots = fmt.validate(data)
    normalized = {'packages': packages, 'roots': roots}
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode('ascii')).hexdigest()
    if not isinstance(report, dict) or type(report.get('schema')) is not int or report['schema'] != 1:
        raise fmt.Invalid('report schema must be integer 1')
    if report.get('catalog_sha256') != digest or report.get('roots') != roots:
        raise fmt.Invalid('report does not bind to this catalog and roots')
    if report.get('status') != 'unsatisfiable':
        raise fmt.Invalid('report must claim unsatisfiable')
    core = report.get('core')
    if not isinstance(core, dict) or not core or any(p not in roots or roots[p] != s for p, s in core.items()):
        raise fmt.Invalid('core must be a nonempty unchanged subset of roots')
    if report.get('dropped_roots') != {p: s for p, s in roots.items() if p not in core}:
        raise fmt.Invalid('dropped roots differ from core complement')
    minimality = report.get('minimality')
    witnesses = report.get('removal_witnesses')
    if minimality not in ('irreducible', 'inconclusive') or not isinstance(witnesses, dict):
        raise fmt.Invalid('invalid minimality or witnesses')
    if not set(witnesses) <= set(core) or (minimality == 'irreducible' and set(witnesses) != set(core)):
        raise fmt.Invalid('missing or unexpected removal witnesses')
    for removed, selected in witnesses.items():
        if not isinstance(selected, dict) or any(
                not isinstance(p, str) or not isinstance(v, str) for p, v in selected.items()):
            raise fmt.Invalid('witness must map canonical names to release strings')
        remaining = {p: s for p, s in core.items() if p != removed}
        if edges.assignment(packages, remaining, selected) != selected:
            raise fmt.Invalid('invalid or unreachable removal witness for ' + removed)
    result = edges.exhaustive({'packages': packages, 'roots': core}, max_assignments)
    base = {'method': 'cartesian-core-audit-v1', 'catalog_sha256': digest,
            'core': core, 'removal_witnesses_checked': len(witnesses),
            'exhaustion': result}
    if result['status'] == 'resolved':
        return dict(base, status='rejected', reason='claimed impossible core has a solution',
                    counterexample=result['selected'])
    if result['status'] == 'inconclusive':
        return dict(base, status='inconclusive', reason='core impossibility not established')
    return dict(base, status='verified', claim='unsatisfiable', minimality=minimality,
                irreducible_verified=minimality == 'irreducible')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', help='workspace catalog JSON, or demo')
    parser.add_argument('--report', help='workspace Conflict Core schema-1 report')
    parser.add_argument('--max-assignments', type=int, default=10000)
    args = parser.parse_args(argv)
    try:
        if args.catalog == 'demo':
            if args.report:
                raise fmt.Invalid('demo uses its saved report')
            data = fmt.load(BASE / 'conflict-core/examples/requests-conflict.json')
            report = fmt.load(Path(__file__).parent / 'examples/requests-report.json')
        else:
            if not args.report:
                raise fmt.Invalid('--report is required')
            data, report = fmt.load(args.catalog), fmt.load(args.report)
        result = audit(data, report, args.max_assignments)
        code = {'verified': 0, 'rejected': 1, 'inconclusive': 3}[result['status']]
    except (fmt.Invalid, OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        result, code = {'status': 'invalid', 'error': str(exc)}, 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
