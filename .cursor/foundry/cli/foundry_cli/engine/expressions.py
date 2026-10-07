"""Typed when-expression evaluator (implementation-flow parity)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from foundry_cli.engine.examination_state import derive_open_clarifying_questions_count
from foundry_cli.ledger import count_events, last_event


class WhenExpressionError(Exception):
    """Raised when a when expression is unknown or cannot be evaluated safely."""

    def __init__(self, expr: str, message: str | None = None) -> None:
        self.expr = expr
        super().__init__(message or f"Unknown or unsupported when expression: {expr!r}")


class _TokKind(Enum):
    EOF = auto()
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACK = auto()
    RBRACK = auto()
    COMMA = auto()
    DOT = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()
    IN = auto()
    ASSIGN = auto()


@dataclass(frozen=True)
class _Token:
    kind: _TokKind
    value: str | None = None
    pos: int = 0


def _normalize_expr(expr: str) -> str:
    return " ".join(expr.split())


def _expression_is_supported(expr: str) -> bool:
    markers = (
        "history.count('receipt.linked'",
        "history.count('connection.taken'",
        "history.count('visit.sealed'",
        "config.limits.",
        "config.review.enabled",
        "!config.review.enabled",
        "history.last('gate.resolved'",
        "state.open_clarifying_questions_count",
        "state.approved_ac_version",
        "state.feature_branch",
        "state.execution_graph_id",
        "state.final_commit_sha",
        "history.last('visit.sealed'",
    )
    return any(marker in expr for marker in markers)


class _Lexer:
    def __init__(self, source: str) -> None:
        self._source = source
        self._pos = 0

    def _peek(self, offset: int = 0) -> str:
        index = self._pos + offset
        return self._source[index] if index < len(self._source) else ""

    def _advance(self, count: int = 1) -> None:
        self._pos += count

    def next_token(self) -> _Token:
        self._skip_ws()
        start = self._pos
        if self._pos >= len(self._source):
            return _Token(_TokKind.EOF, pos=start)

        ch = self._source[self._pos]
        two = self._source[self._pos : self._pos + 2]

        if two == "==":
            self._advance(2)
            return _Token(_TokKind.EQ, "==", start)
        if two == "!=":
            self._advance(2)
            return _Token(_TokKind.NE, "!=", start)
        if two == "<=":
            self._advance(2)
            return _Token(_TokKind.LE, "<=", start)
        if two == ">=":
            self._advance(2)
            return _Token(_TokKind.GE, ">=", start)
        if two == "&&":
            self._advance(2)
            return _Token(_TokKind.AND, "&&", start)
        if two == "||":
            self._advance(2)
            return _Token(_TokKind.OR, "||", start)

        if ch in "()[].,!":
            mapping = {
                "(": _TokKind.LPAREN,
                ")": _TokKind.RPAREN,
                "[": _TokKind.LBRACK,
                "]": _TokKind.RBRACK,
                ",": _TokKind.COMMA,
                ".": _TokKind.DOT,
                "!": _TokKind.NOT,
            }
            self._advance()
            return _Token(mapping[ch], ch, start)

        if ch in "<>":
            kind = _TokKind.LT if ch == "<" else _TokKind.GT
            self._advance()
            return _Token(kind, ch, start)

        if ch == "=":
            self._advance()
            return _Token(_TokKind.ASSIGN, "=", start)

        if ch in "'\"":
            quote = ch
            self._advance()
            buf: list[str] = []
            while self._pos < len(self._source):
                c = self._source[self._pos]
                if c == quote:
                    self._advance()
                    return _Token(_TokKind.STRING, "".join(buf), start)
                if c == "\\" and self._pos + 1 < len(self._source):
                    buf.append(self._source[self._pos + 1])
                    self._advance(2)
                    continue
                buf.append(c)
                self._advance()
            raise WhenExpressionError(self._source, "Unterminated string literal")

        if ch.isdigit():
            while self._pos < len(self._source) and (
                self._source[self._pos].isdigit() or self._source[self._pos] == "."
            ):
                self._advance()
            return _Token(_TokKind.NUMBER, self._source[start : self._pos], start)

        if ch.isalpha() or ch == "_":
            while self._pos < len(self._source) and (
                self._source[self._pos].isalnum() or self._source[self._pos] in "_"
            ):
                self._advance()
            ident = self._source[start : self._pos]
            if ident == "true":
                return _Token(_TokKind.TRUE, ident, start)
            if ident == "false":
                return _Token(_TokKind.FALSE, ident, start)
            if ident == "null":
                return _Token(_TokKind.NULL, ident, start)
            if ident == "in":
                return _Token(_TokKind.IN, ident, start)
            return _Token(_TokKind.IDENT, ident, start)

        raise WhenExpressionError(self._source, f"Unexpected character {ch!r} at {start}")

    def _skip_ws(self) -> None:
        while self._pos < len(self._source) and self._source[self._pos].isspace():
            self._advance()


@dataclass
class _Parser:
    lexer: _Lexer
    current: _Token

    @classmethod
    def parse(cls, source: str) -> Any:
        lexer = _Lexer(source)
        parser = cls(lexer, lexer.next_token())
        node = parser._parse_or()
        if parser.current.kind != _TokKind.EOF:
            raise WhenExpressionError(source, "Unexpected trailing tokens")
        return node

    def _advance(self) -> None:
        self.current = self.lexer.next_token()

    def _expect(self, kind: _TokKind) -> _Token:
        if self.current.kind != kind:
            raise WhenExpressionError("", f"Expected {kind}, got {self.current.kind}")
        token = self.current
        self._advance()
        return token

    def _parse_or(self) -> Any:
        left = self._parse_and()
        while self.current.kind == _TokKind.OR:
            self._advance()
            right = self._parse_and()
            left = ("or", left, right)
        return left

    def _parse_and(self) -> Any:
        left = self._parse_comparison()
        while self.current.kind == _TokKind.AND:
            self._advance()
            right = self._parse_comparison()
            left = ("and", left, right)
        return left

    def _parse_comparison(self) -> Any:
        left = self._parse_unary()
        op_map = {
            _TokKind.EQ: "==",
            _TokKind.NE: "!=",
            _TokKind.LT: "<",
            _TokKind.LE: "<=",
            _TokKind.GT: ">",
            _TokKind.GE: ">=",
            _TokKind.IN: "in",
        }
        if self.current.kind in op_map:
            op = op_map[self.current.kind]
            self._advance()
            right = self._parse_unary()
            return ("cmp", op, left, right)
        return left

    def _parse_unary(self) -> Any:
        if self.current.kind == _TokKind.NOT:
            self._advance()
            return ("not", self._parse_unary())
        return self._parse_postfix()

    def _parse_postfix(self) -> Any:
        node = self._parse_atom()
        while True:
            if self.current.kind == _TokKind.DOT:
                self._advance()
                name = self._expect(_TokKind.IDENT).value or ""
                node = ("attr", node, name)
            elif self.current.kind == _TokKind.LPAREN:
                self._advance()
                args: list[Any] = []
                if self.current.kind != _TokKind.RPAREN:
                    args.append(self._parse_arg())
                    while self.current.kind == _TokKind.COMMA:
                        self._advance()
                        args.append(self._parse_arg())
                self._expect(_TokKind.RPAREN)
                node = ("call", node, args)
            else:
                break
        return node

    def _parse_arg(self) -> Any:
        if self.current.kind == _TokKind.IDENT and self.lexer._peek() == "=":
            name = self.current.value or ""
            self._advance()
            self._expect(_TokKind.ASSIGN)
            value = self._parse_or()
            return ("kwarg", name, value)
        return self._parse_or()

    def _parse_atom(self) -> Any:
        if self.current.kind == _TokKind.TRUE:
            self._advance()
            return ("lit", True)
        if self.current.kind == _TokKind.FALSE:
            self._advance()
            return ("lit", False)
        if self.current.kind == _TokKind.NULL:
            self._advance()
            return ("lit", None)
        if self.current.kind == _TokKind.NUMBER:
            raw = self.current.value or "0"
            self._advance()
            if "." in raw:
                return ("lit", float(raw))
            return ("lit", int(raw))
        if self.current.kind == _TokKind.STRING:
            value = self.current.value or ""
            self._advance()
            return ("lit", value)
        if self.current.kind == _TokKind.LBRACK:
            self._advance()
            items: list[Any] = []
            if self.current.kind != _TokKind.RBRACK:
                items.append(self._parse_or())
                while self.current.kind == _TokKind.COMMA:
                    self._advance()
                    items.append(self._parse_or())
            self._expect(_TokKind.RBRACK)
            return ("list", items)
        if self.current.kind == _TokKind.LPAREN:
            self._advance()
            inner = self._parse_or()
            self._expect(_TokKind.RPAREN)
            return inner
        if self.current.kind == _TokKind.IDENT:
            name = self.current.value or ""
            self._advance()
            return ("name", name)
        raise WhenExpressionError("", f"Unexpected token {self.current.kind}")


class _EvalContext:
    def __init__(
        self,
        snapshot: dict[str, Any],
        visit: dict[str, Any],
        expr: str,
        names: dict[str, Any] | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.visit = visit
        self.expr = expr
        self.names = names or {}
        self.visit_id = str(visit.get("id", ""))
        self.gate_node = str(visit.get("node_id") or "")

    def eval(self, node: Any) -> Any:
        kind = node[0]
        if kind == "lit":
            return node[1]
        if kind == "list":
            return [self.eval(item) for item in node[1]]
        if kind == "name":
            return self._resolve_name(node[1])
        if kind == "not":
            return not self._truthy(self.eval(node[1]))
        if kind == "and":
            left = self.eval(node[1])
            if not self._truthy(left):
                return left
            return self.eval(node[2])
        if kind == "or":
            left = self.eval(node[1])
            if self._truthy(left):
                return left
            return self.eval(node[2])
        if kind == "cmp":
            return self._compare(node[1], self.eval(node[2]), self.eval(node[3]))
        if kind == "attr":
            if self._is_namespace_path(node):
                return self._eval_path_value(node)
            base = self.eval(node[1])
            return self._attr(base, node[2])
        if kind == "call":
            callee = node[1]
            if callee[0] != "attr" or callee[1][0] != "name":
                raise WhenExpressionError(self.expr, "Unsupported function call")
            namespace = callee[1][1]
            method = callee[2]
            if namespace != "history":
                raise WhenExpressionError(self.expr, f"Unsupported namespace call: {namespace}.{method}")
            return self._history_call(method, node[2])
        raise WhenExpressionError(self.expr, f"Unsupported AST node {kind!r}")

    def _truthy(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return True

    def _compare(self, op: str, left: Any, right: Any) -> bool:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "in":
            if not isinstance(right, list):
                raise WhenExpressionError(self.expr, "'in' requires a list")
            return left in right
        if op in ("<", "<=", ">", ">="):
            if left is None or right is None:
                return False
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                return False
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            return left >= right
        raise WhenExpressionError(self.expr, f"Unknown comparison {op!r}")

    def _is_namespace_path(self, node: Any) -> bool:
        if node[0] != "attr":
            return False
        if node[1][0] == "name" and node[1][1] in ("config", "state", "visit"):
            return True
        return node[1][0] == "attr" and self._is_namespace_path(node[1])

    def _attr(self, base: Any, name: str) -> Any:
        if base is None:
            raise WhenExpressionError(self.expr, f"Cannot read .{name} from null")
        if isinstance(base, dict):
            if name == "outcome" or name == "decision":
                return base.get(name)
            return base.get(name)
        raise WhenExpressionError(self.expr, f"Cannot read .{name} from {type(base).__name__}")

    def _resolve_name(self, name: str) -> Any:
        if name in self.names:
            return self.names[name]
        if name == "visit":
            return {"id": self.visit_id}
        if name == "config":
            config = self.snapshot.get("config")
            return config if isinstance(config, dict) else {}
        if name == "state":
            state = self.snapshot.get("state")
            return state if isinstance(state, dict) else {}
        if name == "history":
            return {"_history": True}
        raise WhenExpressionError(self.expr, f"Unknown identifier {name!r}")

    def _default_limit(self, name: str) -> int:
        return 2 if name in ("repair", "reverify") else 0

    def _path_parts(self, node: Any) -> list[str]:
        parts: list[str] = []
        current = node
        while current[0] == "attr":
            parts.append(current[2])
            current = current[1]
        if current[0] != "name":
            raise WhenExpressionError(self.expr, "Invalid property path")
        parts.append(current[1])
        parts.reverse()
        return parts

    def _eval_path_value(self, node: Any) -> Any:
        """Evaluate postfix chains starting at config/state/visit."""
        parts = self._path_parts(node)
        root = parts[0]
        if root == "visit":
            if parts == ["visit", "id"]:
                return self.visit_id
            raise WhenExpressionError(self.expr, f"Unsupported visit path: {'.'.join(parts)}")
        if root == "state":
            if len(parts) != 2:
                raise WhenExpressionError(self.expr, f"Unsupported state path: {'.'.join(parts)}")
            field = parts[1]
            if field == "open_clarifying_questions_count":
                state = self.snapshot.get("state")
                if isinstance(state, dict):
                    return derive_open_clarifying_questions_count(state)
                return 0
            state = self.snapshot.get("state")
            if not isinstance(state, dict):
                return None
            return state.get(field)
        if root == "config":
            config = self.snapshot.get("config")
            if not isinstance(config, dict):
                config = {}
            if parts == ["config", "review", "enabled"]:
                review = config.get("review")
                if isinstance(review, dict):
                    return bool(review.get("enabled"))
                return False
            if len(parts) == 3 and parts[1] == "limits":
                limits = config.get("limits")
                if not isinstance(limits, dict):
                    limits = {}
                value = limits.get(parts[2])
                if isinstance(value, (int, float)):
                    return int(value)
                return self._default_limit(parts[2])
            raise WhenExpressionError(self.expr, f"Unsupported config path: {'.'.join(parts)}")
        raise WhenExpressionError(self.expr, f"Unsupported path root {root!r}")

    def _history_call(self, method: str, raw_args: list[Any]) -> Any:
        kwargs: dict[str, Any] = {}
        event_type: str | None = None
        for arg in raw_args:
            if arg[0] == "lit" and event_type is None:
                event_type = str(arg[1])
            elif arg[0] == "kwarg":
                kwargs[arg[1]] = self._eval_arg_value(arg[2])
        if event_type is None:
            raise WhenExpressionError(self.expr, "history call missing event type")
        if method == "count":
            return self._history_count(event_type, kwargs)
        if method == "last":
            return self._history_last(event_type, kwargs)
        raise WhenExpressionError(self.expr, f"Unsupported history.{method}")

    def _eval_arg_value(self, node: Any) -> Any:
        if node[0] == "attr" and node[1][0] == "name" and node[1][1] == "visit" and node[2] == "id":
            return self.visit_id
        if node[0] == "lit":
            return node[1]
        if node[0] == "name":
            return self._resolve_name(node[1])
        if node[0] == "attr":
            return self._eval_path_value(node)
        return self.eval(node)

    def _receipt_visit_id_for_intake(self) -> str:
        receipt_visit_id = self.visit_id
        if self.gate_node in ("execute.intake.gate", "verify.intake.gate"):
            from foundry_cli.engine.hooks import _latest_sealed_visit_id

            intake_node = "execute.intake" if self.gate_node.startswith("execute.") else "verify.intake"
            prior_intake = _latest_sealed_visit_id(self.snapshot, intake_node)
            if prior_intake:
                receipt_visit_id = prior_intake
        return receipt_visit_id

    def _history_count(self, event_type: str, kwargs: dict[str, Any]) -> int:
        visit_id = kwargs.get("visit_id")
        if visit_id is not None and not isinstance(visit_id, str):
            visit_id = str(visit_id)
        schema = kwargs.get("schema")
        if isinstance(schema, str) and "intake-receipt" in schema:
            visit_id = self._receipt_visit_id_for_intake()
        node_id = kwargs.get("node_id")
        loop = kwargs.get("loop")
        return count_events(
            self.snapshot,
            event_type,
            visit_id=visit_id if isinstance(visit_id, str) else None,
            node_id=node_id if isinstance(node_id, str) else None,
            schema=schema if isinstance(schema, str) else None,
            loop=loop if isinstance(loop, str) else None,
        )

    def _history_last(self, event_type: str, kwargs: dict[str, Any]) -> dict[str, Any] | None:
        node_id = kwargs.get("node_id")
        visit_id = kwargs.get("visit_id")
        event = last_event(
            self.snapshot,
            event_type,
            node_id=node_id if isinstance(node_id, str) else None,
            visit_id=visit_id if isinstance(visit_id, str) else None,
        )
        if event is None:
            return None
        payload = event.get("payload") or {}
        view: dict[str, Any] = {"_event": event}
        if isinstance(payload, dict):
            for key in ("outcome", "decision", "schema"):
                if key in payload:
                    view[key] = payload[key]
        return view

    def eval_node(self, node: Any) -> Any:
        if node[0] == "attr" and node[1][0] == "name":
            root = node[1][1]
            if root in ("config", "state", "visit") and root not in self.names:
                return self._eval_path_value(node)
        if node[0] == "attr" and node[1][0] == "attr" and not self._rooted_in_names(node):
            return self._eval_path_value(node)
        return self.eval(node)

    def _rooted_in_names(self, node: Any) -> bool:
        current = node
        while current[0] == "attr":
            current = current[1]
        return current[0] == "name" and current[1] in self.names


def _coerce_bool(value: Any, expr: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    raise WhenExpressionError(expr, f"When expression must be boolean, got {type(value).__name__}")


def evaluate_when_expression(snapshot: dict[str, Any], visit: dict[str, Any], expr: str) -> bool:
    """Evaluate a catalog when expression against snapshot and active visit."""
    expr = expr.strip()
    normalized = _normalize_expr(expr)
    if not _expression_is_supported(normalized):
        raise WhenExpressionError(expr)
    try:
        tree = _Parser.parse(normalized)
    except WhenExpressionError:
        raise
    except Exception as exc:
        raise WhenExpressionError(expr, str(exc)) from exc
    ctx = _EvalContext(snapshot, visit, expr)
    try:
        result = ctx.eval_node(tree)
    except WhenExpressionError:
        raise
    except Exception as exc:
        raise WhenExpressionError(expr, str(exc)) from exc
    return _coerce_bool(result, expr)


def evaluate_expression(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    expr: str,
    *,
    names: dict[str, Any] | None = None,
) -> Any:
    """Evaluate an expression with extra root ``names`` (e.g. gate ``evidence``); no registry marker check."""
    normalized = _normalize_expr(expr.strip())
    try:
        tree = _Parser.parse(normalized)
    except WhenExpressionError:
        raise
    except Exception as exc:
        raise WhenExpressionError(expr, str(exc)) from exc
    ctx = _EvalContext(snapshot, visit, expr, names)
    try:
        return ctx.eval_node(tree)
    except WhenExpressionError:
        raise
    except Exception as exc:
        raise WhenExpressionError(expr, str(exc)) from exc


def evaluate_condition(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    expr: str,
    *,
    names: dict[str, Any] | None = None,
) -> bool:
    return _coerce_bool(evaluate_expression(snapshot, visit, expr, names=names), expr)
