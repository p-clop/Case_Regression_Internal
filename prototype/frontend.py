"""Extract a deliberately bounded EventIR from Clang's typed C AST.

This is a static extractor, not a C interpreter or a race detector. Unsupported
constructs in reachable code raise FrontendError rather than disappearing from
the event stream. Header bodies and unreachable user functions are not analyzed.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from dataclasses import dataclass
from typing import Any


class FrontendError(ValueError):
    """The input cannot be faithfully represented by this prototype."""


_WRAPPERS = {
    "ParenExpr", "ConstantExpr", "ExprWithCleanups", "FullExpr",
}
_ORDERS = {0: "relaxed", 1: "consume", 2: "acquire", 3: "release",
           4: "acq_rel", 5: "seq_cst"}
_UNINITIALIZED = object()


@dataclass(frozen=True)
class _Pointer:
    """One exact, statically resolved scalar object; never a may-alias set."""
    key: str


def _children(node: dict) -> list[dict]:
    return [item for item in node.get("inner", []) if item.get("kind")]


def _strip(node: dict) -> dict:
    while node.get("kind") in _WRAPPERS | {"ImplicitCastExpr", "CStyleCastExpr"}:
        children = _children(node)
        if len(children) != 1:
            break
        node = children[0]
    return node


def _has_assignment(node: dict) -> bool:
    return (node.get("kind") == "CompoundAssignOperator"
            or node.get("kind") == "BinaryOperator" and node.get("opcode") == "="
            or node.get("kind") == "UnaryOperator" and node.get("opcode") in {"++", "--"}
            or any(_has_assignment(child) for child in _children(node)))


class _Return(Exception):
    def __init__(self, value: Any):
        self.value = value


class _Extractor:
    def __init__(self, path: Path, source: str, ast: dict):
        self.path = path
        self.source = source
        self.source_bytes = source.encode("utf-8")
        self.source_cache = {str(path): self.source_bytes}
        self.ast = ast
        self.functions: dict[str, dict] = {}
        self.global_decls: dict[str, dict] = {}
        self.objects: dict[str, dict] = {}
        self.memory: dict[str, dict] = {}
        self.records: dict[str, dict] = {}
        self.main_values: dict[str, Any] = {}
        self.main_objects: dict[str, str] = {}
        self.heap: dict[str, dict] = {}
        self.bindings: list[dict] = []
        self.calls: list[dict] = []
        self.assumptions: list[dict] = []
        self.enums: dict[str, int] = {}
        self.threads: list[dict] = []
        self.thread: dict | None = None
        self.stack: list[str] = []
        self.scopes: list[dict[str, Any]] = []
        self._collect_enums(ast)
        for node in _children(ast):
            if not self._from_source(node):
                continue
            if node.get("kind") == "FunctionDecl" and self._body(node) is not None:
                self.functions[node["name"]] = node
            elif node.get("kind") == "VarDecl":
                self.global_decls[node["id"]] = node
            elif node.get("kind") == "RecordDecl" and node.get("completeDefinition"):
                self.records[f"{node.get('tagUsed')} {node.get('name')}"] = node

    def _collect_enums(self, node: dict) -> None:
        if node.get("kind") == "EnumDecl":
            value = -1
            for child in _children(node):
                if child.get("kind") != "EnumConstantDecl":
                    continue
                value += 1
                for expr in _children(child):
                    if "value" in expr:
                        value = int(expr["value"])
                        break
                self.enums[child["id"]] = value
        for child in _children(node):
            self._collect_enums(child)

    def _from_source(self, node: dict) -> bool:
        loc = node.get("loc", {})
        loc = loc.get("expansionLoc", loc)
        if "includedFrom" in loc:
            return False
        if "file" in loc:
            return Path(loc["file"]).resolve() == self.path
        return "offset" in loc

    @staticmethod
    def _body(node: dict) -> dict | None:
        return next((child for child in _children(node)
                     if child.get("kind") == "CompoundStmt"), None)

    def location(self, node: dict) -> dict:
        loc = node.get("loc") or node.get("range", {}).get("begin", {})
        loc = loc.get("expansionLoc", loc)
        offset = loc.get("offset")
        if offset is not None and 0 <= offset <= len(self.source_bytes):
            # Clang offsets and columns are byte-based, even for UTF-8 input.
            return {"line": self.source_bytes.count(b"\n", 0, offset) + 1,
                    "column": offset - self.source_bytes.rfind(b"\n", 0, offset)}
        return {"line": loc.get("line", 0), "column": loc.get("col", 0)}

    def fail(self, node: dict, message: str) -> None:
        loc = self.location(node)
        raise FrontendError(f"{self.path}:{loc['line']}:{loc['column']}: {message}")

    @staticmethod
    def _type(node: dict) -> str:
        typ = node.get("type", {})
        return typ.get("desugaredQualType", typ.get("qualType", ""))

    def _constant(self, node: dict) -> int:
        if _has_assignment(node):
            self.fail(node, "constant expressions must not modify local or shared objects")
        before = len(self.thread["events"]) if self.thread is not None else 0
        value = self.expr(node)
        after = len(self.thread["events"]) if self.thread is not None else 0
        if after != before:
            self.fail(node, "constant expressions must not have shared-memory side effects")
        if not isinstance(value, int):
            self.fail(node, "a compile-time integer constant is required here")
        if not -(2**31) <= value < 2**31:
            self.fail(node, "integer constant is outside the supported signed 32-bit range")
        return value

    def _object(self, decl: dict, use: dict) -> dict:
        key = decl["id"]
        if key in self.memory:
            return self.memory[key]
        typ = self._type(decl)
        spelling = decl.get("type", {}).get("qualType", "")
        if decl.get("tls"):
            self.fail(use, "thread-local storage is unsupported and cannot be treated as a shared global")
        if typ in {"int", "_Atomic(int)"}:
            kind = "atomic_int" if typ == "_Atomic(int)" else "int"
        elif spelling == "pthread_mutex_t":
            kind = "pthread_mutex_t"
        else:
            self.fail(use, f"global object {decl.get('name')!r} has unsupported type {typ!r}; "
                      "only int, atomic_int and pthread_mutex_t are extracted")
        if decl.get("storageClass") == "extern" and not _children(decl):
            self.fail(use, "extern shared objects without an initializer are unsupported")
        initial = 0
        if kind != "pthread_mutex_t" and _children(decl):
            initializer = _children(decl)[-1]
            if (kind == "atomic_int" and initializer.get("kind") == "ImplicitCastExpr"
                    and initializer.get("castKind") == "NonAtomicToAtomic"):
                initializer = _children(initializer)[0]
            initial = self._constant(initializer)
        obj = {"id": decl["name"], "type": kind, "initial": initial,
               "origin": "global", "source_location": self.location(decl)}
        if any(existing["id"] == obj["id"] for existing in self.memory.values()):
            self.fail(use, "multiple declarations of the same shared object are unsupported")
        self.memory[key] = obj
        return obj

    def _field_object(self, node: dict) -> dict:
        if node.get("isArrow") or len(_children(node)) != 1:
            self.fail(node, "only direct fields of global flat structs are supported")
        base = self._global_ref(_children(node)[0])
        if base is None or base.get("tls"):
            self.fail(node, "struct fields require a direct non-thread-local global base")
        record = self.records.get(self._type(base))
        if record is None or record.get("tagUsed") != "struct":
            self.fail(node, "only complete flat struct definitions are supported")
        fields = [child for child in _children(record) if child.get("kind") == "FieldDecl"]
        if any(self._type(field) != "int" or field.get("isBitfield") for field in fields):
            self.fail(node, "structs must contain only ordinary int fields; unions, arrays and bitfields are unsupported")
        field = next((f for f in fields if f["id"] == node.get("referencedMemberDecl")), None)
        if field is None:
            self.fail(node, "cannot resolve struct field identity")
        key = base["id"] + ":" + field["id"]
        if key in self.memory:
            return self.memory[key]
        initial = 0
        initializers = _children(base)
        if initializers:
            init = initializers[-1]
            if init.get("kind") != "InitListExpr":
                self.fail(base, "global structs require scalar brace initializers")
            values = _children(init)
            index = fields.index(field)
            if index < len(values) and values[index].get("kind") != "ImplicitValueInitExpr":
                initial = self._constant(values[index])
        elif base.get("storageClass") == "extern":
            self.fail(base, "extern struct objects without a definition are unsupported")
        obj = {"id": f"{base['name']}.{field['name']}", "type": "int", "initial": initial,
               "origin": "global", "base_object": base["name"], "field_path": [field["name"]],
               "source_location": self.location(field)}
        self.memory[key] = obj
        return obj

    def _lvalue_object(self, node: dict) -> dict:
        ref = _strip(node)
        if ref.get("kind") == "MemberExpr":
            return self._field_object(ref)
        if ref.get("kind") == "DeclRefExpr":
            key = ref.get("referencedDecl", {}).get("id")
            if key in self.global_decls:
                return self._object(self.global_decls[key], ref)
            if key in self.main_objects:
                return self.memory[self.main_objects[key]]
            self.fail(node, "addresses of worker-local objects are unsupported")
        if ref.get("kind") == "UnaryOperator" and ref.get("opcode") == "*":
            pointer = self.expr(_children(ref)[0])
            if not isinstance(pointer, _Pointer) or pointer.key not in self.memory:
                self.fail(node, "dereference requires a uniquely resolved scalar pointer")
            obj = self.memory[pointer.key]
            if obj["type"] != "int":
                self.fail(node, "plain pointer dereferences require an int object")
            return obj
        self.fail(node, "unresolved pointer, array or nested-field lvalue is unsupported")

    def _address(self, node: dict) -> _Pointer:
        obj = self._lvalue_object(node)
        if obj["type"] != "int":
            self.fail(node, "scalar aliases require an int object")
        return _Pointer(next(key for key, candidate in self.memory.items() if candidate is obj))

    def _binding(self, kind: str, name: str, pointer: _Pointer) -> None:
        self.bindings.append({"kind": kind, "thread": self.thread["id"],
                              "function": self.stack[-1], "name": name,
                              "object": self.memory[pointer.key]["id"]})

    def _global_ref(self, node: dict) -> dict | None:
        ref = _strip(node)
        if ref.get("kind") != "DeclRefExpr":
            return None
        return self.global_decls.get(ref.get("referencedDecl", {}).get("id"))

    def _atomic_object(self, node: dict) -> dict:
        ref = _strip(node)
        if ref.get("kind") != "UnaryOperator" or ref.get("opcode") != "&":
            self.fail(node, "atomic operations require the direct address of a global atomic_int")
        decl = self._global_ref(_children(ref)[0])
        if decl is None:
            self.fail(node, "atomic pointer aliases, fields and local atomics are unsupported")
        obj = self._object(decl, node)
        if obj["type"] != "atomic_int":
            self.fail(node, "atomic operation requires an atomic_int object")
        return obj

    def event(self, node: dict, kind: str, obj: dict | None = None,
              ordering: str = "plain", value: Any = None) -> Any:
        if self.thread is None:
            self.fail(node, "shared accesses from main or global initializers are unsupported")
        index = len(self.thread["events"])
        if obj is not None:
            self.objects[obj["id"]] = obj
        event = {"id": f"{self.thread['id']}:E{index}", "kind": kind,
                 "object": obj["id"] if obj else None, "ordering": ordering,
                 "source_location": self.location(node), "function": self.stack[-1]}
        if kind == "Load":
            event["target"] = f"r{sum(e['kind'] == 'Load' for e in self.thread['events'])}"
        if kind == "Store":
            if not (isinstance(value, int) or isinstance(value, dict) and set(value) == {"event"}):
                self.fail(node, "store value must be an integer constant or an earlier load")
            event["value"] = value
        self.thread["events"].append(event)
        if kind == "Load":
            return {"event": event["id"]}
        return None

    def _lookup(self, node: dict, decl: dict) -> Any:
        key = decl.get("id")
        for scope in reversed(self.scopes):
            if key in scope:
                value = scope[key]
                if value is _UNINITIALIZED:
                    self.fail(node, f"read of uninitialized local {decl.get('name')!r}")
                return value
        self.fail(node, f"unresolved reference to {decl.get('name')!r}")

    def _assign(self, lhs: dict, value: Any, node: dict) -> Any:
        ref = _strip(lhs)
        if ref.get("kind") in {"MemberExpr", "UnaryOperator"}:
            obj = self._lvalue_object(ref)
            self.event(node, "Store", obj, value=value)
            return value
        if ref.get("kind") != "DeclRefExpr":
            self.fail(lhs, "stores through pointers, array elements and struct fields are unsupported")
        decl = ref.get("referencedDecl", {})
        if decl.get("id") in self.global_decls:
            obj = self._object(self.global_decls[decl["id"]], lhs)
            if obj["type"] != "int":
                self.fail(lhs, "use explicit atomic_load/store operations for atomic objects")
            self.event(node, "Store", obj, value=value)
            return value
        for scope in reversed(self.scopes):
            if decl.get("id") in scope:
                if self._type(ref) != "int":
                    self.fail(lhs, "only local int assignments are supported")
                scope[decl["id"]] = value
                return value
        self.fail(lhs, "assignment target is outside the supported local/global scope")

    def _token(self, node: dict, *, spelling: bool = False) -> str:
        """Read only the operation token at a Clang-provided source location.

        Clang's JSON AtomicExpr omits its opcode. The typed AST still supplies
        all operands; an allowlisted source token disambiguates load and store.
        Both expansion and spelling tokens are checked, so a macro cannot
        disguise another builtin as a supported operation.
        """
        begin = node.get("range", {}).get("begin", {})
        begin = begin.get("spellingLoc" if spelling else "expansionLoc", begin)
        filename = begin.get("file", str(self.path))
        if filename not in self.source_cache:
            try:
                self.source_cache[filename] = Path(filename).read_bytes()
            except OSError as exc:
                self.fail(node, f"cannot validate atomic builtin spelling in {filename}: {exc}")
        contents = self.source_cache[filename]
        offset = begin.get("offset", -1)
        match = re.match(rb"[A-Za-z_][A-Za-z_0-9]*", contents[offset:]) if offset >= 0 else None
        return match.group(0).decode("ascii") if match else ""

    def _atomic(self, node: dict) -> Any:
        token = self._token(node)
        children = _children(node)
        loads = {"atomic_load", "atomic_load_explicit", "__c11_atomic_load"}
        stores = {"atomic_store", "atomic_store_explicit", "__c11_atomic_store"}
        if token not in loads | stores:
            self.fail(node, f"unsupported atomic operation or macro alias {token!r}; "
                      "supported operations are atomic_load[_explicit] and atomic_store[_explicit]")
        builtin = self._token(node, spelling=True)
        expected_builtin = "__c11_atomic_load" if token in loads else "__c11_atomic_store"
        if builtin != expected_builtin:
            self.fail(node, f"atomic macro resolves to unsupported builtin {builtin!r}; expected {expected_builtin}")
        expected = 2 if token in loads else 3
        if len(children) != expected:
            self.fail(node, "unexpected Clang AtomicExpr layout; refusing to infer operands")
        expected_type = "int" if token in loads else "void"
        if self._type(node) != expected_type:
            self.fail(node, "atomic operation result type differs from the allowlisted load/store API")
        obj = self._atomic_object(children[0])
        order = _ORDERS.get(self._constant(children[1]))
        if order is None or order == "consume":
            self.fail(node, "invalid or unsupported atomic memory order (consume is unsupported)")
        if token in loads:
            if order not in {"relaxed", "acquire", "seq_cst"}:
                self.fail(node, "load memory order must be relaxed, acquire or seq_cst")
            return self.event(node, "Load", obj, order)
        if order not in {"relaxed", "release", "seq_cst"}:
            self.fail(node, "store memory order must be relaxed, release or seq_cst")
        return self.event(node, "Store", obj, order, self.expr(children[2]))

    def _callee(self, node: dict) -> tuple[str, list[dict]]:
        children = _children(node)
        if not children:
            self.fail(node, "call has no callee in Clang AST")
        callee = _strip(children[0])
        if callee.get("kind") != "DeclRefExpr" or callee.get("referencedDecl", {}).get("kind") != "FunctionDecl":
            self.fail(node, "indirect calls and function-pointer aliases are unsupported")
        return callee["referencedDecl"]["name"], children[1:]

    def call(self, node: dict) -> Any:
        name, args = self._callee(node)
        recognized = {"atomic_thread_fence", "__c11_atomic_thread_fence", "__atomic_thread_fence",
                      "pthread_mutex_lock", "pthread_mutex_unlock"}
        if name in self.functions and name in recognized:
            self.fail(node, "source definitions shadowing recognized pthread/atomic APIs are unsupported")
        if name in {"atomic_thread_fence", "__c11_atomic_thread_fence", "__atomic_thread_fence"}:
            if len(args) != 1:
                self.fail(node, "thread fence requires one memory order")
            order = _ORDERS.get(self._constant(args[0]))
            if order not in {"relaxed", "acquire", "release", "acq_rel", "seq_cst"}:
                self.fail(node, "unsupported thread fence memory order")
            return self.event(node, "Fence", ordering=order)
        if name in {"pthread_mutex_lock", "pthread_mutex_unlock"}:
            if len(args) != 1:
                self.fail(node, "mutex operation requires one argument")
            ref = _strip(args[0])
            if ref.get("kind") != "UnaryOperator" or ref.get("opcode") != "&":
                self.fail(node, "mutex operation requires a direct global mutex address")
            decl = self._global_ref(_children(ref)[0])
            if decl is None:
                self.fail(node, "mutex aliases and local mutexes are unsupported")
            obj = self._object(decl, node)
            if obj["type"] != "pthread_mutex_t":
                self.fail(node, "mutex operation requires pthread_mutex_t")
            self.event(node, "Lock" if name.endswith("_lock") else "Unlock", obj)
            # The return status is deliberately not fabricated as zero.
            return None
        if name not in self.functions:
            self.fail(node, f"unsupported reachable call {name!r}")
        self.calls.append({"thread": self.thread["id"], "caller": self.stack[-1], "callee": name})
        return self.invoke(name, [self.expr(arg) for arg in args], node)

    def invoke(self, name: str, args: list[Any], call_node: dict) -> Any:
        if name in self.stack:
            self.fail(call_node, f"recursive helper call {name!r} is unsupported")
        function = self.functions[name]
        if function.get("variadic"):
            self.fail(call_node, "variadic helper functions are unsupported")
        params = [child for child in _children(function) if child.get("kind") == "ParmVarDecl"]
        worker = not self.stack
        return_type = self._type(function).split("(", 1)[0].strip()
        if worker:
            if return_type != "void *" or len(params) != 1 or self._type(params[0]) != "void *":
                self.fail(call_node, "thread entry must have the signature void *worker(void *)")
        elif return_type not in {"void", "int"}:
            self.fail(call_node, "helpers must return void or int")
        if len(params) != len(args):
            self.fail(call_node, "variadic functions or mismatched argument counts are unsupported")
        if len(params) > 1:
            self.fail(call_node, "helpers support at most one int parameter to avoid unspecified argument evaluation order")
        for param in params:
            typ = self._type(param)
            if typ != "int" and not (worker and typ == "void *"):
                self.fail(param, "helper parameters must be int; worker accepts null or one resolved void * argument")
        self.scopes.append({param["id"]: value for param, value in zip(params, args)})
        self.stack.append(name)
        if worker and isinstance(args[0], _Pointer):
            self._binding("thread_argument", params[0]["name"], args[0])
        try:
            self.statement(self._body(function))
        except _Return as result:
            return result.value
        finally:
            self.stack.pop()
            self.scopes.pop()
        return None

    def expr(self, node: dict) -> Any:
        kind = node.get("kind")
        children = _children(node)
        if kind in _WRAPPERS:
            return self.expr(children[0])
        if kind in {"ImplicitCastExpr", "CStyleCastExpr"}:
            if self._type(node) == "void":
                # Discarding a local variable or argument has no event. Other
                # expressions are evaluated so (void)helper() retains effects.
                ref = _strip(children[0])
                if ref.get("kind") == "DeclRefExpr" and self._global_ref(ref) is None:
                    return None
                self.expr(children[0])
                return None
            cast = node.get("castKind", "")
            if cast == "BitCast" and self._type(node) in {"void *", "int *"}:
                if self._type(children[0]) not in {"void *", "int *"}:
                    self.fail(node, "pointer casts may only propagate a known int/void pointer")
                value = self.expr(children[0])
                if not isinstance(value, _Pointer):
                    self.fail(node, "pointer cast requires a uniquely resolved scalar address")
                return value
            if cast in {"NoOp", "LValueToRValue", "FunctionToPointerDecay", "NullToPointer"}:
                return self.expr(children[0])
            if cast == "IntegralCast" and self._type(node) == "int":
                return self.expr(children[0])
            self.fail(node, f"unsupported cast {cast!r}; only int value propagation is supported")
        if kind in {"IntegerLiteral", "CharacterLiteral"}:
            value = int(node["value"])
            if self._type(node) != "int" or not -(2**31) <= value < 2**31:
                self.fail(node, "only signed 32-bit int literals are supported; integer narrowing is unsupported")
            return value
        if kind == "DeclRefExpr":
            decl = node.get("referencedDecl", {})
            if decl.get("id") in self.enums:
                return self.enums[decl["id"]]
            if decl.get("id") in self.global_decls:
                obj = self._object(self.global_decls[decl["id"]], node)
                if obj["type"] != "int":
                    self.fail(node, "use explicit atomic_load/store operations for atomic objects")
                return self.event(node, "Load", obj)
            if self.thread is None and decl.get("id") in self.main_values:
                return self.main_values[decl["id"]]
            return self._lookup(node, decl)
        if kind == "MemberExpr":
            return self.event(node, "Load", self._field_object(node))
        if kind == "AtomicExpr":
            return self._atomic(node)
        if kind == "CallExpr":
            return self.call(node)
        if kind == "BinaryOperator":
            op = node.get("opcode")
            if op == "=":
                return self._assign(children[0], self.expr(children[1]), node)
            # Comma is sequenced. Other expressions with two potential event
            # sources could impose an invented evaluation order, so reject.
            if op == ",":
                self.expr(children[0])
                return self.expr(children[1])
            if op in {"&&", "||"}:
                self.fail(node, "short-circuit control flow is unsupported")
            if any(_has_assignment(child) for child in children):
                self.fail(node, "assignments within arithmetic operands have unsupported evaluation order")
            before = len(self.thread["events"]) if self.thread is not None else 0
            left, right = self.expr(children[0]), self.expr(children[1])
            after = len(self.thread["events"]) if self.thread is not None else 0
            if before != after:
                self.fail(node, "binary arithmetic with shared-memory side effects is unsupported")
            if not isinstance(left, int) or not isinstance(right, int):
                self.fail(node, "arithmetic/comparisons depending on shared loads are unsupported")
            operations = {"+": lambda: left + right, "-": lambda: left - right,
                          "*": lambda: left * right, "&": lambda: left & right,
                          "|": lambda: left | right, "^": lambda: left ^ right,
                          "==": lambda: int(left == right), "!=": lambda: int(left != right),
                          "<": lambda: int(left < right), "<=": lambda: int(left <= right),
                          ">": lambda: int(left > right), ">=": lambda: int(left >= right)}
            if op not in operations:
                self.fail(node, f"unsupported constant binary operator {op!r}")
            result = operations[op]()
            if not -(2**31) <= result < 2**31:
                self.fail(node, "integer expression overflows the supported signed 32-bit range")
            return result
        if kind == "UnaryOperator":
            op = node.get("opcode")
            if op == "&":
                return self._address(children[0])
            if op == "*":
                return self.event(node, "Load", self._lvalue_object(node))
            if op in {"+", "-", "~", "!"}:
                value = self.expr(children[0])
                if not isinstance(value, int):
                    self.fail(node, "unary operations on shared-load values are unsupported")
                result = {"+": lambda: value, "-": lambda: -value,
                          "~": lambda: ~value, "!": lambda: int(not value)}[op]()
                if not -(2**31) <= result < 2**31:
                    self.fail(node, "unary expression overflows the supported signed 32-bit range")
                return result
            self.fail(node, f"unsupported unary operator {op!r}; pointer arithmetic and increment/decrement are unsupported")
        self.fail(node, f"unsupported reachable expression {kind!r}")

    def statement(self, node: dict | None) -> None:
        if node is None:
            return
        kind = node.get("kind")
        if kind == "CompoundStmt":
            self.scopes.append({})
            try:
                for child in _children(node):
                    self.statement(child)
            finally:
                self.scopes.pop()
        elif kind == "DeclStmt":
            for decl in _children(node):
                if decl.get("kind") != "VarDecl" or self._type(decl) not in {"int", "int *"}:
                    self.fail(decl, "only automatic int and uniquely resolved int * locals are supported")
                if decl.get("storageClass") in {"static", "extern"}:
                    self.fail(decl, "static/extern local storage is unsupported")
                children = _children(decl)
                value = self.expr(children[-1]) if children else _UNINITIALIZED
                if self._type(decl) == "int *":
                    if not isinstance(value, _Pointer):
                        self.fail(decl, "local pointer initializer must resolve to exactly one scalar object")
                    self._binding("pointer_alias", decl["name"], value)
                self.scopes[-1][decl["id"]] = value
        elif kind == "ReturnStmt":
            children = _children(node)
            raise _Return(self.expr(children[0]) if children else None)
        elif kind == "NullStmt":
            return
        elif kind.endswith("Stmt"):
            self.fail(node, f"unsupported reachable control flow {kind!r}; only straight-line code is supported")
        else:
            self.expr(node)

    def _thread_handle(self, node: dict, address: bool) -> str:
        ref = _strip(node)
        if address:
            if ref.get("kind") != "UnaryOperator" or ref.get("opcode") != "&":
                self.fail(node, "pthread_create requires a direct local pthread_t address")
            ref = _strip(_children(ref)[0])
        if ref.get("kind") != "DeclRefExpr":
            self.fail(node, "thread arrays and aliased pthread_t handles are unsupported")
        key = ref.get("referencedDecl", {}).get("id")
        if key not in self.main_handles:
            self.fail(node, "pthread handle must be a directly declared local pthread_t")
        return key

    def _main_declaration(self, decl: dict, started: bool) -> None:
        if decl.get("kind") != "VarDecl" or decl.get("storageClass") in {"static", "extern"}:
            self.fail(decl, "main supports only automatic thread handles and bounded scalar storage")
        children = _children(decl)
        if decl.get("type", {}).get("qualType") == "pthread_t" and not children:
            self.main_handles.add(decl["id"])
            return
        if started:
            self.fail(decl, "main storage must be initialized before the first pthread_create")
        typ = self._type(decl)
        if typ == "int" and len(children) == 1:
            initial = self._constant(children[0])
            obj = {"id": f"main.{decl['name']}", "type": "int", "initial": initial,
                   "origin": "thread_argument", "source_location": self.location(decl)}
            self.memory[decl["id"]] = obj
            self.main_objects[decl["id"]] = decl["id"]
            self.main_values[decl["id"]] = initial
            return
        if typ != "int *" or len(children) != 1:
            self.fail(decl, "main supports initialized int objects, one scalar malloc, and pthread_t handles")
        if self.heap:
            self.fail(decl, "multiple allocation sites or main pointer aliases are unsupported")
        init = children[0]
        while init.get("kind") in _WRAPPERS | {"ImplicitCastExpr", "CStyleCastExpr"}:
            sub = _children(init)
            if len(sub) != 1:
                self.fail(init, "ambiguous malloc pointer initializer")
            if init.get("kind") in {"ImplicitCastExpr", "CStyleCastExpr"}:
                if init.get("castKind") != "BitCast" or self._type(init) != "int *" or self._type(sub[0]) != "void *":
                    self.fail(init, "malloc must convert its direct void * result to int *")
            init = sub[0]
        if init.get("kind") != "CallExpr":
            self.fail(decl, "main int * must be initialized by one direct scalar malloc")
        name, args = self._callee(init)
        if name != "malloc" or name in self.functions or len(args) != 1:
            self.fail(init, "only the standard malloc(sizeof(int)) allocation is supported")
        size = _strip(args[0])
        if size.get("kind") != "UnaryExprOrTypeTraitExpr" or size.get("name") != "sizeof":
            self.fail(size, "malloc size must be exactly sizeof(int) or sizeof *the_pointer")
        if "argType" in size:
            correct_size = size["argType"].get("qualType") == "int"
        else:
            operand = _strip(_children(size)[0]) if _children(size) else {}
            deref = _children(operand)
            pointed = _strip(deref[0]) if deref else {}
            correct_size = (operand.get("kind") == "UnaryOperator" and operand.get("opcode") == "*"
                            and self._type(operand) == "int" and pointed.get("kind") == "DeclRefExpr"
                            and pointed.get("referencedDecl", {}).get("id") == decl["id"])
        if not correct_size:
            self.fail(size, "malloc allocation size/type does not identify exactly one int")
        site = {"id": "main:malloc:0", "function": "main", "source_location": self.location(init)}
        obj = {"id": decl["name"], "type": "int", "initial": None, "origin": "heap_escape",
               "allocation_site": site, "source_location": self.location(decl)}
        if any(other["id"] == obj["id"] for other in self.memory.values()):
            self.fail(decl, "heap object identity conflicts with another object")
        self.memory[decl["id"]] = obj
        self.main_values[decl["id"]] = _Pointer(decl["id"])
        self.heap[decl["id"]] = {"guarded": False, "initialized": False, "freed": False}

    def _main_heap_guard(self, node: dict, started: bool) -> None:
        children = _children(node)
        if started or len(children) != 2:
            self.fail(node, "only a pre-thread malloc null guard with an early return is supported")
        condition, branch = children
        condition = _strip(condition)
        if condition.get("kind") != "UnaryOperator" or condition.get("opcode") != "!":
            self.fail(node, "supported allocation guard is exactly if (!pointer) return 1")
        pointer = self.expr(_children(condition)[0])
        if not isinstance(pointer, _Pointer) or pointer.key not in self.heap:
            self.fail(node, "allocation guard must test the single malloc pointer")
        if branch.get("kind") == "CompoundStmt" and len(_children(branch)) == 1:
            branch = _children(branch)[0]
        if (branch.get("kind") != "ReturnStmt" or len(_children(branch)) != 1
                or self._constant(_children(branch)[0]) != 1):
            self.fail(node, "malloc failure branch must contain only return 1")
        state = self.heap[pointer.key]
        if state["guarded"] or state["initialized"]:
            self.fail(node, "malloc must have one null guard before initialization")
        state["guarded"] = True
        self.assumptions.append({"kind": "allocation_succeeded",
                                 "allocation_site": self.memory[pointer.key]["allocation_site"]["id"],
                                 "source_location": self.location(node)})

    def _main_initialize_heap(self, node: dict, started: bool) -> None:
        children = _children(node)
        if started or node.get("opcode") != "=" or len(children) != 2:
            self.fail(node, "main writes after pthread_create and general startup mutations are unsupported")
        lhs = _strip(children[0])
        if lhs.get("kind") != "UnaryOperator" or lhs.get("opcode") != "*":
            self.fail(lhs, "only initialization through the guarded scalar malloc pointer is supported")
        pointer = self.expr(_children(lhs)[0])
        if not isinstance(pointer, _Pointer) or pointer.key not in self.heap:
            self.fail(lhs, "startup initialization must target the single malloc allocation")
        state = self.heap[pointer.key]
        if not state["guarded"] or state["freed"]:
            self.fail(lhs, "heap initialization requires a preceding successful-allocation guard")
        self.memory[pointer.key]["initial"] = self._constant(children[1])
        state["initialized"] = True

    def _thread_argument(self, node: dict) -> Any:
        value = self.expr(node)
        if isinstance(value, _Pointer):
            if value.key in self.heap:
                state = self.heap[value.key]
                if not state["guarded"] or not state["initialized"] or state["freed"]:
                    self.fail(node, "heap arguments must be guarded, initialized and live before pthread_create")
            return value
        if value == 0:
            return 0
        self.fail(node, "thread argument must be null or one uniquely resolved int object")

    def run(self) -> dict:
        if "main" not in self.functions:
            raise FrontendError(f"{self.path}: a main function with direct pthread_create calls is required")
        main = self.functions["main"]
        body = self._body(main)
        self.main_handles: set[str] = set()
        created: dict[str, tuple[str, dict]] = {}
        joined: set[str] = set()
        specs: list[tuple[str, dict, Any]] = []
        joins_started = False
        for statement in _children(body):
            kind = statement.get("kind")
            if kind == "DeclStmt":
                for decl in _children(statement):
                    self._main_declaration(decl, bool(created))
                continue
            if kind == "IfStmt":
                self._main_heap_guard(statement, bool(created))
                continue
            if kind == "BinaryOperator":
                self._main_initialize_heap(statement, bool(created))
                continue
            if kind == "ReturnStmt":
                children = _children(statement)
                if children and self._constant(children[0]) != 0:
                    self.fail(statement, "main must return 0")
                break
            if kind == "NullStmt":
                continue
            if kind != "CallExpr":
                self.fail(statement, "main must be straight-line pthread_create calls followed by pthread_join calls and return 0")
            name, args = self._callee(statement)
            if name in self.functions:
                self.fail(statement, "source definitions shadowing pthread APIs are unsupported")
            if name == "pthread_create":
                if joins_started:
                    self.fail(statement, "creating threads after joins is unsupported; all creates must precede all joins")
                if len(args) != 4:
                    self.fail(statement, "pthread_create requires four arguments")
                handle = self._thread_handle(args[0], True)
                if handle in created:
                    self.fail(statement, "reusing a pthread_t handle is unsupported")
                if self._constant(args[1]) != 0:
                    self.fail(statement, "only default pthread attributes are supported")
                argument = self._thread_argument(args[3])
                entry = _strip(args[2])
                if entry.get("kind") != "DeclRefExpr" or entry.get("referencedDecl", {}).get("kind") != "FunctionDecl":
                    self.fail(statement, "thread entry must be a direct function reference")
                name = entry["referencedDecl"]["name"]
                if name not in self.functions:
                    self.fail(statement, f"worker function {name!r} is not defined in this source file")
                created[handle] = (name, statement)
                specs.append((name, statement, argument))
            elif name == "pthread_join":
                joins_started = True
                if len(args) != 2 or self._constant(args[1]) != 0:
                    self.fail(statement, "pthread_join requires a null return-value pointer")
                handle = self._thread_handle(args[0], False)
                if handle not in created or handle in joined:
                    self.fail(statement, "pthread_join must match exactly one earlier pthread_create")
                joined.add(handle)
            elif name == "free":
                if len(args) != 1 or not created or len(joined) != len(created):
                    self.fail(statement, "free is supported only after every created thread has joined")
                pointer = self.expr(args[0])
                if not isinstance(pointer, _Pointer) or pointer.key not in self.heap:
                    self.fail(statement, "free must target the single scalar malloc object")
                state = self.heap[pointer.key]
                if state["freed"]:
                    self.fail(statement, "duplicate free is unsupported")
                state["freed"] = True
            else:
                self.fail(statement, f"unsupported main call {name!r}")
        if not specs:
            self.fail(main, "no pthread_create calls found")
        if len(specs) != len(joined):
            self.fail(main, "every created thread must have a matching pthread_join")
        for index, (entry, node, argument) in enumerate(specs):
            self.thread = {"id": f"T{index}", "index": index, "entry": entry, "events": []}
            self.invoke(entry, [argument], node)
            self.threads.append(self.thread)
        return {"version": "prototype-1", "source": {"path": str(self.path)},
                "threads": self.threads, "objects": list(self.objects.values()),
                "bindings": self.bindings, "calls": self.calls, "assumptions": self.assumptions,
                "diagnostics": [
                    "Static bounded extraction assumes every pthread_create succeeds and all created workers can overlap.",
                    "Plain shared int accesses describe hardware events; this does not establish defined C behavior or absence of data races.",
                ]}


def extract(source: str | Path, clang: str = "clang") -> dict:
    """Parse a source-file path using Clang and return a prototype-1 EventIR.

    Supported subset: straight-line pthread workers; scalar global int and
    atomic_int; flat global structs with int fields; escaped main-local ints;
    one guarded, initialized scalar malloc; direct single-object int * aliases;
    direct helper calls; load/store atomics and thread fences. General pointer
    analysis, arbitrary allocation/control flow and pointer arithmetic reject.
    A source string is interpreted as a path, not inline C source.
    """
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise FrontendError(f"C source file does not exist: {path}")
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FrontendError(f"Cannot read source file {path}: {exc}") from exc
    command = [str(clang), "-std=c11", "-pthread", "-Xclang", "-ast-dump=json",
               "-fsyntax-only", str(path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise FrontendError(f"Clang executable not found: {clang}; provide --clang /path/to/clang") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FrontendError(f"Clang AST extraction failed: {exc}") from exc
    if result.returncode:
        raise FrontendError(f"Clang rejected {path}:\n{result.stderr.strip()}")
    try:
        ast = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FrontendError(f"Clang did not return a valid JSON AST: {exc}") from exc
    extractor = _Extractor(path, contents, ast)
    return extractor.run()
