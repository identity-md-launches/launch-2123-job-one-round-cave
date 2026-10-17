#!/usr/bin/env python3
"""Compare declared Python callable interfaces in a recomputed text merge."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SPEC = importlib.util.spec_from_file_location(
    'interface_tree', Path(__file__).resolve().parents[1] / 'tree-review' / 'tree_review.py')
tree = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tree)
LIMITS = [
    'Interface differences require review; neither sameness nor difference proves compatibility.',
    'Only direct module functions and direct class methods/nested classes are inventoried.',
    'Conditional definitions and duplicate names make a file incomplete; local functions are ignored.',
    'No execution, import resolution, call-site checking, inheritance or runtime decorator analysis.',
    'Class bases, assignments, aliases, exports, attributes and function bodies are not interfaces here.',
    'Expression hashes describe AST syntax, not values; Python grammar depends on this interpreter.',
    'Bounded stable UTF-8 workspace trees; no atomic snapshot or race protection.',
    'Hashes identify bytes, not authors or approval. No files are written.']


def expression(node):
    if node is None:
        return None
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode('utf-8')).hexdigest()


def signature(node):
    args = node.args
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    def argument(arg, kind, default=None):
        return {'name': arg.arg, 'kind': kind, 'annotation_ast_sha256': expression(arg.annotation),
                'required': default is None and kind not in ('var-positional', 'var-keyword'),
                'default_ast_sha256': expression(default)}
    parameters = [argument(arg, 'positional-only' if i < len(args.posonlyargs)
                           else 'positional-or-keyword', default)
                  for i, (arg, default) in enumerate(zip(positional, defaults))]
    if args.vararg:
        parameters.append(argument(args.vararg, 'var-positional'))
    parameters.extend(argument(arg, 'keyword-only', default)
                      for arg, default in zip(args.kwonlyargs, args.kw_defaults))
    if args.kwarg:
        parameters.append(argument(args.kwarg, 'var-keyword'))
    return {'async': isinstance(node, ast.AsyncFunctionDef), 'parameters': parameters,
            'return_annotation_ast_sha256': expression(node.returns),
            'decorator_ast_sha256': [expression(value) for value in node.decorator_list],
            'type_parameter_ast_sha256': [expression(value) for value in getattr(node, 'type_params', [])]}


def inventory(text):
    if text is None:
        return {'complete': True, 'symbols': {}, 'problems': []}
    tree.validate_text(text)
    try:
        # Compilation adds scope/duplicate-argument checks; no code is run.
        compile(text, '<review-input>', 'exec', dont_inherit=True)
        module = ast.parse(text, filename='<review-input>')
    except SyntaxError as error:
        return {'complete': False, 'symbols': {}, 'problems': [
            {'kind': 'syntax-error', 'line': error.lineno, 'column': error.offset}]}
    except (ValueError, RecursionError, OverflowError):
        return {'complete': False, 'symbols': {}, 'problems': [{'kind': 'parser-limit'}]}
    symbols, problems = {}, []
    definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    def scope(body, prefix):
        seen = set()
        for node in body:
            if isinstance(node, definitions):
                qualified = '.'.join(prefix + [node.name])
                if node.name in seen:
                    problems.append({'kind': 'duplicate-definition', 'symbol': qualified,
                                     'line': node.lineno})
                seen.add(node.name)
                if isinstance(node, ast.ClassDef):
                    scope(node.body, prefix + [node.name])
                else:
                    symbols[qualified] = {'line': node.lineno, 'signature': signature(node)}
            else:
                # Definitions hidden under if/try/with/etc. are not a static binding.
                # Do not descend into local function bodies or lambda expressions.
                stack = list(ast.iter_child_nodes(node))
                while stack:
                    child = stack.pop()
                    if isinstance(child, definitions):
                        problems.append({'kind': 'conditional-definition',
                                         'symbol': '.'.join(prefix + [child.name]),
                                         'line': child.lineno})
                    else:
                        stack.extend(ast.iter_child_nodes(child))
    scope(module.body, [])
    return {'complete': not problems, 'symbols': dict(sorted(symbols.items())), 'problems': problems}


def inspect(sources):
    if len(sources) != 3:
        raise ValueError('exactly three source trees are required')
    packet = tree.combine(sources)
    files = []
    for entry in packet['files']:
        name = entry['path']
        item = {'path': name, 'merge_status': entry['status'],
                'candidate_sha256': entry['candidate_sha256']}
        if entry['status'].endswith('conflict'):
            item['status'] = 'blocked'
        elif Path(name).suffix not in ('.py', '.pyi'):
            item['status'] = 'skipped'
        else:
            versions = {side: inventory(source['files'].get(name))
                        for side, source in zip(tree.SIDES, sources)}
            versions['candidate'] = inventory(entry['candidate'])
            symbols = sorted(set().union(*(set(v['symbols']) for v in versions.values())))
            changes = []
            for symbol in symbols:
                values = {side: version['symbols'].get(symbol) for side, version in versions.items()}
                signatures = {side: value['signature'] if value else None
                              for side, value in values.items()}
                differences = [side for side in ('ours', 'theirs')
                               if signatures[side] != signatures['candidate']]
                if differences:
                    changes.append({'symbol': symbol, 'differs_from': differences,
                                    'candidate_differs_from_base': signatures['base'] != signatures['candidate'],
                                    'kind': 'removed' if signatures['candidate'] is None else
                                            'added' if signatures['base'] is None else 'changed',
                                    'versions': values})
            complete = all(v['complete'] for v in versions.values())
            item.update(status='incomplete' if not complete else 'review' if changes else 'same',
                        complete=complete, changes=changes,
                        problems={side: v['problems'] for side, v in versions.items()},
                        symbol_counts={side: len(v['symbols']) for side, v in versions.items()})
        files.append(item)
    counts = {status: sum(f['status'] == status for f in files)
              for status in ('blocked', 'skipped', 'incomplete', 'review', 'same')}
    return {'schema': 'interface-review/v1', 'review_required': any(counts[s] for s in
            ('blocked', 'incomplete', 'review')), 'text_merge_clean': packet['clean'],
            'inputs': packet['inputs'], 'counts': counts, 'files': files, 'limits': LIMITS}


def from_directories(paths):
    if len(paths) != 3:
        raise ValueError('exactly three source directories are required')
    budget = [0]
    return inspect([tree.snapshot(path, budget) for path in paths])


def demo():
    base = 'def merge(\n    base,\n    ours,\n    theirs,\n):\n    return base\n'
    texts = (base, base.replace('    base,', '    original,'),
             base.replace('    theirs,', '    theirs,\n    *, strict=True,'))
    return inspect([{'files': {'merger.py': text}, 'directories': set()} for text in texts])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', help='BASE_DIR OURS_DIR THEIRS_DIR')
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args(argv)
    if args.demo and args.paths or not args.demo and len(args.paths) != 3:
        parser.error('provide three source trees or --demo')
    try:
        report = demo() if args.demo else from_directories(args.paths)
    except (OSError, UnicodeError, ValueError, RecursionError, OverflowError) as error:
        print('interface-review: ' + ascii(str(error)), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report['review_required'] else 0


if __name__ == '__main__':
    sys.exit(main())
