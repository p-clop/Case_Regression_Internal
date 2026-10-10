"""python -m prototype [case directories] --out results/prototype"""

import argparse
import subprocess
from pathlib import Path

from .pipeline import find_model, find_tool, run_case, save_json


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Bounded Clang pthread/EventIR/litmus regression prototype')
    parser.add_argument('cases', nargs='*', type=Path, help='case directories with case.c and expected.json')
    parser.add_argument('--out', type=Path, default=Path('results/prototype'))
    parser.add_argument('--clang', help='Clang executable path (use a matching local installation)')
    parser.add_argument('--herd7', help='herd7 executable path')
    parser.add_argument('--x86-model', help='x86tso.cat path')
    parser.add_argument('--riscv-model', help='riscv.cat path')
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('--no-run-herd', action='store_true', help='structure only; overall result remains UNKNOWN')
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    root = Path(__file__).resolve().parent.parent
    cases = args.cases or sorted((root / 'cases').glob('P0*'))
    if not cases:
        parser.error('no cases found')
    if len({case.name for case in cases}) != len(cases):
        parser.error('case directory names must be unique')
    clang = find_tool('clang', args.clang)
    herd = find_tool('herd7', args.herd7)
    models = {arch: find_model(herd, arch, getattr(args, arch + '_model')) for arch in ('x86', 'riscv')}
    results = []
    for case in cases:
        result = run_case(case, args.out / case.name, clang=clang, herd=herd, models=models,
                          timeout=args.timeout, run_herd=not args.no_run_herd)
        results.append(result)
        observations = ', '.join(f'{arch}={v.get("observation") or v["status"]}'
                                 for arch, v in result['verification'].items())
        print(f'{case.name}: {result["status"]}; structure={result["structure"]["status"]}; '
              f'{observations or result.get("reason", "")}')
    versions = {}
    for name, tool, flag in [('clang', clang, '--version'), ('herd7', herd, '-version')]:
        if tool:
            try:
                version = subprocess.run([tool, flag], text=True, capture_output=True, timeout=10, check=False)
                versions[name] = (version.stdout + version.stderr).strip()
            except (OSError, subprocess.TimeoutExpired) as error:
                versions[name] = str(error)
    statuses = [r['status'] for r in results]
    status = 'FAIL' if 'FAIL' in statuses else 'UNKNOWN' if 'UNKNOWN' in statuses else 'PASS'
    save_json(args.out / 'summary.json', {'status': status, 'tools': versions, 'cases': results})
    lines = ['# 独立原型回归结果', '', f'整体状态：**{status}**。', '',
             'PASS 表示结构和指定硬件映射的模型结果符合人工 Oracle；不证明原始 C 程序无数据竞争。', '',
             '| Case | 结构 | x86-TSO | RVWMO | 状态 |',
             '| --- | --- | --- | --- | --- |']
    for result in results:
        observations = [result['verification'].get(arch, {}).get('observation') or 'UNKNOWN'
                        for arch in ('x86', 'riscv')]
        lines.append(f'| [{result["case"]}]({result["case"]}/result.json) | '
                     f'{result["structure"]["status"]} | {observations[0]} | {observations[1]} | {result["status"]} |')
    lines.extend(['', '每个 Case 目录提供 `source.ll`、`eventir.json`、`unit.json`、两架构 litmus、寄存器映射和 herd7 原始日志。',
                  '以本次 `result.json` 为准；失败运行不会把既有旧文件认作本次成功证据。', ''])
    (args.out / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')
    return {'PASS': 0, 'FAIL': 1, 'UNKNOWN': 2}[status]


if __name__ == '__main__':
    raise SystemExit(main())
