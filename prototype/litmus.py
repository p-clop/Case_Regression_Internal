"""Explicit 32-bit mappings to x86-TSO and RVWMO hardware litmus tests.

RISC-V mappings: https://docs.riscv.org/reference/isa/unpriv/mm-eplan.html
All results concern this mapping, not arbitrary C compilation or C data races.
"""

import re


class LoweringError(ValueError):
    pass


def generate(unit: dict, architecture: str, name: str) -> tuple[str, dict]:
    if architecture not in {'x86', 'riscv'}:
        raise LoweringError(f'unknown architecture: {architecture}')
    objects = unit['objects']
    if len(objects) > 10:
        raise LoweringError('prototype supports at most 10 retained objects')
    for obj in objects:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', obj['id']):
            raise LoweringError(f'unsupported object name: {obj["id"]}')
        if type(obj['initial']) is not int or not -(2**31) <= obj['initial'] < 2**31:
            raise LoweringError('only signed 32-bit integer initializers are supported')
    address = {o['id']: f'x{i+1}' for i, o in enumerate(objects)}
    registers = {}
    rows = []
    initial = [f'{o["id"]}={o["initial"]};' for o in objects]
    for thread in unit['threads']:
        instructions = []
        read_index = 0
        if architecture == 'riscv':
            initial.extend(f'{thread["index"]}:{reg}={obj};' for obj, reg in address.items())
        for event in thread['events']:
            kind, order = event['kind'], event['ordering']
            if kind not in {'Load', 'Store', 'Fence'}:
                raise LoweringError(f'{kind} lowering is not implemented; no model conclusion available')
            allowed = {'Load': {'plain', 'relaxed', 'acquire', 'seq_cst'},
                       'Store': {'plain', 'relaxed', 'release', 'seq_cst'},
                       'Fence': {'relaxed', 'acquire', 'release', 'acq_rel', 'seq_cst'}}
            if order not in allowed[kind]:
                raise LoweringError(f'unsupported {kind} ordering: {order}')
            obj = event.get('object')
            if kind != 'Fence' and obj not in address:
                raise LoweringError(f'event refers to unknown object: {obj}')
            if kind == 'Fence':
                if architecture == 'x86':
                    if order == 'seq_cst':
                        instructions.append('MFENCE')
                else:
                    fences = {'acquire': 'fence r,rw', 'release': 'fence rw,w',
                              'acq_rel': 'fence.tso', 'seq_cst': 'fence rw,rw'}
                    if order in fences:
                        instructions.append(fences[order])
                continue
            if kind == 'Load':
                if architecture == 'x86':
                    names = ['EAX', 'EBX', 'ECX', 'EDX', 'ESI']
                    if read_index >= len(names):
                        raise LoweringError('at most 5 loads per thread supported on x86')
                    reg = names[read_index]
                    instructions.append(f'MOV {reg},[{obj}]')
                else:
                    if read_index >= 20:
                        raise LoweringError('at most 20 loads per thread supported on RISC-V')
                    reg = f'x{11+read_index}'
                    if order == 'seq_cst':
                        instructions.append('fence rw,rw')
                    instructions.append(f'lw {reg},0({address[obj]})')
                    if order in {'acquire', 'seq_cst'}:
                        instructions.append('fence r,rw')
                registers[event['id']] = reg
                read_index += 1
                continue
            value = event.get('value')
            if isinstance(value, dict):
                dependency = value.get('event')
                if dependency not in registers or not any(e['id'] == dependency for e in thread['events']):
                    raise LoweringError('store value must refer to an earlier load in the same thread')
                operand = registers[dependency]
            elif type(value) is int and -(2**31) <= value < 2**31:
                operand = f'${value}' if architecture == 'x86' else 'x31'
                if architecture == 'riscv':
                    instructions.append(f'li x31,{value}')
            else:
                raise LoweringError(f'unsupported store value: {value!r}')
            if architecture == 'x86':
                instructions.append(f'MOV [{obj}],{operand}')
                if order == 'seq_cst':
                    instructions.append('MFENCE')
            else:
                if order in {'release', 'seq_cst'}:
                    instructions.append('fence rw,w')
                instructions.append(f'sw {operand},0({address[obj]})')
        if not instructions:
            raise LoweringError('empty projected thread is not supported')
        rows.append(instructions)
    clauses = []
    for observation in unit['outcome']:
        if observation['event'] not in registers:
            raise LoweringError('outcome refers to a removed or unsupported load')
        clauses.append(f'{observation["thread"]}:{registers[observation["event"]]}={observation["value"]}')
    if not clauses:
        raise LoweringError('explicit nonempty observation condition is required')
    title = re.sub(r'[^A-Za-z0-9_]', '_', name)
    lines = [f'{"X86" if architecture == "x86" else "RISCV"} {title}', '', '{',
             *['  ' + s for s in initial], '}', '',
             ' | '.join(f'P{t["index"]}' for t in unit['threads']) + ' ;']
    for i in range(max(map(len, rows))):
        lines.append(' | '.join(r[i] if i < len(r) else '' for r in rows) + ' ;')
    lines.extend(['', 'exists (' + ' /\\ '.join(clauses) + ')', ''])
    return '\n'.join(lines), registers
