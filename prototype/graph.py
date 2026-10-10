"""Conservative event slicing for the explicitly bounded prototype input language."""

from copy import deepcopy


class GraphError(ValueError):
    pass


def build_unit(program: dict, seeds: list[str], outcome: list[dict]) -> dict:
    """Retain connected shared objects, data predecessors, and thread ordering.

    This is a deliberately conservative object/thread closure, not a minimal or
    general-purpose concurrent program slicer. Potential communication edges do
    not assert reads-from or happens-before; herd decides those per execution.
    """
    events = {e['id']: e for t in program['threads'] for e in t['events']}
    owner = {e['id']: t['id'] for t in program['threads'] for e in t['events']}
    accesses: dict[str, list[dict]] = {}
    for event in events.values():
        if event.get('object') is not None:
            accesses.setdefault(event['object'], []).append(event)
    shared = {
        obj for obj, uses in accesses.items()
        if len({owner[e['id']] for e in uses}) >= 2
        and any(e['kind'] in {'Store', 'RMW', 'Lock', 'Unlock'} for e in uses)
    }
    if not seeds or not set(seeds) <= shared:
        raise GraphError(f'seed objects must be may-shared objects; available: {sorted(shared)}')

    observations = []
    for item in outcome:
        if not isinstance(item.get('thread'), int) or not 0 <= item['thread'] < len(program['threads']):
            raise GraphError('outcome refers to an unknown thread')
        thread = program['threads'][item['thread']]
        reads = [e for e in thread['events']
                 if e['kind'] == 'Load' and e.get('object') == item['object']]
        occurrence = item.get('occurrence', 0)
        if not isinstance(occurrence, int) or not 0 <= occurrence < len(reads):
            raise GraphError(f'outcome load not found: {item}')
        if type(item.get('value')) is not int:
            raise GraphError('outcome values must be integers')
        observations.append({'thread': thread['index'], 'event': reads[occurrence]['id'],
                             'value': item['value']})

    selected_objects = set(seeds) | {events[o['event']]['object'] for o in observations}
    selected_events: set[str] = set()
    changed = True
    while changed:
        previous = (set(selected_objects), set(selected_events))
        selected_events.update(e['id'] for e in events.values()
                               if e.get('object') in selected_objects)
        for thread in program['threads']:
            if any(e['id'] in selected_events for e in thread['events']):
                # Preserve all other shared accesses and synchronization in an
                # involved thread; do not retain isolated private noise solely
                # because it happens to be adjacent in program order.
                selected_objects.update(e['object'] for e in thread['events']
                                        if e.get('object') in shared)
                selected_events.update(e['id'] for e in thread['events']
                                       if e['kind'] in {'Fence', 'Lock', 'Unlock'}
                                       or e.get('ordering') not in {'plain', 'relaxed'})
        for event_id in list(selected_events):
            event = events[event_id]
            if event.get('object'):
                selected_objects.add(event['object'])
            value = event.get('value')
            if isinstance(value, dict):
                dependency = value.get('event')
                if dependency not in events or owner[dependency] != owner[event_id]:
                    raise GraphError(f'unresolved data dependency for {event_id}')
                selected_events.add(dependency)
                selected_objects.add(events[dependency]['object'])
        changed = previous != (selected_objects, selected_events)

    threads = deepcopy(program['threads'])
    edges = []
    for thread in threads:
        thread['events'] = [e for e in thread['events'] if e['id'] in selected_events]
        for left, right in zip(thread['events'], thread['events'][1:]):
            edges.append({'kind': 'po', 'from': left['id'], 'to': right['id']})
        for event in thread['events']:
            if isinstance(event.get('value'), dict):
                edges.append({'kind': 'data', 'from': event['value']['event'], 'to': event['id']})
    for obj in sorted(selected_objects):
        for write in accesses.get(obj, []):
            for read in accesses.get(obj, []):
                if (write['id'] in selected_events and read['id'] in selected_events
                        and write['kind'] == 'Store' and read['kind'] == 'Load'
                        and owner[write['id']] != owner[read['id']]):
                    edges.append({'kind': 'communication_candidate', 'from': write['id'], 'to': read['id']})
    objects = [deepcopy(o) for o in program['objects'] if o['id'] in selected_objects]
    involved = {t['id'] for t in threads if t['events']}
    bindings = [deepcopy(b) for b in program.get('bindings', [])
                if b['thread'] in involved and b['object'] in selected_objects]
    calls = []
    for thread in threads:
        needed = {e.get('function', thread['entry']) for e in thread['events']}
        available = [c for c in program.get('calls', []) if c['thread'] == thread['id']]
        changed = True
        while changed:
            previous = set(needed)
            needed.update(c['caller'] for c in available if c['callee'] in needed)
            changed = previous != needed
        calls.extend(deepcopy(c) for c in available if c['callee'] in needed)
    return {
        'version': 'prototype-1', 'source': program['source'],
        'shared_objects': sorted(shared), 'seed_objects': seeds,
        'objects': objects, 'threads': threads, 'edges': edges,
        'bindings': bindings, 'calls': calls,
        'assumptions': deepcopy(program.get('assumptions', [])),
        'outcome': observations,
        'slice': {'strategy': 'conservative_shared_object_thread_closure',
                  'retained_events': sorted(selected_events),
                  'removed_events': sorted(set(events) - selected_events),
                  'removed_objects': sorted(set(accesses) - selected_objects)},
        'scope': 'hardware_projection_of_bounded_source_events',
        'limitations': [
            'C data-race freedom and full compiler correctness are not proved.',
            'Communication candidates are not established reads-from or synchronization edges.',
            'pthread creation succeeds; workers run once; startup/join occur outside the projected threads.',
        ],
    }
