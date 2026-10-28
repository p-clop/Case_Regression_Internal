"""Independent hardware-projection oracles for the fixed C01--C08 case set."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

from .internal import run_internal, check_equivalences
from .litmus import generate, LoweringError
from .pipeline import digest, find_tool, find_model, save_json

ROOT = Path(__file__).resolve().parents[1]
ARCHES = ('x86', 'riscv')
SCHEMA = 'c-architecture-oracle-1'


def aggregate(states):
    states = list(states)
    return 'FAIL' if 'FAIL' in states else 'PASS' if states and all(s == 'PASS' for s in states) else 'UNKNOWN'


def input_hashes(case):
    paths = [case / name for name in ('case.c', 'expected.json', 'expected.md', 'architecture.json',
                                     'architecture.md', 'architecture_reviews.json')]
    paths += [ROOT / 'prototype' / name for name in
              ('architecture.py', 'litmus.py', 'internal.py', 'frontend.py', 'graph.py', 'regression.py', 'pipeline.py')]
    paths += [ROOT / 'scripts/run_c_architecture.sh', ROOT / 'tests/internal_manifest.json', ROOT / 'C_ARCHITECTURE.md']
    return {str(path.resolve()): digest(path) for path in paths}


def subject_hash(inputs):
    return hashlib.sha256(json.dumps({k: v for k, v in inputs.items()
                                     if Path(k).name != 'architecture_reviews.json'}, sort_keys=True).encode()).hexdigest()


def model_files(model):
    pending, result = [Path(model)], {}
    while pending:
        path = pending.pop().resolve()
        if str(path) in result:
            continue
        result[str(path)] = digest(path)
        for name in re.findall(r'\binclude\s+"([^"]+)"', path.read_text()):
            include = path.parent / name
            if not include.is_file():
                raise ValueError(f'model include unavailable: {include}')
            pending.append(include)
    return result


def validate_oracle(case):
    oracle = json.loads((case / 'architecture.json').read_text())
    if not isinstance(oracle, dict) or oracle.get('schema') != SCHEMA or oracle.get('case') != case.name:
        raise ValueError('architecture oracle schema/case mismatch')
    if oracle.get('scope') != 'explicit_32bit_hardware_projection' or oracle.get('c_program_correctness') != 'UNKNOWN':
        raise ValueError('architecture oracle must preserve its hardware/C-language boundary')
    if oracle.get('source_sha256') != digest(case / 'case.c'):
        raise ValueError('architecture oracle bound to a different source version')
    if oracle.get('structure_oracle_sha256') != digest(case / 'expected.json'):
        raise ValueError('architecture oracle bound to a different structural oracle')
    if oracle.get('family') not in ('single_location', 'message_passing'):
        raise ValueError('unknown architecture family')
    for key in ('assumptions', 'references', 'remaining_gaps'):
        if not isinstance(oracle.get(key), list) or not oracle[key]:
            raise ValueError(f'architecture oracle missing {key}')
    if oracle.get('variants', {}).get('plain') != {'projection': 'slice', 'fences': []}:
        raise ValueError('plain projection must not silently add fences')
    for name in ('slice', 'full'):
        if name not in oracle['projections']:
            continue
        projection = oracle['projections'][name]
        ids, symbols, events = set(), set(), {}
        for obj in projection['objects']:
            if (obj['id'] in ids or obj['symbol'] in symbols
                    or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', obj['symbol'])
                    or type(obj['initial']) is not int or not -(2**31) <= obj['initial'] < 2**31):
                raise ValueError('object symbols must be distinct 32-bit locations')
            ids.add(obj['id'])
            symbols.add(obj['symbol'])
        if [t['index'] for t in projection['threads']] != [0, 1]:
            raise ValueError('projection must contain exactly T0 and T1')
        for t in projection['threads']:
            for e in t['events']:
                if (e['id'] in events or e['object'] not in ids or e['kind'] not in ('Load', 'Store')
                        or e['ordering'] != 'plain' or (e['kind'] == 'Store' and type(e.get('value')) is not int)):
                    raise ValueError('invalid plain projected event')
                events[e['id']] = (t['index'], e['kind'])
    required = ({'read_initial', 'read_written', 'unwritten_value'} if oracle['family'] == 'single_location'
                else {'stale_payload', 'published_payload', 'unwritten_value', 'fenced_stale_payload'})
    if case.name == 'C08_unrelated_code':
        required.add('full_noise_stale_payload')
    queries = oracle.get('queries', [])
    if len(queries) != len(required) or {q['id'] for q in queries} != required:
        raise ValueError('missing or duplicate architecture query from family coverage')
    for q in queries:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', q['id']) or not q.get('reasoning'):
            raise ValueError('query requires safe identity and independent reasoning')
        if set(q['expected']) != set(ARCHES) or not set(q['expected'].values()) <= {'Never', 'Sometimes', 'Always'}:
            raise ValueError('query requires explicit expectations for both architectures')
        wanted_variant = {'fenced_stale_payload': 'fenced', 'full_noise_stale_payload': 'full_noise'}.get(q['id'], 'plain')
        if q['variant'] != wanted_variant:
            raise ValueError('query variant changes the declared baseline/control meaning')
        variant = oracle['variants'][q['variant']]
        projection = oracle['projections'][variant['projection']]
        loads = {(t['index'], e['id']) for t in projection['threads'] for e in t['events'] if e['kind'] == 'Load'}
        if not q['target'] or any((o['thread'], o['event']) not in loads or type(o['value']) is not int
                                  for o in q['target']):
            raise ValueError('query target must identify retained loads')
    return oracle


def projection_signature(program, declaration):
    symbols = {o['id']: o['symbol'] for o in declaration['objects']}
    objects = [{'id': o['id'], 'symbol': symbols.get(o['id']), 'initial': o['initial']}
               for o in program['objects']]
    threads = [{'index': t['index'], 'entry': t['entry'], 'events': [
        {k: e[k] for k in ('id', 'kind', 'object', 'ordering', 'value') if k in e}
        for e in t['events']]} for t in program['threads']]
    return {'objects': sorted(objects, key=lambda o: o['id']), 'threads': threads}


def compare_projection(program, declaration):
    wanted = deepcopy(declaration)
    wanted['objects'].sort(key=lambda o: o['id'])
    actual = projection_signature(program, declaration)
    return {'status': 'PASS' if actual == wanted else 'FAIL', 'expected': wanted, 'actual': actual}


def build_projection(program, declaration, fences, target):
    matched = compare_projection(program, declaration)
    if matched['status'] != 'PASS':
        raise ValueError('actual event projection differs from independent architecture oracle')
    symbols = {o['id']: o['symbol'] for o in declaration['objects']}
    unit = deepcopy(program)
    unit['objects'] = [{'id': symbols[o['id']], 'initial': o['initial']} for o in program['objects']]
    inserted = 0
    for t in unit['threads']:
        events = []
        for e in t['events']:
            e['object'] = symbols[e['object']]
            events.append(e)
            for fence in fences:
                if fence['thread'] == t['index'] and fence['after'] == e['id']:
                    events.append({'id': f"T{t['index']}:ARCH_FENCE", 'kind': 'Fence', 'ordering': fence['ordering']})
                    inserted += 1
        t['events'] = events
    if inserted != len(fences):
        raise ValueError('fence anchor missing from projection')
    unit['outcome'] = deepcopy(target)
    return unit


def review(case, subject, target, expected, models):
    result = {'status': 'UNKNOWN', 'reason': 'no_formal_review'}
    try:
        document = json.loads((case / 'architecture_reviews.json').read_text())
        if document.get('schema') != 'c-architecture-reviews-1' or document.get('case') != case.name:
            raise ValueError('invalid review document')
        records = [r for r in document['records'] if r.get('target') == target]
        if not records:
            return result
        if len(records) != 1:
            raise ValueError('conflicting review records')
        r = records[0]
        if (r.get('decision') != 'CONFIRMED' or r.get('subject_sha256') != subject
                or r.get('expected') != expected or not models or r.get('model_files') != models):
            raise ValueError('stale or incomplete review binding')
        if not all(isinstance(r.get(k), str) and r[k].strip()
                   for k in ('review_id', 'reviewer', 'reviewed_at', 'rationale')):
            raise ValueError('incomplete review identity or rationale')
        if datetime.fromisoformat(r['reviewed_at']).tzinfo is None:
            raise ValueError('review date requires timezone')
        return {**r, 'status': 'CONFIRMED'}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result['reason'] = str(exc)
        return result


def execute_query(litmus, herd, model, expected, timeout):
    result = {'status': 'UNKNOWN', 'expected': expected, 'actual': None, 'model_files': {}}
    if not herd or not model or not Path(model).is_file():
        return {**result, 'reason': 'herd7_or_model_unavailable'}
    try:
        result['model_files'] = model_files(model)
        command = [herd, '-model', str(model), str(litmus)]
        result['command'] = command
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        stdout, stderr = litmus.with_suffix('.stdout.txt'), litmus.with_suffix('.stderr.txt')
        stdout.write_text(completed.stdout)
        stderr.write_text(completed.stderr)
        result.update(returncode=completed.returncode, stdout_log=str(stdout), stderr_log=str(stderr))
        observations = re.findall(r'^Observation\s+\S+\s+(Never|Sometimes|Always)\s+\d+\s+\d+\s*$',
                                  completed.stdout, re.MULTILINE)
        if completed.returncode or len(observations) != 1:
            return {**result, 'reason': 'unreliable_model_output'}
        result['actual'] = observations[0]
        result['status'] = 'PASS' if observations[0] == expected else 'FAIL'
        result['reason'] = None if result['status'] == 'PASS' else 'model_result_differs_from_oracle'
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result['reason'] = str(exc)
    return result


def run_case(case, structural_directory, output, *, herd, models, timeout=30):
    output.mkdir(parents=True, exist_ok=True)
    result = {'schema': 'c-architecture-result-1', 'case': case.name, 'comparison_status': 'UNKNOWN',
              'scope': 'explicit_32bit_hardware_projection', 'review_status': 'UNKNOWN',
              'conclusion_status': 'UNKNOWN', 'c_program_correctness': 'UNKNOWN', 'queries': [], 'artifacts': {}}
    try:
        oracle = validate_oracle(case)
        inputs = input_hashes(case)
        subject = subject_hash(inputs)
        result['provenance'] = {'inputs': inputs, 'review_subject_sha256': subject}
        structural_path = structural_directory / case.name
        structure = json.loads((structural_path / 'result.json').read_text())
        if (structure.get('case') != case.name or structure.get('status') != 'PASS'
                or structure['provenance']['source_sha256'] != digest(case / 'case.c')
                or structure['provenance']['oracle_sha256'] != digest(case / 'expected.json')):
            raise ValueError('current passing structural evidence unavailable')
        for name in ('unit.json', 'eventir.json'):
            if structure['artifacts'].get(name) != digest(structural_path / name):
                raise ValueError('structural artifact hash mismatch')
        programs = {'slice': json.loads((structural_path / 'unit.json').read_text()),
                    'full': json.loads((structural_path / 'eventir.json').read_text())}
        result['projection_checks'] = {name: compare_projection(programs[name], declaration)
                                       for name, declaration in oracle['projections'].items()}
        if any(c['status'] != 'PASS' for c in result['projection_checks'].values()):
            result.update(comparison_status='FAIL', reason='projection_differs_from_independent_oracle')
        else:
            for query in oracle['queries']:
                variant = oracle['variants'][query['variant']]
                projection = variant['projection']
                unit = build_projection(programs[projection], oracle['projections'][projection],
                                        variant['fences'], query['target'])
                save_json(output / f"{query['id']}.unit.json", unit)
                for arch in ARCHES:
                    text, registers = generate(unit, arch, case.name + '_' + query['id'] + '_' + arch)
                    path = output / f"{query['id']}.{arch}.litmus"
                    path.write_text(text)
                    save_json(output / f"{query['id']}.{arch}.registers.json", registers)
                    checked = execute_query(path, herd, models.get(arch), query['expected'][arch], timeout)
                    checked.update(query=query['id'], variant=query['variant'], architecture=arch,
                                   target=query['target'], source_sha256=digest(path))
                    checked['review'] = review(case, subject, query['id'] + '.' + arch,
                                               checked['expected'], checked['model_files'])
                    checked['conclusion_status'] = (checked['status'] if checked['review']['status'] == 'CONFIRMED'
                                                     else 'UNKNOWN')
                    result['queries'].append(checked)
            result['comparison_status'] = aggregate(q['status'] for q in result['queries'])
            result['review_status'] = ('CONFIRMED' if all(q['review']['status'] == 'CONFIRMED'
                                                        for q in result['queries']) else 'UNKNOWN')
            result['conclusion_status'] = aggregate(q['conclusion_status'] for q in result['queries'])
        result['remaining_gaps'] = oracle['remaining_gaps']
    except (OSError, ValueError, KeyError, TypeError, AttributeError, LoweringError) as exc:
        result['reason'] = str(exc)
    for path in output.iterdir():
        if path.is_file() and path.name != 'result.json':
            result['artifacts'][path.name] = digest(path)
    save_json(output / 'result.json', result)
    return result


def validate_evidence(case, output):
    oracle = validate_oracle(case)
    result = json.loads((output / 'result.json').read_text())
    if result.get('schema') != 'c-architecture-result-1' or result.get('case') != case.name:
        raise ValueError('architecture result identity mismatch')
    if result.get('provenance', {}).get('inputs') != input_hashes(case):
        raise ValueError('stale architecture inputs or missing provenance')
    if result['comparison_status'] == 'PASS':
        expected = {(q['id'], a): q['expected'][a] for q in oracle['queries'] for a in ARCHES}
        actual = {(q['query'], q['architecture']): q['expected'] for q in result['queries']}
        if len(result['queries']) != len(expected) or actual != expected:
            raise ValueError('passing architecture result omits or changes a required query')
        if any(q['status'] != 'PASS' or q['actual'] != q['expected'] for q in result['queries']):
            raise ValueError('passing architecture summary contradicts query observations')
        for q in result['queries']:
            prefix = q['query'] + '.' + q['architecture']
            required = {q['query'] + '.unit.json', prefix + '.litmus', prefix + '.registers.json',
                        prefix + '.stdout.txt', prefix + '.stderr.txt'}
            if (not required <= result['artifacts'].keys() or not q['model_files']
                    or q.get('returncode') != 0):
                raise ValueError('passing architecture query lacks model/artifact evidence')
            observations = re.findall(r'^Observation\s+\S+\s+(Never|Sometimes|Always)\s+\d+\s+\d+\s*$',
                                      (output / (prefix + '.stdout.txt')).read_text(), re.MULTILINE)
            if observations != [q['actual']] or digest(output / (prefix + '.litmus')) != q['source_sha256']:
                raise ValueError('architecture query contradicts raw model evidence')
    for name, expected in result['artifacts'].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output.resolve()) or digest(path) != expected:
            raise ValueError('architecture artifact changed or missing')
    for query in result['queries']:
        for path, expected in query['model_files'].items():
            if digest(Path(path)) != expected:
                raise ValueError('architecture CAT closure changed')
    return result


def publish_latest(output):
    top = ROOT / 'results/c_architecture'
    top.mkdir(parents=True, exist_ok=True)
    save_json(top / 'latest.json', {'summary': str(output / 'summary.json')})
    link = Path(os.path.relpath(output / 'summary.md', top)).as_posix()
    (top / 'summary.md').write_text(
        f'# C 系列架构投影最近报告\n\n[本次报告]({link})。\n\n正式审查与原始 C 程序正确性分别记录。\n',
        encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--internal', type=Path, help='current structural run; default extracts all eight cases')
    parser.add_argument('--case', action='append', help='select a case from the fixed manifest')
    parser.add_argument('--clang')
    parser.add_argument('--herd7')
    parser.add_argument('--x86-model')
    parser.add_argument('--riscv-model')
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    manifest = json.loads((ROOT / 'tests/internal_manifest.json').read_text())
    cases = [ROOT / item['directory'] for item in manifest['cases']]
    if args.case:
        if not set(args.case) <= {c.name for c in cases}:
            parser.error('unknown selected C case')
        cases = [c for c in cases if c.name in args.case]
    output = (args.out or ROOT / 'results/c_architecture' /
              datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')).resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('output must be a fresh directory')
    output.mkdir(parents=True, exist_ok=True)
    structural = args.internal.resolve() if args.internal else output / 'structure'
    if not args.internal:
        clang = find_tool('clang', args.clang or os.environ.get('PROTOTYPE_CLANG'))
        structural_cases = list(cases)
        if any(c.name == 'C08_unrelated_code' for c in cases) and not any(c.name == 'C07_two_objects' for c in cases):
            structural_cases.append(ROOT / 'cases/C07_two_objects')
        results = [run_internal(case, structural / case.name, clang=clang, timeout=args.timeout) for case in structural_cases]
        check_equivalences(results, structural)
    herd = find_tool('herd7', args.herd7 or os.environ.get('PROTOTYPE_HERD7'))
    models = {a: find_model(herd, a, getattr(args, a + '_model') or os.environ.get(
        'PROTOTYPE_X86_MODEL' if a == 'x86' else 'PROTOTYPE_RISCV_MODEL')) for a in ARCHES}
    results = [run_case(c, structural, output / c.name, herd=herd, models=models, timeout=args.timeout) for c in cases]
    summary = {'schema': 'c-architecture-run-1', 'time_shanghai': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
               'comparison_status': aggregate(r['comparison_status'] for r in results),
               'formal_review': 'CONFIRMED' if all(r['review_status'] == 'CONFIRMED' for r in results) else 'UNKNOWN',
               'c_program_correctness': 'UNKNOWN', 'cases': results,
               'model_calls': sum('command' in q for r in results for q in r['queries'])}
    if herd:
        try:
            version = subprocess.run([herd, '-version'], capture_output=True, text=True, timeout=10)
            summary['herd7'] = {'executable': herd, 'version': (version.stdout + version.stderr).strip()}
        except (OSError, subprocess.TimeoutExpired) as exc:
            summary['herd7'] = {'reason': str(exc)}
    save_json(output / 'summary.json', summary)
    lines = ['# C01–C08 架构投影比较报告', '', '## 投影范围', '',
             f"比较：{summary['comparison_status']}；模型调用：{summary['model_calls']}；正式审查：{summary['formal_review']}。", '',
             '显式 32 位普通 Load/Store 映射；结果不证明存在数据竞争的原始 C 程序正确。结构结果另行记录。', '']
    for result in results:
        explanation_link = Path(os.path.relpath(ROOT / 'cases' / result['case'] / 'architecture.md', output)).as_posix()
        lines += [f"## {result['case']}", '',
                  f"比较：{result['comparison_status']}；正式审查：{result['review_status']}；已审查结论：{result['conclusion_status']}。", '',
                  f"[独立依据]({explanation_link})；[完整证据]({result['case']}/result.json)。", '']
        if result.get('reason'):
            lines += ['原因：' + result['reason'] + '。', '']
        lines += ['| 查询 | 架构 | 预期 | 实际 | 比较 |',
                  '| --- | --- | --- | --- | --- |']
        for q in result['queries']:
            lines += [f"| `{q['query']}` | {q['architecture']} | {q['expected']} | {q['actual'] or 'UNKNOWN'} | {q['status']} |"]
        lines += ['']
    lines += ['## 验收与后续工作', '',
              '完成标准是每项查询有独立目标、依据、模型和可复核日志。下一步审查映射与正式 Oracle，完整 C 语义和核心前端集成仍按各自范围推进。', '']
    (output / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')
    if not args.out:
        publish_latest(output)
    print(f"{summary['comparison_status']}: {output / 'summary.md'}")
    return {'PASS': 0, 'FAIL': 1, 'UNKNOWN': 2}[summary['comparison_status']]


if __name__ == '__main__':
    raise SystemExit(main())
