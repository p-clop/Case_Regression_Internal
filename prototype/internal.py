"""Structural regression runner: python -m prototype.internal."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess

from .frontend import FrontendError, extract
from .graph import GraphError, build_unit
from .pipeline import digest, find_tool, save_json
from .regression import CHECKS, canonical_unit, compare_case


def _unknown(reason: str) -> dict:
    return {'status': 'UNKNOWN', 'reason': reason}


def run_internal(case: Path, output: Path, *, clang: str | None,
                 artifacts: Path | None = None, timeout: int = 30) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    result = {'case': case.name, 'status': 'UNKNOWN', 'scope': 'structure_only',
              'checks': {name: _unknown('not_run') for name in CHECKS},
              'verification': {arch: _unknown('architecture_checked_by_separate_runner') for arch in ('x86', 'riscv')},
              'output': str(output), 'artifacts': {}}
    try:
        source = case / 'case.c'
        oracle_path = case / 'expected.json'
        expected = json.loads(oracle_path.read_text(encoding='utf-8'))
        if expected.get('id') != case.name:
            raise ValueError('Oracle id does not match the selected case directory')
        result['provenance'] = {'source_sha256': digest(source), 'oracle_sha256': digest(oracle_path),
                                'clang': clang, 'mode': 'import' if artifacts else 'extract'}
        if artifacts:
            artifact_root = artifacts / case.name
            manifest = json.loads((artifact_root / 'manifest.json').read_text(encoding='utf-8'))
            if manifest.get('source_sha256') != digest(source):
                raise ValueError('artifact source hash differs from current case.c (or is missing)')
            for name in ('eventir.json', 'unit.json', 'slice.json'):
                if manifest.get('sha256', {}).get(name) != digest(artifact_root / name):
                    raise ValueError(f'artifact hash mismatch or missing: {name}')
            program = json.loads((artifact_root / 'eventir.json').read_text(encoding='utf-8'))
            unit = json.loads((artifact_root / 'unit.json').read_text(encoding='utf-8'))
            sliced = json.loads((artifact_root / 'slice.json').read_text(encoding='utf-8'))
            if sliced != unit.get('slice'):
                raise ValueError('slice.json differs from unit.json.slice')
        else:
            if not clang:
                raise FrontendError('Clang unavailable; use --clang or bash scripts/run_internal_regression.sh')
            program = extract(source, clang=clang)
            unit = build_unit(program, expected['seed_objects'], expected['outcome'])
            llvm = subprocess.run([clang, '-std=c11', '-pthread', '-O0', '-g', '-S', '-emit-llvm',
                                   str(source.resolve()), '-o', str((output / 'source.ll').resolve())],
                                  capture_output=True, text=True, check=False, timeout=timeout)
            if llvm.returncode:
                raise FrontendError('LLVM generation failed: ' + llvm.stderr)
            result['artifacts']['source.ll'] = digest(output / 'source.ll')
        save_json(output / 'eventir.json', program)
        save_json(output / 'unit.json', unit)
        save_json(output / 'slice.json', unit['slice'])
        for name in ('eventir.json', 'unit.json', 'slice.json'):
            result['artifacts'][name] = digest(output / name)
        save_json(output / 'manifest.json', {'version': 'internal-artifacts-1',
                  'source_sha256': digest(source), 'sha256': result['artifacts']})
        comparison = compare_case(program, unit, expected)
        save_json(output / 'comparison.json', comparison)
        result.update(status=comparison['status'], checks=comparison['checks'], errors=comparison['errors'])
        if comparison['status'] == 'PASS':
            result['counts'] = {'shared_objects': len(unit['shared_objects']),
                                'events': sum(len(t['events']) for t in program['threads']),
                                'retained_events': len(unit['slice']['retained_events']),
                                'removed_events': len(unit['slice']['removed_events'])}
        if expected.get('equivalent_unit_to'):
            result['equivalent_unit_to'] = expected['equivalent_unit_to']
    except (FrontendError, GraphError, OSError, ValueError, KeyError, TypeError,
            subprocess.TimeoutExpired) as error:
        result['status'] = 'UNKNOWN'
        result['reason'] = str(error)
        result['checks'] = {name: _unknown(str(error)) for name in CHECKS}
    save_json(output / 'result.json', result)
    return result


def check_equivalences(results: list[dict], output: Path) -> None:
    """Compare only current-run artifacts, never a stale previous result."""
    current = {r['case']: r for r in results}
    for result in results:
        reference = result.get('equivalent_unit_to')
        if not reference or result['status'] != 'PASS':
            continue
        baseline = current.get(reference)
        if not baseline or baseline['status'] != 'PASS':
            check = _unknown('equivalence_reference_missing_or_not_passing_in_current_run')
        else:
            try:
                left = json.loads((output / result['case'] / 'unit.json').read_text(encoding='utf-8'))
                right = json.loads((output / reference / 'unit.json').read_text(encoding='utf-8'))
                actual, expected = canonical_unit(left), canonical_unit(right)
                differences = [] if actual == expected else [
                    {'path': 'unit.equivalent_unit_to', 'expected': expected, 'actual': actual}]
                check = {'status': 'FAIL' if differences else 'PASS', 'reference': reference,
                         'errors': differences}
            except (OSError, ValueError, KeyError, TypeError) as error:
                check = _unknown(str(error))
        result['checks']['equivalence'] = check
        if check['status'] != 'PASS':
            result['status'] = check['status']
        result.setdefault('errors', []).extend(check.get('errors', []))
        save_json(output / result['case'] / 'result.json', result)
        save_json(output / result['case'] / 'comparison.json',
                  {'status': result['status'], 'checks': result['checks'], 'errors': result['errors']})


def write_summary(output: Path, results: list[dict], metadata: dict) -> str:
    statuses = [r['status'] for r in results]
    status = 'FAIL' if 'FAIL' in statuses else 'UNKNOWN' if 'UNKNOWN' in statuses else 'PASS'
    counts = {state: statuses.count(state) for state in ('PASS', 'FAIL', 'UNKNOWN')}
    save_json(output / 'summary.json', {'status': status, 'scope': 'structure_only',
                                      'counts': counts, **metadata, 'cases': results})
    columns = ['case', *CHECKS, 'equivalence', 'retained_events', 'removed_events',
               'structure_status', 'x86_model', 'riscv_model', 'reason']
    with (output / 'summary.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for result in results:
            writer.writerow({'case': result['case'],
                             **{name: result['checks'][name]['status'] for name in CHECKS},
                             'equivalence': result['checks'].get('equivalence', {}).get('status', 'N/A'),
                             'retained_events': result.get('counts', {}).get('retained_events', ''),
                             'removed_events': result.get('counts', {}).get('removed_events', ''),
                             'structure_status': result['status'], 'x86_model': 'UNKNOWN',
                             'riscv_model': 'UNKNOWN', 'reason': result.get('reason', '')})
    lines = ['# C01–C08 自动结构回归', '',
             f'本次结构结果：**{status}**；PASS {counts["PASS"]} / FAIL {counts["FAIL"]} / UNKNOWN {counts["UNKNOWN"]}。', '',
             '本入口只执行结构检查，模型项保持 **UNKNOWN**。独立架构判据见各例 `architecture.json`，执行 `scripts/run_c_architecture.sh`；模型比较与正式审查分列。', '',
             '| Case | 共享对象 | 事件 | 切片 | Verification Unit | 绑定/调用 | 保留/删除事件 | 结构结果 |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for result in results:
        c = result['checks']
        numbers = result.get('counts', {})
        lines.append(f'| [{result["case"]}]({result["case"]}/result.json) | '
                     + ' | '.join(c[name]['status'] for name in CHECKS)
                     + f' | {numbers.get("retained_events", "?")}/{numbers.get("removed_events", "?")} | {result["status"]} |')
    lines.extend(['', '额外的单元等价检查：', ''])
    for result in results:
        if result.get('equivalent_unit_to'):
            lines.append(f'- {result["case"]} 与 {result["equivalent_unit_to"]}：'
                         + result['checks'].get('equivalence', {}).get('status', 'UNKNOWN'))
    for result in results:
        if result.get('reason'):
            lines.extend(['', f'{result["case"]}：{result["reason"]}'])
        elif result.get('errors'):
            lines.extend(['', f'{result["case"]} 的字段差异见 [{result["case"]}/comparison.json]'
                          f'({result["case"]}/comparison.json)。'])
    lines.extend(['', '完整记录：`summary.json`；可导入表格的结果：`summary.csv`。', ''])
    (output / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')
    return status


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Compare internal C01-C08 structural oracles')
    parser.add_argument('cases', nargs='*', type=Path)
    parser.add_argument('--out', type=Path, default=Path('results/internal'))
    parser.add_argument('--clang')
    parser.add_argument('--artifacts', type=Path, help='import per-case eventir/slice/unit and hash manifest')
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    root = Path(__file__).resolve().parent.parent
    if args.cases:
        cases = args.cases
    else:
        manifest = json.loads((root / 'tests/internal_manifest.json').read_text(encoding='utf-8'))
        cases = [root / item['directory'] for item in manifest['cases']]
    if not cases or len({case.name for case in cases}) != len(cases):
        parser.error('case names must be unique and at least one case is required')
    clang = find_tool('clang', args.clang)
    results = [run_internal(case, args.out / case.name, clang=clang,
                            artifacts=args.artifacts, timeout=args.timeout) for case in cases]
    check_equivalences(results, args.out)
    metadata = {'command_scope': [str(case) for case in cases]}
    if clang and not args.artifacts:
        try:
            version = subprocess.run([clang, '--version'], text=True, capture_output=True, timeout=10, check=False)
            metadata['clang_version'] = (version.stdout + version.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as error:
            metadata['clang_version'] = str(error)
    status = write_summary(args.out, results, metadata)
    for result in results:
        checks = ', '.join(f'{name}={check["status"]}' for name, check in result['checks'].items())
        print(f'{result["case"]}: {result["status"]}; {checks}; model=UNKNOWN')
        if result.get('reason'):
            print('  ' + result['reason'])
        elif result.get('errors'):
            print(f'  {len(result["errors"])} differences; see {result["output"]}/comparison.json')
    return {'PASS': 0, 'FAIL': 1, 'UNKNOWN': 2}[status]


if __name__ == '__main__':
    raise SystemExit(main())
