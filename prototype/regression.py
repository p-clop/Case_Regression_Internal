"""Independent structural oracles for C01-C08 and future internal cases.

Comparisons use stable object/event identities, not source paths or Clang AST
addresses. A structural PASS is independent of an unrun memory-model check.
"""

from __future__ import annotations

import json
from typing import Any


CHECKS = ('shared_objects', 'events', 'slice', 'verification_unit', 'bindings')
MISSING = '<missing>'


def _difference(errors: list, path: str, expected: Any, actual: Any) -> None:
    errors.append({'path': path, 'expected': expected, 'actual': actual})


def _compare(actual: Any, expected: Any, path: str, errors: list) -> None:
    """Compare all oracle keys; permit extra explanatory/source metadata."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            _difference(errors, path, expected, actual)
            return
        for key, value in expected.items():
            _compare(actual.get(key, MISSING), value, f'{path}.{key}', errors)
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            _difference(errors, path, expected, actual)
            return
        if len(actual) != len(expected):
            _difference(errors, path + '.length', len(expected), len(actual))
        for i, (left, right) in enumerate(zip(actual, expected)):
            _compare(left, right, f'{path}[{i}]', errors)
    elif type(actual) is not type(expected) or actual != expected:
        _difference(errors, path, expected, actual)


def _sort(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda value: json.dumps(value, sort_keys=True))


def _project(record: dict, fields: tuple[str, ...]) -> dict:
    return {field: record.get(field, MISSING) for field in fields}


def _validate_oracle(expected: dict) -> None:
    required = {'id', 'objects', 'shared_objects', 'threads', 'seed_objects', 'outcome',
                'slice', 'unit', 'bindings', 'calls', 'assumptions', 'excluded_objects'}
    if expected.get('schema_version') != 2 or expected.get('validation') != 'structure':
        raise ValueError('internal Oracle requires schema_version=2 and validation=structure')
    missing = required - set(expected)
    if missing:
        raise ValueError(f'Oracle missing required fields: {sorted(missing)}')
    for field in required - {'id', 'slice', 'unit'}:
        if not isinstance(expected[field], list):
            raise ValueError(f'Oracle field {field} must be a list')
    for field, keys in [('slice', {'retained_events', 'removed_events', 'removed_objects'}),
                        ('unit', {'objects', 'threads', 'edges', 'outcome', 'bindings', 'calls'})]:
        if not isinstance(expected[field], dict) or not keys <= set(expected[field]):
            raise ValueError(f'Oracle {field} requires {sorted(keys)}')
        if not all(isinstance(expected[field][key], list) for key in keys):
            raise ValueError(f'Oracle {field} values must be lists')
    for obj in expected['objects']:
        if not isinstance(obj, dict) or not {'id', 'type', 'initial', 'origin'} <= set(obj):
            raise ValueError('Oracle objects require id, type, initial and origin')
    ids = [o['id'] for o in expected['objects']]
    if len(ids) != len(set(ids)):
        raise ValueError('Oracle object IDs must be unique')
    event_ids = []
    for thread in expected['threads']:
        if not isinstance(thread, dict) or not {'id', 'entry', 'events'} <= set(thread):
            raise ValueError('Oracle threads require id, entry and events')
        for event in thread['events']:
            if not {'id', 'kind', 'object', 'ordering', 'function'} <= set(event):
                raise ValueError('Oracle events require identity, object, ordering and function')
            if event['kind'] == 'Store' and 'value' not in event:
                raise ValueError('Oracle Stores require value')
            event_ids.append(event['id'])
    if len(event_ids) != len(set(event_ids)):
        raise ValueError('Oracle event IDs must be unique')
    retained, removed = expected['slice']['retained_events'], expected['slice']['removed_events']
    if (len(retained) != len(set(retained)) or len(removed) != len(set(removed))
            or set(retained) & set(removed) or set(retained) | set(removed) != set(event_ids)):
        raise ValueError('Oracle slice must partition its extracted event IDs')


def compare_case(program: dict, unit: dict, expected: dict) -> dict:
    """Compare five contracts, returning field-level differences for each."""
    _validate_oracle(expected)
    checks = {name: {'status': 'PASS', 'errors': []} for name in CHECKS}

    def errors(name):
        return checks[name]['errors']

    def collection(container, name, category, path, fields=(), strings=False):
        value = container.get(name) if isinstance(container, dict) else None
        if not isinstance(value, list):
            _difference(errors(category), path, 'list', value)
            return []
        for index, record in enumerate(value):
            valid = (isinstance(record, str) if strings else isinstance(record, dict)
                     and all(isinstance(record.get(field), str) for field in fields))
            if not valid:
                _difference(errors(category), f'{path}[{index}]',
                            'string' if strings else f'object with string fields {fields}', record)
        return value

    for doc, prefix in [(program, 'program'), (unit, 'unit')]:
        collection(doc, 'objects', 'shared_objects' if prefix == 'program' else 'verification_unit',
                   prefix + '.objects', ('id',))
        all_threads = collection(doc, 'threads', 'events', prefix + '.threads', ('id', 'entry'))
        for i, thread in enumerate(all_threads):
            collection(thread, 'events', 'events', f'{prefix}.threads[{i}].events', ('id',))
        for field, columns in [('bindings', ('kind', 'thread', 'function', 'name', 'object')),
                               ('calls', ('thread', 'caller', 'callee'))]:
            collection(doc, field, 'bindings', prefix + '.' + field, columns)
        collection(doc, 'assumptions', 'bindings', prefix + '.assumptions')
    for field in ('shared_objects', 'seed_objects'):
        collection(unit, field, 'shared_objects', 'unit.' + field, strings=True)
    collection(unit, 'edges', 'verification_unit', 'unit.edges', ('kind', 'from', 'to'))
    collection(unit, 'outcome', 'verification_unit', 'unit.outcome')
    for field in ('retained_events', 'removed_events', 'removed_objects'):
        collection(unit.get('slice') if isinstance(unit, dict) else None,
                   field, 'slice', 'slice.' + field, strings=True)
    shape_errors = [item for check in checks.values() for item in check['errors']]
    if shape_errors:
        for check in checks.values():
            check['status'] = 'FAIL' if check['errors'] else 'UNKNOWN'
        return {'status': 'FAIL', 'checks': checks, 'errors': shape_errors}

    objects = program.get('objects', [])
    actual_ids = [o.get('id') for o in objects]
    if len(actual_ids) != len(set(actual_ids)):
        _difference(errors('shared_objects'), 'objects.unique_ids', True, False)
    actual_objects = {o.get('id'): o for o in objects}
    wanted_objects = {o['id']: o for o in expected['objects']}
    _compare(sorted(actual_ids), sorted(wanted_objects), 'objects.ids', errors('shared_objects'))
    for name, spec in wanted_objects.items():
        _compare(actual_objects.get(name, MISSING), spec, f'objects.{name}', errors('shared_objects'))
    _compare(sorted(unit.get('shared_objects', [])), sorted(expected['shared_objects']),
             'shared_objects', errors('shared_objects'))
    for excluded in expected['excluded_objects']:
        if excluded in actual_objects:
            _difference(errors('shared_objects'), f'excluded_objects.{excluded}', 'absent', 'present')

    threads = program.get('threads', [])
    _compare(threads, expected['threads'], 'threads', errors('events'))
    event_records = [event for thread in threads for event in thread.get('events', [])]
    event_ids = [e.get('id') for e in event_records]
    if len(event_ids) != len(set(event_ids)):
        _difference(errors('events'), 'events.unique_ids', True, False)
    by_id = {e.get('id'): e for e in event_records}
    for event in event_records:
        if event.get('object') is not None and event['object'] not in actual_objects:
            _difference(errors('events'), f'events.{event.get("id")}.object', 'known object', event['object'])
        location = event.get('source_location', {})
        if not isinstance(location, dict):
            _difference(errors('events'), f'events.{event.get("id")}.source_location',
                        'object with line and column', location)
            continue
        for axis in ('line', 'column'):
            if type(location.get(axis)) is not int or location[axis] < 1:
                _difference(errors('events'), f'events.{event.get("id")}.source_location.{axis}',
                            'positive integer', location.get(axis, MISSING))

    sliced = unit.get('slice', {})
    for field in ('retained_events', 'removed_events', 'removed_objects'):
        _compare(sorted(sliced.get(field, [])), sorted(expected['slice'][field]),
                 'slice.' + field, errors('slice'))
    retained = sliced.get('retained_events', [])
    removed = sliced.get('removed_events', [])
    if set(retained) & set(removed) or set(retained) | set(removed) != set(event_ids):
        _difference(errors('slice'), 'slice.partition', sorted(event_ids), sorted(retained + removed))
    _compare(unit.get('seed_objects', MISSING), expected['seed_objects'], 'slice.seed_objects', errors('slice'))

    unit_threads = unit.get('threads', [])
    unit_objects = unit.get('objects', [])
    _compare(sorted(o.get('id') for o in unit_objects), sorted(expected['unit']['objects']),
             'unit.objects', errors('verification_unit'))
    for obj in unit_objects:
        _compare(obj, actual_objects.get(obj.get('id'), MISSING),
                 f'unit.objects.{obj.get("id")}.source_record', errors('verification_unit'))
    unit_projection = [dict(id=t.get('id'), entry=t.get('entry'),
                            events=[e.get('id') for e in t.get('events', [])]) for t in unit_threads]
    _compare(unit_projection, expected['unit']['threads'], 'unit.threads', errors('verification_unit'))
    retained_in_unit = []
    for thread in unit_threads:
        for event in thread.get('events', []):
            event_id = event.get('id')
            retained_in_unit.append(event_id)
            _compare(event, by_id.get(event_id, MISSING),
                     f'unit.events.{event_id}.source_record', errors('verification_unit'))
    _compare(sorted(retained_in_unit), sorted(retained), 'unit.retained_events', errors('verification_unit'))
    _compare(_sort(unit.get('edges', [])), _sort(expected['unit']['edges']),
             'unit.edges', errors('verification_unit'))
    _compare(unit.get('outcome', []), expected['unit']['outcome'], 'unit.outcome', errors('verification_unit'))
    for field in ('bindings', 'calls'):
        _compare(_sort(unit.get(field, [])), _sort(expected['unit'][field]),
                 'unit.' + field, errors('verification_unit'))
    _compare(unit.get('assumptions', []), program.get('assumptions', []),
             'unit.assumptions', errors('verification_unit'))
    for edge in unit.get('edges', []):
        if edge.get('from') not in retained or edge.get('to') not in retained:
            _difference(errors('verification_unit'), 'unit.edge_endpoints', 'retained events', edge)

    for field, columns in [('bindings', ('kind', 'thread', 'function', 'name', 'object')),
                           ('calls', ('thread', 'caller', 'callee'))]:
        values = [_project(record, columns) for record in program.get(field, [])]
        _compare(_sort(values), _sort(expected[field]), field, errors('bindings'))
    _compare(_sort(program.get('assumptions', [])), _sort(expected['assumptions']),
             'assumptions', errors('bindings'))
    all_errors = []
    for check in checks.values():
        check['status'] = 'FAIL' if check['errors'] else 'PASS'
        all_errors.extend(check['errors'])
    return {'status': 'FAIL' if all_errors else 'PASS', 'checks': checks, 'errors': all_errors}


def canonical_unit(unit: dict) -> dict:
    """Identity-independent VU form used for the C08 noise-insertion oracle."""
    positions = {event['id']: [i, j] for i, thread in enumerate(unit['threads'])
                 for j, event in enumerate(thread['events'])}
    threads = []
    for thread in unit['threads']:
        events = []
        for event in thread['events']:
            normalized = _project(event, ('kind', 'object', 'ordering'))
            if 'value' in event:
                value = event['value']
                normalized['value'] = ({'event': positions[value['event']]}
                                       if isinstance(value, dict) else value)
            events.append(normalized)
        threads.append({'entry': thread['entry'], 'events': events})
    objects = []
    for obj in unit['objects']:
        objects.append({key: obj[key] for key in ('id', 'type', 'initial', 'origin', 'base_object', 'field_path')
                        if key in obj})
    return {'objects': sorted(objects, key=lambda o: o['id']), 'threads': threads,
            'edges': _sort([{'kind': edge['kind'], 'from': positions[edge['from']],
                             'to': positions[edge['to']]} for edge in unit['edges']]),
            'outcome': [dict(thread=o['thread'], event=positions[o['event']], value=o['value'])
                        for o in unit['outcome']]}
