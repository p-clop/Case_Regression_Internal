"""Run a source/oracle pair without inventing success when tools are missing."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from .frontend import FrontendError, extract
from .graph import GraphError, build_unit
from .litmus import LoweringError, generate


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_tool(name: str, explicit: str | None = None) -> str | None:
    if explicit:
        return shutil.which(explicit)
    found = shutil.which(name)
    if found:
        return found
    # Only use an installed opam switch, never activate or mutate user settings.
    if name == 'herd7':
        candidates = sorted((Path.home() / '.opam').glob('*/bin/herd7'))
        return str(candidates[0]) if candidates else None
    return None


def find_model(herd: str | None, architecture: str, explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if herd:
        base = Path(herd).resolve().parent.parent
        name = 'x86tso.cat' if architecture == 'x86' else 'riscv.cat'
        for path in [base / 'share/herdtools7/herd' / name, base / 'libdir' / name]:
            if path.is_file():
                return path
    return None


def check_oracle(program: dict, unit: dict, expected: dict) -> list[str]:
    errors = []
    actual_objects = {o['id']: o for o in program['objects']}
    wanted_objects = {o['id']: o for o in expected['objects']}
    if set(actual_objects) != set(wanted_objects):
        errors.append('extracted memory objects differ from oracle')
    for name in sorted(set(actual_objects) & set(wanted_objects)):
        for key, value in wanted_objects[name].items():
            if actual_objects[name].get(key) != value:
                errors.append(f'object {name}: {key}: {actual_objects[name].get(key)!r} != {value!r}')
    if unit['shared_objects'] != sorted(expected['shared_objects']):
        errors.append(f'shared objects: actual {unit["shared_objects"]}, expected {expected["shared_objects"]}')
    if sorted(o['id'] for o in unit['objects']) != sorted(expected['slice_objects']):
        errors.append('retained slice objects differ from the independent oracle')
    if unit['slice']['removed_objects'] != sorted(expected['removed_objects']):
        errors.append('removed objects differ from the independent oracle')
    if len(program['threads']) != len(expected['threads']):
        errors.append('thread count differs from oracle')
    for i, (actual, wanted) in enumerate(zip(program['threads'], expected['threads'])):
        if actual['entry'] != wanted['entry']:
            errors.append(f'T{i}: thread entry differs')
        if len(actual['events']) != len(wanted['events']):
            errors.append(f'T{i}: event count {len(actual["events"])} != {len(wanted["events"])}')
        for j, (event, spec) in enumerate(zip(actual['events'], wanted['events'])):
            for key, value in spec.items():
                if event.get(key) != value:
                    errors.append(f'T{i}:E{j}: {key}: {event.get(key)!r} != {value!r}')
            location = event.get('source_location', {})
            if location.get('line', 0) < 1 or location.get('column', 0) < 1:
                errors.append(f'T{i}:E{j}: missing source location')
    return errors


def verify(litmus: Path, herd: str | None, model: Path | None, expected: str, timeout: int) -> dict:
    if not herd or not model or not model.is_file():
        return {'status': 'UNKNOWN', 'reason': 'herd7_or_model_missing', 'observation': None,
                'expected': expected}
    command = [herd, '-model', str(model), str(litmus)]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'status': 'UNKNOWN', 'reason': str(error), 'command': command,
                'expected': expected, 'observation': None}
    raw = result.stdout + result.stderr
    log = litmus.with_suffix('.herd.txt')
    log.write_text(raw, encoding='utf-8')
    observations = re.findall(r'^Observation\s+\S+\s+(Sometimes|Never|Always)\b', raw, re.MULTILINE)
    # herd can report parsing/model errors without a useful Observation line.
    if result.returncode or len(observations) != 1:
        status, reason, observation = 'UNKNOWN', 'herd_failed_or_unrecognized_output', None
    else:
        observation = observations[0]
        status = 'PASS' if observation == expected else 'FAIL'
        reason = None if status == 'PASS' else 'model_result_differs_from_oracle'
    return {'status': status, 'observation': observation, 'expected': expected,
            'reason': reason, 'returncode': result.returncode, 'command': command,
            'model_sha256': digest(model), 'log': str(log)}


def run_case(case: Path, output: Path, *, clang: str | None, herd: str | None,
             models: dict[str, Path | None], timeout: int = 30, run_herd: bool = True) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    source = case / 'case.c'
    expected_path = case / 'expected.json'
    result = {'case': case.name, 'status': 'UNKNOWN', 'structure': {'status': 'UNKNOWN'},
              'verification': {}, 'output': str(output),
              'scope': 'hardware_projection_of_bounded_source_events'}
    try:
        expected = json.loads(expected_path.read_text(encoding='utf-8'))
        result['provenance'] = {'source_sha256': digest(source),
                                'oracle_sha256': digest(expected_path), 'clang': clang, 'herd7': herd}
        if not clang:
            raise FrontendError('clang is missing; pass --clang /path/to/clang')
        program = extract(source, clang=clang)
        save_json(output / 'eventir.json', program)
        llvm = subprocess.run([clang, '-std=c11', '-pthread', '-O0', '-g', '-S', '-emit-llvm',
                               str(source.resolve()), '-o', str((output / 'source.ll').resolve())],
                              text=True, capture_output=True, timeout=timeout, check=False)
        if llvm.returncode:
            raise FrontendError(f'LLVM IR generation failed: {llvm.stderr}')
        unit = build_unit(program, expected['seed_objects'], expected['outcome'])
        save_json(output / 'unit.json', unit)
        errors = check_oracle(program, unit, expected)
        result['structure'] = {'status': 'FAIL' if errors else 'PASS', 'errors': errors,
                               'shared_objects': unit['shared_objects'],
                               'retained_events': len(unit['slice']['retained_events']),
                               'removed_events': len(unit['slice']['removed_events'])}
        result['provenance']['llvm_ir_sha256'] = digest(output / 'source.ll')
        if errors:
            result['status'] = 'FAIL'
        else:
            for architecture in ('x86', 'riscv'):
                text, registers = generate(unit, architecture, case.name + '_' + architecture)
                litmus = output / f'{architecture}.litmus'
                litmus.write_text(text, encoding='utf-8')
                save_json(output / f'{architecture}.registers.json', registers)
                result['verification'][architecture] = (
                    verify(litmus, herd, models.get(architecture),
                           expected['expected_observations'][architecture], timeout)
                    if run_herd else {'status': 'UNKNOWN', 'reason': 'not_requested', 'observation': None})
            statuses = [v['status'] for v in result['verification'].values()]
            result['status'] = 'FAIL' if 'FAIL' in statuses else 'UNKNOWN' if 'UNKNOWN' in statuses else 'PASS'
    except (FrontendError, GraphError, LoweringError, OSError, ValueError, KeyError,
            subprocess.TimeoutExpired) as error:
        result['reason'] = str(error)
    save_json(output / 'result.json', result)
    return result
