from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .analyzer import FieldCandidate, draft_scenarios, infer_field
from .contracts import validate_contract_data


class PageObjectImportError(ValueError):
    """Raised when a page object cannot be imported as a contract."""


@dataclass(frozen=True)
class PageObjectControl:
    name: str = ""
    label: str = ""
    placeholder: str = ""
    input_type: str = ""
    selector: str = ""
    required: bool = False
    constraints: dict[str, Any] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)
    source_language: str = ""
    source_kind: str = "locator"
    line: int = 0

    def to_candidate(self) -> FieldCandidate:
        return FieldCandidate(
            name=self.name,
            label=self.label,
            input_type=self.input_type,
            placeholder=self.placeholder,
            selector=self.selector,
            required=self.required,
            constraints=self.constraints,
            options=self.options,
        )


LANGUAGE_SUFFIXES = {
    ".java": "java",
    ".js": "typescript",
    ".jsx": "typescript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".py": "python",
}

LANGUAGE_ALIASES = {
    "java": "java",
    "js": "typescript",
    "jsx": "typescript",
    "javascript": "typescript",
    "ts": "typescript",
    "tsx": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
}

STRING_PATTERN = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`'
STRING_RE = re.compile(STRING_PATTERN, re.DOTALL)
ASSIGNMENT_RE = re.compile(
    rf"(?P<target>(?:this\.)?[A-Za-z_$][\w$]*)\s*(?::[^=;\n]+)?=\s*(?P<expr>[^;]+);",
    re.DOTALL,
)
FIND_BY_RE = re.compile(
    r"@FindBy\s*\((?P<args>.*?)\)\s*"
    r"(?:@\w+(?:\s*\([^)]*\))?\s*)*"
    r"(?:(?:private|protected|public|static|final|transient|volatile)\s+)*"
    r"(?:[\w$<>?,.\s\[\]]+\s+)?"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*(?:[;=])",
    re.DOTALL,
)
METHOD_HEADER_RE = re.compile(
    r"(?:(?:public|private|protected|async|static|final|override|readonly)\s+)*"
    r"(?:[\w$<>\[\],.?]+\s+)*"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"\((?P<params>[^)]*)\)\s*"
    r"(?:throws\s+[^{]+)?"
    r"(?::\s*[^{]+)?\s*\{",
    re.DOTALL,
)

LOCATOR_METHODS = {
    "locator",
    "getByLabel",
    "getByPlaceholder",
    "getByRole",
    "getByTestId",
    "id",
    "name",
    "css",
    "cssSelector",
    "xpath",
    "className",
    "tagName",
}
PLAYWRIGHT_ACTIONS = {
    "fill": "text",
    "type": "text",
    "selectOption": "select",
    "select_option": "select",
    "check": "checkbox",
    "uncheck": "checkbox",
    "setInputFiles": "file",
    "set_input_files": "file",
}
SKIPPED_ROLES = {
    "alert",
    "button",
    "heading",
    "img",
    "link",
    "menuitem",
    "status",
    "tab",
}
ROLE_INPUT_TYPES = {
    "checkbox": "checkbox",
    "combobox": "select",
    "listbox": "select",
    "radio": "radio",
    "searchbox": "search",
    "spinbutton": "number",
    "textbox": "text",
}
ACTION_WORDS = {
    "back",
    "button",
    "btn",
    "cancel",
    "click",
    "close",
    "continue",
    "link",
    "login",
    "next",
    "save",
    "sign",
    "submit",
}
CONTROL_SUFFIXES = {
    "box",
    "by",
    "checkbox",
    "combo",
    "combobox",
    "control",
    "dropdown",
    "element",
    "field",
    "input",
    "locator",
    "radio",
    "select",
    "textbox",
}
CONTROL_PREFIXES = {
    "check",
    "choose",
    "enter",
    "fill",
    "find",
    "get",
    "input",
    "locate",
    "provide",
    "select",
    "set",
    "toggle",
    "type",
}


def import_page_object_file(
    path: str | Path,
    *,
    contract_id: str | None = None,
    locale: dict[str, str] | None = None,
) -> dict[str, Any]:
    page_object_path = Path(path)
    source_text = page_object_path.read_text(encoding="utf-8")
    return import_page_object_contract(
        source_text,
        contract_id=contract_id,
        source_value=str(page_object_path),
        locale=locale,
        language=_language_from_path(page_object_path),
    )


def import_page_object_contract(
    source_text: str,
    *,
    contract_id: str | None = None,
    source_value: str = "page-object",
    locale: dict[str, str] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    resolved_language = _resolve_language(language, source_value, source_text)
    controls = parse_page_object_controls(
        source_text,
        language=resolved_language,
        source_name=source_value,
    )
    contract = build_page_object_contract(
        controls,
        source=source_value,
        contract_id=contract_id or _class_name(source_text, resolved_language),
        locale=locale,
    )
    _validate_page_object_contract(contract)
    return contract


def parse_page_object_controls(
    source_text: str,
    *,
    language: str | None = None,
    source_name: str = "page-object",
) -> list[PageObjectControl]:
    if not source_text.strip():
        raise PageObjectImportError(f"Page object source is empty: {source_name}")

    resolved_language = _resolve_language(language, source_name, source_text)
    if resolved_language == "python":
        controls = _parse_python_controls(source_text)
    elif resolved_language in {"java", "typescript"}:
        controls = _parse_c_style_controls(source_text, language=resolved_language)
    else:
        raise PageObjectImportError(f"Unsupported page object language: {resolved_language}")

    controls = _dedupe_controls(control for control in controls if not _looks_like_action_control(control))
    if not controls:
        raise PageObjectImportError(f"No supported page object controls were found in {source_name}")
    return controls


def build_page_object_contract(
    controls: Sequence[PageObjectControl],
    *,
    source: str,
    contract_id: str | None = None,
    locale: dict[str, str] | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    used_keys: set[str] = set()

    for index, control in enumerate(controls, start=1):
        field_key = _unique_field_key(control, index, used_keys)
        field = infer_field(control.to_candidate())
        _prepend_inference_signals(
            field,
            [
                f"page_object:{control.source_language}",
                f"page_object:{control.source_kind}",
                *([f"page_object:line={control.line}"] if control.line else []),
            ],
        )
        fields[field_key] = field

    if not fields:
        raise PageObjectImportError("No supported page object controls were found")

    resolved_contract_id = _contract_id(contract_id or _source_contract_name(source))
    return {
        "schemaVersion": "1.0",
        "id": resolved_contract_id,
        "source": {
            "type": "page_object",
            "value": source,
        },
        "locale": locale or {"language": "en"},
        "fields": fields,
        "scenarios": draft_scenarios(
            fields,
            positive_id="valid_page_object",
            positive_description="All imported page object controls contain valid values.",
        ),
        "generation": {
            "deterministic": True,
            "defaultSeed": f"{resolved_contract_id}-page-object",
        },
        "validation": {
            "status": "needs_review",
        },
    }


def _validate_page_object_contract(contract: dict[str, Any]) -> None:
    result = validate_contract_data(contract)
    if not result.is_valid:
        errors = [
            f"{finding.field or '<root>'}: {finding.message}"
            for finding in result.findings
            if finding.severity == "error"
        ]
        message = "; ".join(errors) if errors else f"validation status is {result.status}"
        raise PageObjectImportError(f"Imported page object contract is invalid: {message}")


def _parse_c_style_controls(source_text: str, *, language: str) -> list[PageObjectControl]:
    code = _strip_c_style_comments(source_text)
    controls: list[PageObjectControl] = []

    if language == "java":
        for match in FIND_BY_RE.finditer(code):
            control = _control_from_find_by(
                match.group("args"),
                name=match.group("name"),
                language=language,
                line=_line_for_index(code, match.start()),
            )
            if control:
                controls.append(control)

    for match in ASSIGNMENT_RE.finditer(code):
        target_name = _clean_target_name(match.group("target"))
        control = _control_from_c_expression(
            match.group("expr"),
            name=target_name,
            language=language,
            source_kind="locator_field",
            line=_line_for_index(code, match.start()),
        )
        if control:
            controls.append(control)

    for method_name, body, body_start in _iter_c_style_method_bodies(code):
        controls.extend(
            _controls_from_c_action_body(
                body,
                method_name=method_name,
                language=language,
                offset=body_start,
                source_text=code,
            )
        )

    return controls


def _control_from_find_by(args: str, *, name: str, language: str, line: int) -> PageObjectControl | None:
    how_match = re.search(rf"how\s*=\s*How\.(?P<how>\w+).*?using\s*=\s*(?P<value>{STRING_PATTERN})", args, re.DOTALL)
    if how_match:
        return _control_from_locator(
            how_match.group("how"),
            _unquote_string(how_match.group("value")),
            name=name,
            language=language,
            source_kind="find_by",
            line=line,
        )

    for key, strategy in (
        ("css", "css"),
        ("cssSelector", "css"),
        ("xpath", "xpath"),
        ("id", "id"),
        ("name", "name"),
        ("className", "className"),
        ("tagName", "tagName"),
    ):
        match = re.search(rf"\b{key}\s*=\s*(?P<value>{STRING_PATTERN})", args, re.DOTALL)
        if match:
            return _control_from_locator(
                strategy,
                _unquote_string(match.group("value")),
                name=name,
                language=language,
                source_kind="find_by",
                line=line,
            )
    return None


def _control_from_c_expression(
    expression: str,
    *,
    name: str,
    language: str,
    source_kind: str,
    line: int,
) -> PageObjectControl | None:
    for method, args in _iter_calls(expression, LOCATOR_METHODS):
        strings = _string_literals(args)
        if method in {"id", "name", "css", "cssSelector", "xpath", "className", "tagName"}:
            if not _is_by_call(expression, method) or not strings:
                continue
            strategy = "css" if method in {"css", "cssSelector"} else method
            return _control_from_locator(
                strategy,
                strings[0],
                name=name,
                language=language,
                source_kind=source_kind,
                line=line,
            )

        if method == "locator" and strings:
            return _control_from_locator(
                "css_or_xpath",
                strings[0],
                name=name,
                language=language,
                source_kind=source_kind,
                line=line,
            )
        if method == "getByLabel" and strings:
            return _control_from_locator(
                "label",
                strings[0],
                name=name,
                label=strings[0],
                language=language,
                source_kind=source_kind,
                line=line,
            )
        if method == "getByPlaceholder" and strings:
            return _control_from_locator(
                "placeholder",
                strings[0],
                name=name,
                placeholder=strings[0],
                language=language,
                source_kind=source_kind,
                line=line,
            )
        if method == "getByTestId" and strings:
            return _control_from_locator(
                "testid",
                strings[0],
                name=name,
                language=language,
                source_kind=source_kind,
                line=line,
            )
        if method == "getByRole" and strings:
            role = strings[0].lower()
            if role in SKIPPED_ROLES:
                return None
            label = _role_name_from_args(args)
            return _control_from_locator(
                "role",
                label or role,
                name=name,
                label=label,
                input_type=ROLE_INPUT_TYPES.get(role, ""),
                language=language,
                source_kind=source_kind,
                line=line,
            )
    return None


def _controls_from_c_action_body(
    body: str,
    *,
    method_name: str,
    language: str,
    offset: int,
    source_text: str,
) -> list[PageObjectControl]:
    controls: list[PageObjectControl] = []

    for action, args, start in _iter_calls_with_positions(body, PLAYWRIGHT_ACTIONS):
        strings = _string_literals(args)
        if not strings:
            continue
        call_name = _name_from_method_context(method_name, args)
        control = _control_from_locator(
            "css_or_xpath",
            strings[0],
            name=call_name,
            input_type=PLAYWRIGHT_ACTIONS[action],
            language=language,
            source_kind=f"method:{action}",
            line=_line_for_index(source_text, offset + start),
        )
        if control:
            controls.append(control)

    selenium_action_re = re.compile(
        rf"findElement\s*\(\s*(?P<locator>By\.\w+\s*\(\s*(?:{STRING_PATTERN})\s*\))\s*\)"
        r"\s*\.\s*(?P<action>sendKeys|click)\s*\((?P<args>[^)]*)\)",
        re.DOTALL,
    )
    for match in selenium_action_re.finditer(body):
        if match.group("action") == "click" and not _looks_checkbox_text(method_name):
            continue
        call_name = _name_from_method_context(method_name, match.group("args"))
        control = _control_from_c_expression(
            match.group("locator"),
            name=call_name,
            language=language,
            source_kind=f"method:{match.group('action')}",
            line=_line_for_index(source_text, offset + match.start()),
        )
        if control:
            controls.append(control)

    return controls


def _parse_python_controls(source_text: str) -> list[PageObjectControl]:
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise PageObjectImportError(f"Unable to parse Python page object: {exc.msg}") from exc

    parser = _PythonPageObjectVisitor()
    parser.visit(tree)
    return parser.controls


class _PythonPageObjectVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.controls: list[PageObjectControl] = []
        self.method_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.method_stack.append(node.name)
        self.generic_visit(node)
        self.method_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            name = _python_target_name(target)
            if not name:
                continue
            control = _control_from_python_expr(
                node.value,
                name=name,
                source_kind="locator_field",
                line=node.lineno,
            )
            if control:
                self.controls.append(control)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        name = _python_target_name(node.target)
        if name and node.value is not None:
            control = _control_from_python_expr(
                node.value,
                name=name,
                source_kind="locator_field",
                line=node.lineno,
            )
            if control:
                self.controls.append(control)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        method_name = self.method_stack[-1] if self.method_stack else ""
        control = _control_from_python_action_call(node, method_name=method_name)
        if control:
            self.controls.append(control)
        self.generic_visit(node)


def _control_from_python_expr(
    node: ast.AST,
    *,
    name: str,
    source_kind: str,
    line: int,
) -> PageObjectControl | None:
    if isinstance(node, ast.Tuple) and len(node.elts) >= 2:
        strategy = _python_by_strategy(node.elts[0])
        value = _literal_string(node.elts[1])
        if strategy and value:
            return _control_from_locator(
                strategy,
                value,
                name=name,
                language="python",
                source_kind=source_kind,
                line=line,
            )

    if not isinstance(node, ast.Call):
        return None

    method = _python_call_name(node)
    if method in {"find_element", "find_elements"} and len(node.args) >= 2:
        strategy = _python_by_strategy(node.args[0])
        value = _literal_string(node.args[1])
        if strategy and value:
            return _control_from_locator(
                strategy,
                value,
                name=name,
                language="python",
                source_kind=source_kind,
                line=line,
            )

    if method == "locator" and node.args:
        value = _literal_string(node.args[0])
        if value:
            return _control_from_locator(
                "css_or_xpath",
                value,
                name=name,
                language="python",
                source_kind=source_kind,
                line=line,
            )
    if method == "get_by_label" and node.args:
        label = _literal_string(node.args[0])
        if label:
            return _control_from_locator(
                "label",
                label,
                name=name,
                label=label,
                language="python",
                source_kind=source_kind,
                line=line,
            )
    if method == "get_by_placeholder" and node.args:
        placeholder = _literal_string(node.args[0])
        if placeholder:
            return _control_from_locator(
                "placeholder",
                placeholder,
                name=name,
                placeholder=placeholder,
                language="python",
                source_kind=source_kind,
                line=line,
            )
    if method == "get_by_test_id" and node.args:
        value = _literal_string(node.args[0])
        if value:
            return _control_from_locator(
                "testid",
                value,
                name=name,
                language="python",
                source_kind=source_kind,
                line=line,
            )
    if method == "get_by_role" and node.args:
        role = (_literal_string(node.args[0]) or "").lower()
        if role in SKIPPED_ROLES:
            return None
        label = _python_keyword_string(node, "name")
        return _control_from_locator(
            "role",
            label or role,
            name=name,
            label=label,
            input_type=ROLE_INPUT_TYPES.get(role, ""),
            language="python",
            source_kind=source_kind,
            line=line,
        )
    return None


def _control_from_python_action_call(node: ast.Call, *, method_name: str) -> PageObjectControl | None:
    method = _python_call_name(node)
    if method in PLAYWRIGHT_ACTIONS and node.args:
        selector = _literal_string(node.args[0])
        if selector:
            name = _name_from_python_method_context(method_name, node.args[1:])
            return _control_from_locator(
                "css_or_xpath",
                selector,
                name=name,
                input_type=PLAYWRIGHT_ACTIONS[method],
                language="python",
                source_kind=f"method:{method}",
                line=getattr(node, "lineno", 0),
            )

    if method in {"send_keys", "click"} and isinstance(node.func, ast.Attribute):
        if method == "click" and not _looks_checkbox_text(method_name):
            return None
        receiver = node.func.value
        if isinstance(receiver, ast.Call):
            name = _name_from_python_method_context(method_name, node.args)
            return _control_from_python_expr(
                receiver,
                name=name,
                source_kind=f"method:{method}",
                line=getattr(node, "lineno", 0),
            )
    return None


def _control_from_locator(
    strategy: str,
    value: str,
    *,
    name: str = "",
    label: str = "",
    placeholder: str = "",
    input_type: str = "",
    language: str,
    source_kind: str,
    line: int,
) -> PageObjectControl | None:
    selector = _selector_for(strategy, value)
    selector_name = _name_from_selector(selector)
    semantic_name = _semantic_name(name) or _semantic_name(selector_name)
    resolved_label = label or _label_from_selector(selector)
    resolved_placeholder = placeholder or _placeholder_from_selector(selector)
    resolved_input_type = input_type or _input_type_from_selector(selector)
    constraints = _constraints_from_selector(selector)

    if resolved_input_type == "file":
        return None

    if not semantic_name:
        semantic_name = _semantic_name(resolved_label or resolved_placeholder or value)

    if not resolved_label and semantic_name:
        resolved_label = _humanize(semantic_name)

    control = PageObjectControl(
        name=semantic_name,
        label=resolved_label,
        placeholder=resolved_placeholder,
        input_type=resolved_input_type,
        selector=selector,
        required=_required_from_selector(selector),
        constraints=constraints,
        source_language=language,
        source_kind=source_kind,
        line=line,
    )
    if _looks_like_action_control(control):
        return None
    return control


def _selector_for(strategy: str, value: str) -> str:
    normalized = strategy.lower().replace("_", "").replace("-", "")
    if normalized == "id":
        return f"#{value}"
    if normalized == "name":
        return f'[name="{_escape_selector_value(value)}"]'
    if normalized in {"css", "cssselector", "cssorxpath"}:
        return value
    if normalized == "xpath":
        return value
    if normalized == "testid":
        return f'[data-testid="{_escape_selector_value(value)}"]'
    if normalized == "label":
        return f'getByLabel("{_escape_selector_value(value)}")'
    if normalized == "placeholder":
        return f'getByPlaceholder("{_escape_selector_value(value)}")'
    if normalized == "role":
        return f'getByRole("{_escape_selector_value(value)}")'
    if normalized == "classname":
        return f".{value}"
    return value


def _dedupe_controls(controls: Iterable[PageObjectControl]) -> list[PageObjectControl]:
    merged: dict[str, PageObjectControl] = {}
    for control in controls:
        key = _dedupe_key(control)
        if key in merged:
            merged[key] = _merge_controls(merged[key], control)
        else:
            merged[key] = control
    return list(merged.values())


def _merge_controls(left: PageObjectControl, right: PageObjectControl) -> PageObjectControl:
    constraints = dict(left.constraints)
    constraints.update(right.constraints)
    return PageObjectControl(
        name=_better_name(left.name, right.name),
        label=left.label or right.label,
        placeholder=left.placeholder or right.placeholder,
        input_type=left.input_type or right.input_type,
        selector=left.selector or right.selector,
        required=left.required or right.required,
        constraints=constraints,
        options=left.options or right.options,
        source_language=left.source_language or right.source_language,
        source_kind=_merge_source_kind(left.source_kind, right.source_kind),
        line=left.line or right.line,
    )


def _dedupe_key(control: PageObjectControl) -> str:
    if control.selector:
        return f"selector:{control.selector}"
    if control.name:
        return f"name:{control.name.lower()}"
    return f"label:{control.label.lower()}"


def _merge_source_kind(left: str, right: str) -> str:
    if not left:
        return right
    if not right or left == right:
        return left
    return f"{left}+{right}"


def _better_name(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    left_words = _words(left)
    right_words = _words(right)
    if len(right_words) < len(left_words):
        return right
    return left


def _looks_like_action_control(control: PageObjectControl) -> bool:
    if control.input_type in {"checkbox", "radio", "select"}:
        return False
    words = set(_words(" ".join([control.name, control.label, control.selector])))
    return "button" in words or "btn" in words or bool(words & ACTION_WORDS and words & {"submit", "click", "save", "cancel"})


def _looks_checkbox_text(value: str) -> bool:
    words = set(_words(value))
    return bool(words & {"agree", "checkbox", "check", "consent", "terms", "toggle"})


def _unique_field_key(control: PageObjectControl, index: int, used_keys: set[str]) -> str:
    raw_key = control.name or _name_from_selector(control.selector) or control.label or control.placeholder or f"field{index}"
    base = _field_key_base(raw_key) or f"field{index}"
    key = base
    suffix = 2
    while key in used_keys:
        key = f"{base}{suffix}"
        suffix += 1
    used_keys.add(key)
    return key


def _field_key_base(value: str) -> str:
    semantic = _semantic_name(value)
    if semantic and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", semantic):
        return semantic

    tokens = re.findall(r"[A-Za-z0-9]+", semantic or value)
    if not tokens:
        return ""

    first, *rest = tokens
    key = first.lower() + "".join(token[:1].upper() + token[1:] for token in rest)
    if key[0].isdigit():
        key = f"field{key}"
    return key


def _semantic_name(value: str) -> str:
    text = _clean_target_name(value)
    words = _words(text)
    while len(words) > 1 and words[0] in CONTROL_PREFIXES:
        words = words[1:]
    while len(words) > 1 and words[-1] in CONTROL_SUFFIXES:
        words = words[:-1]
    if not words:
        return ""
    first, *rest = words
    return first + "".join(word[:1].upper() + word[1:] for word in rest)


def _words(value: str) -> list[str]:
    text = _clean_target_name(value)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return [part.lower() for part in re.findall(r"[A-Za-z0-9]+", text)]


def _humanize(value: str) -> str:
    words = _words(value)
    if not words:
        return value
    return " ".join(words).capitalize()


def _clean_target_name(value: str) -> str:
    text = value.strip()
    if text.startswith("this."):
        text = text[5:]
    if text.startswith("self."):
        text = text[5:]
    return text.lstrip("_").replace("$", "")


def _selector_attributes(selector: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    css_attr_re = re.compile(
        rf"\[\s*(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*(?:[~|^$*]?=\s*(?P<value>{STRING_PATTERN}|[^\]\s]+))?\s*\]",
        re.DOTALL,
    )
    for match in css_attr_re.finditer(selector):
        name = match.group("name").lower()
        value = match.group("value")
        attrs[name] = _unquote_string(value) if value else "true"

    xpath_attr_re = re.compile(
        rf"@(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?P<value>{STRING_PATTERN})",
        re.DOTALL,
    )
    for match in xpath_attr_re.finditer(selector):
        attrs.setdefault(match.group("name").lower(), _unquote_string(match.group("value")))
    return attrs


def _constraints_from_selector(selector: str) -> dict[str, Any]:
    attrs = _selector_attributes(selector)
    constraints: dict[str, Any] = {}
    for attr_name, constraint_name in (("minlength", "minLength"), ("maxlength", "maxLength")):
        value = _parse_int(attrs.get(attr_name, ""))
        if value is not None:
            constraints[constraint_name] = value
    for attr_name, constraint_name in (("min", "minimum"), ("max", "maximum")):
        value = _parse_number(attrs.get(attr_name, ""))
        if value is not None:
            constraints[constraint_name] = value
    if attrs.get("pattern"):
        constraints["pattern"] = attrs["pattern"]
    return constraints


def _input_type_from_selector(selector: str) -> str:
    lower = selector.lower()
    attrs = _selector_attributes(selector)
    input_type = attrs.get("type", "").lower()
    if input_type:
        return input_type
    if "textarea" in lower:
        return "textarea"
    if "select" in lower:
        return "select"
    if "checkbox" in lower:
        return "checkbox"
    return ""


def _required_from_selector(selector: str) -> bool:
    attrs = _selector_attributes(selector)
    return attrs.get("required") == "true" or attrs.get("aria-required", "").lower() == "true"


def _name_from_selector(selector: str) -> str:
    attrs = _selector_attributes(selector)
    for name in ("name", "id", "data-testid", "data-test", "data-cy"):
        if attrs.get(name):
            return attrs[name]

    id_match = re.search(r"#([A-Za-z_][\w:-]*)", selector)
    if id_match:
        return id_match.group(1)
    return ""


def _label_from_selector(selector: str) -> str:
    attrs = _selector_attributes(selector)
    return attrs.get("aria-label", "")


def _placeholder_from_selector(selector: str) -> str:
    return _selector_attributes(selector).get("placeholder", "")


def _role_name_from_args(args: str) -> str:
    name_match = re.search(rf"\bname\s*[:=]\s*(?P<value>{STRING_PATTERN})", args, re.DOTALL)
    if name_match:
        return _unquote_string(name_match.group("value"))
    strings = _string_literals(args)
    return strings[1] if len(strings) > 1 else ""


def _name_from_method_context(method_name: str, call_args: str) -> str:
    name = _semantic_name(method_name)
    if name and name not in {"form", "page"}:
        return name
    strings = _string_literals(call_args)
    tail = call_args
    if strings:
        first_literal = re.search(re.escape(strings[0]), call_args)
        if first_literal:
            tail = call_args[first_literal.end() :]
    variable_match = re.search(r",\s*(?P<name>[A-Za-z_$][\w$]*)", tail)
    return _semantic_name(variable_match.group("name")) if variable_match else name


def _name_from_python_method_context(method_name: str, args: Sequence[ast.AST]) -> str:
    name = _semantic_name(method_name)
    if name and name not in {"form", "page"}:
        return name
    for arg in args:
        if isinstance(arg, ast.Name):
            return _semantic_name(arg.id)
        if isinstance(arg, ast.Attribute):
            return _semantic_name(arg.attr)
    return name


def _iter_c_style_method_bodies(source: str) -> Iterable[tuple[str, str, int]]:
    for match in METHOD_HEADER_RE.finditer(source):
        method_name = match.group("name")
        if method_name in {"if", "for", "while", "switch", "catch", "function"}:
            continue
        open_brace = source.find("{", match.end() - 1)
        if open_brace < 0:
            continue
        close_brace = _matching_brace(source, open_brace)
        if close_brace < 0:
            continue
        yield method_name, source[open_brace + 1 : close_brace], open_brace + 1


def _matching_brace(source: str, open_brace: int) -> int:
    depth = 0
    in_string = ""
    escaped = False
    for index in range(open_brace, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = ""
            continue
        if char in "\"'`":
            in_string = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _iter_calls(expression: str, method_names: set[str]) -> Iterable[tuple[str, str]]:
    for method, args, _start in _iter_calls_with_positions(expression, method_names):
        yield method, args


def _iter_calls_with_positions(expression: str, method_names: set[str]) -> Iterable[tuple[str, str, int]]:
    method_pattern = "|".join(re.escape(method) for method in sorted(method_names, key=len, reverse=True))
    call_re = re.compile(rf"\b(?P<method>{method_pattern})\s*\(")
    for match in call_re.finditer(expression):
        args_start = match.end() - 1
        args_end = _matching_paren(expression, args_start)
        if args_end < 0:
            continue
        yield match.group("method"), expression[args_start + 1 : args_end], match.start()


def _matching_paren(source: str, open_paren: int) -> int:
    depth = 0
    in_string = ""
    escaped = False
    for index in range(open_paren, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = ""
            continue
        if char in "\"'`":
            in_string = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _is_by_call(expression: str, method: str) -> bool:
    return re.search(rf"\bBy\s*\.\s*{re.escape(method)}\s*\(", expression) is not None


def _strip_c_style_comments(source: str) -> str:
    output: list[str] = []
    index = 0
    in_string = ""
    escaped = False
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = ""
            index += 1
            continue
        if char in "\"'`":
            in_string = char
            output.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            while index < len(source) and source[index] != "\n":
                index += 1
            output.append("\n")
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(source) and not (source[index] == "*" and source[index + 1] == "/"):
                output.append("\n" if source[index] == "\n" else " ")
                index += 1
            index += 2
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _python_target_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _python_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _python_by_strategy(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr.lower().replace("_", "")
    value = _literal_string(node)
    return value.lower().replace("_", "") if value else ""


def _python_keyword_string(node: ast.Call, keyword_name: str) -> str:
    for keyword in node.keywords:
        if keyword.arg == keyword_name:
            return _literal_string(keyword.value)
    return ""


def _literal_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _string_literals(value: str) -> list[str]:
    return [_unquote_string(match.group(0)) for match in STRING_RE.finditer(value)]


def _unquote_string(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    if len(text) < 2 or text[0] not in "\"'`":
        return text
    quote = text[0]
    body = text[1:-1]
    return body.replace(f"\\{quote}", quote).replace("\\\\", "\\")


def _escape_selector_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_number(value: str) -> int | float | None:
    if value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def _prepend_inference_signals(field: dict[str, Any], signals: Sequence[str]) -> None:
    inference = field.setdefault("inference", {"confidence": 0.4, "signals": []})
    existing = list(inference.get("signals", []))
    prefix = [signal for signal in signals if signal and signal not in existing]
    inference["signals"] = prefix + existing


def _language_from_path(path: Path) -> str:
    language = LANGUAGE_SUFFIXES.get(path.suffix.lower())
    if language:
        return language
    raise PageObjectImportError(f"Unsupported page object file extension: {path.suffix or '<none>'}")


def _resolve_language(language: str | None, source_value: str, source_text: str) -> str:
    if language:
        normalized = LANGUAGE_ALIASES.get(language.lower())
        if normalized:
            return normalized
        raise PageObjectImportError(f"Unsupported page object language: {language}")

    suffix_language = LANGUAGE_SUFFIXES.get(Path(source_value).suffix.lower())
    if suffix_language:
        return suffix_language

    if re.search(r"\bdef\s+\w+\s*\(|\bself\.", source_text):
        return "python"
    if "@FindBy" in source_text or "By." in source_text:
        return "java"
    if "locator(" in source_text or "getBy" in source_text:
        return "typescript"
    raise PageObjectImportError("Unable to determine page object language")


def _class_name(source_text: str, language: str) -> str | None:
    if language == "python":
        match = re.search(r"\bclass\s+([A-Za-z_]\w*)", source_text)
    else:
        match = re.search(r"\bclass\s+([A-Za-z_$][\w$]*)", source_text)
    return match.group(1) if match else None


def _source_contract_name(source_value: str) -> str:
    source = source_value.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0].rstrip("/\\")
    name = re.split(r"[/\\]", source)[-1]
    if "." in name:
        return name.rsplit(".", maxsplit=1)[0]
    return name or "page-object"


def _contract_id(value: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value.strip())
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "page-object"


def _line_for_index(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1
