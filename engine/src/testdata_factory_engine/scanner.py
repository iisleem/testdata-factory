from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .analyzer import FieldCandidate, draft_scenarios, infer_field
from .contracts import validate_contract_data


class ScannerError(ValueError):
    """Raised when a page cannot be scanned into a contract draft."""


class ScannerDependencyError(ScannerError):
    """Raised when browser scanning dependencies are not available."""


@dataclass(frozen=True)
class ScannedOption:
    label: str = ""
    value: str = ""
    disabled: bool = False
    selected: bool = False

    @property
    def choice_value(self) -> str:
        return self.value or self.label


@dataclass(frozen=True)
class ScannedControl:
    tag: str
    input_type: str
    selector: str = ""
    id: str = ""
    name: str = ""
    label: str = ""
    placeholder: str = ""
    autocomplete: str = ""
    required: bool = False
    aria: dict[str, Any] = field(default_factory=dict)
    validation_attributes: dict[str, str] = field(default_factory=dict)
    options: list[ScannedOption] = field(default_factory=list)

    def to_candidate(self) -> FieldCandidate:
        return FieldCandidate(
            name=self.name or self.id or self.label,
            label=self.label,
            input_type=self.input_type,
            placeholder=self.placeholder,
            autocomplete=self.autocomplete,
            selector=self.selector,
            required=self.required,
            constraints=_constraints_from_validation(self.input_type, self.validation_attributes),
            options=_option_values(self.options),
        )


def scan_contract_draft(
    source: str | Path,
    *,
    contract_id: str | None = None,
    locale_language: str = "en",
    locale_country: str | None = None,
    timeout_ms: int = 10_000,
) -> dict[str, Any]:
    """Scan a URL or local HTML file with Playwright and return a valid contract draft."""

    url = _source_to_url(source)
    controls = scan_controls(url, timeout_ms=timeout_ms)
    return build_contract_draft(
        controls,
        source=url,
        contract_id=contract_id,
        locale_language=locale_language,
        locale_country=locale_country,
    )


def scan_controls(source_url: str, *, timeout_ms: int = 10_000) -> list[ScannedControl]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ScannerDependencyError(
            "Playwright is required for URL scanning. Install the scanner extra with "
            "`python -m pip install -e 'engine[scanner]'`."
        ) from exc

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            raise ScannerDependencyError(
                "Chromium is required for URL scanning. Install it with "
                "`python -m playwright install chromium`."
            ) from exc

        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(source_url, wait_until="domcontentloaded", timeout=timeout_ms)
            return controls_from_payload(page.evaluate(_FORM_CONTROL_SCRIPT))
        except PlaywrightError as exc:
            raise ScannerError(f"Unable to scan {source_url}: {exc}") from exc
        finally:
            browser.close()


def controls_from_payload(payload: Sequence[Mapping[str, Any]]) -> list[ScannedControl]:
    return [_control_from_payload(item) for item in payload]


def build_contract_draft(
    controls: Sequence[ScannedControl],
    *,
    source: str,
    contract_id: str | None = None,
    locale_language: str = "en",
    locale_country: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    used_keys: set[str] = set()

    for index, control in enumerate(controls, start=1):
        field_key = _unique_field_key(control, index, used_keys)
        fields[field_key] = infer_field(control.to_candidate())

    if not fields:
        raise ScannerError("No supported form controls were found")

    resolved_contract_id = _contract_id(contract_id or _source_name(source))
    locale = {"language": locale_language}
    if locale_country:
        locale["country"] = locale_country.upper()

    draft = {
        "schemaVersion": "1.0",
        "id": resolved_contract_id,
        "source": {
            "type": "url",
            "value": source,
        },
        "locale": locale,
        "fields": fields,
        "scenarios": draft_scenarios(
            fields,
            positive_id="valid_form",
            positive_description="All scanned form fields contain valid values.",
        ),
        "generation": {
            "deterministic": True,
            "defaultSeed": f"{resolved_contract_id}-scan",
        },
        "validation": {
            "status": "needs_review",
        },
    }
    result = validate_contract_data(draft)
    if not result.is_valid:
        raise ScannerError(f"Generated contract draft is invalid: {_validation_result_summary(result)}")
    return draft


def _control_from_payload(item: Mapping[str, Any]) -> ScannedControl:
    options = [
        ScannedOption(
            label=_string(option.get("label")),
            value=_string(option.get("value")),
            disabled=bool(option.get("disabled", False)),
            selected=bool(option.get("selected", False)),
        )
        for option in item.get("options", [])
        if isinstance(option, Mapping)
    ]

    validation = {
        str(key): _string(value)
        for key, value in dict(item.get("validationAttributes", {})).items()
        if value is not None and _string(value) != ""
    }
    aria = {
        str(key): value
        for key, value in dict(item.get("aria", {})).items()
        if value is not None and value != ""
    }

    return ScannedControl(
        tag=_string(item.get("tag")),
        input_type=_string(item.get("inputType") or item.get("type") or "text").lower(),
        selector=_string(item.get("selector")),
        id=_string(item.get("id")),
        name=_string(item.get("name")),
        label=_string(item.get("label")),
        placeholder=_string(item.get("placeholder")),
        autocomplete=_string(item.get("autocomplete")),
        required=bool(item.get("required", False)),
        aria=aria,
        validation_attributes=validation,
        options=options,
    )


def _constraints_from_validation(input_type: str, attrs: Mapping[str, str]) -> dict[str, Any]:
    constraints: dict[str, Any] = {}

    if "minlength" in attrs:
        constraints["minLength"] = _parse_int(attrs["minlength"])
    if "maxlength" in attrs:
        constraints["maxLength"] = _parse_int(attrs["maxlength"])
    if "pattern" in attrs:
        constraints["pattern"] = attrs["pattern"]
    if "step" in attrs:
        step = _parse_number(attrs["step"])
        constraints["step"] = step if step is not None else attrs["step"]
    if attrs.get("multiple") == "true":
        constraints["multiple"] = True

    minimum = _parse_number(attrs.get("min", ""))
    maximum = _parse_number(attrs.get("max", ""))
    if minimum is not None:
        constraints["minimum"] = minimum
    elif attrs.get("min"):
        constraints["min"] = attrs["min"]
    if maximum is not None:
        constraints["maximum"] = maximum
    elif attrs.get("max"):
        constraints["max"] = attrs["max"]

    if input_type == "email":
        constraints.setdefault("format", "email")
    elif input_type == "url":
        constraints.setdefault("format", "uri")

    return {key: value for key, value in constraints.items() if value is not None}


def _option_values(options: Sequence[ScannedOption]) -> list[str]:
    values: list[str] = []
    for option in options:
        value = option.choice_value.strip()
        if value and not option.disabled:
            values.append(value)
    return values


def _unique_field_key(control: ScannedControl, index: int, used_keys: set[str]) -> str:
    raw_key = control.name or control.id or control.label or control.placeholder or f"field{index}"
    base = _field_key_base(raw_key) or f"field{index}"
    key = base
    suffix = 2
    while key in used_keys:
        key = f"{base}{suffix}"
        suffix += 1
    used_keys.add(key)
    return key


def _field_key_base(value: str) -> str:
    stripped = value.strip()
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", stripped):
        return stripped

    tokens = re.findall(r"[A-Za-z0-9]+", stripped)
    if not tokens:
        return ""

    first, *rest = tokens
    key = first.lower() + "".join(token[:1].upper() + token[1:] for token in rest)
    if key[0].isdigit():
        key = f"field{key}"
    return key


def _contract_id(value: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", value)
    return "-".join(tokens).lower() or "scanned-form"


def _source_to_url(source: str | Path) -> str:
    if isinstance(source, Path):
        return source.expanduser().resolve().as_uri()

    source_value = source.strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", source_value):
        return source_value

    path = Path(source_value).expanduser()
    if path.exists():
        return path.resolve().as_uri()
    return source_value


def _source_name(source: str) -> str:
    path = Path(source)
    if path.name:
        return path.stem
    return source


def _validation_result_summary(result: Any) -> str:
    errors = [
        f"{finding.field or '<root>'}: {finding.message}"
        for finding in result.findings
        if finding.severity == "error"
    ]
    if errors:
        return "; ".join(errors)
    return f"validation status is {result.status}"


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


def _string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


_FORM_CONTROL_SCRIPT = """
() => {
  const CONTROL_SELECTOR = [
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"])',
    'textarea',
    'select'
  ].join(',');

  const compactText = (value) => (value || '').replace(/\\s+/g, ' ').trim();
  const attrValue = (value) => String(value || '').replace(/\\\\/g, '\\\\\\\\').replace(/"/g, '\\\\"');
  const labelText = (node) => compactText(node ? (node.innerText || node.textContent) : '');

  const labelsFor = (element) => {
    const labels = [];
    if (element.labels) {
      for (const label of Array.from(element.labels)) {
        const text = labelText(label);
        if (text) labels.push(text);
      }
    }
    return labels;
  };

  const ariaLabelledByText = (element) => {
    const ids = compactText(element.getAttribute('aria-labelledby')).split(/\\s+/).filter(Boolean);
    return ids.map((id) => labelText(document.getElementById(id))).filter(Boolean).join(' ');
  };

  const ariaAttributesFor = (element, labelledByText) => {
    const attrs = {};
    for (const attr of Array.from(element.attributes)) {
      if (attr.name.startsWith('aria-')) {
        const key = attr.name
          .slice('aria-'.length)
          .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
        attrs[key] = attr.value;
      }
    }
    if (labelledByText) attrs.labelledbyText = labelledByText;
    return attrs;
  };

  const selectorFor = (element) => {
    const id = element.id;
    if (id) {
      const idSelector = `#${CSS.escape(id)}`;
      if (document.querySelectorAll(idSelector).length === 1) return idSelector;
    }

    const tag = element.tagName.toLowerCase();
    const name = element.getAttribute('name');
    if (name) {
      const nameSelector = `${tag}[name="${attrValue(name)}"]`;
      if (document.querySelectorAll(nameSelector).length === 1) return nameSelector;

      const type = element.getAttribute('type');
      if (type) {
        const typedNameSelector = `${tag}[type="${attrValue(type)}"][name="${attrValue(name)}"]`;
        if (document.querySelectorAll(typedNameSelector).length === 1) return typedNameSelector;
      }
    }

    const path = [];
    let current = element;
    while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.documentElement) {
      const currentTag = current.tagName.toLowerCase();
      let part = currentTag;
      if (current.id) {
        part = `#${CSS.escape(current.id)}`;
        path.unshift(part);
        break;
      }
      const parent = current.parentElement;
      if (parent) {
        const sameTagSiblings = Array.from(parent.children).filter((child) => child.tagName === current.tagName);
        if (sameTagSiblings.length > 1) {
          part = `${currentTag}:nth-of-type(${sameTagSiblings.indexOf(current) + 1})`;
        }
      }
      path.unshift(part);
      const selector = path.join(' > ');
      if (document.querySelectorAll(selector).length === 1) return selector;
      current = parent;
    }
    return path.join(' > ') || tag;
  };

  const validationAttributesFor = (element) => {
    const attrs = {};
    for (const name of ['minlength', 'maxlength', 'min', 'max', 'pattern', 'step']) {
      if (element.hasAttribute(name)) attrs[name] = element.getAttribute(name);
    }
    if (element.hasAttribute('multiple')) attrs.multiple = 'true';
    return attrs;
  };

  const optionPayload = (element) => {
    if (element.tagName.toLowerCase() !== 'select') return [];
    return Array.from(element.options).map((option) => ({
      label: labelText(option),
      value: option.value,
      disabled: option.disabled,
      selected: option.selected
    }));
  };

  return Array.from(document.querySelectorAll(CONTROL_SELECTOR))
    .filter((element) => !element.disabled)
    .map((element) => {
      const tag = element.tagName.toLowerCase();
      const inputType = tag === 'input' ? compactText(element.getAttribute('type') || 'text').toLowerCase() : tag;
      const ariaLabel = compactText(element.getAttribute('aria-label'));
      const labelledByText = ariaLabelledByText(element);
      const labels = labelsFor(element);
      const label = labels[0] || ariaLabel || labelledByText;

      return {
        tag,
        inputType,
        selector: selectorFor(element),
        id: element.id || '',
        name: element.getAttribute('name') || '',
        label,
        placeholder: element.getAttribute('placeholder') || '',
        autocomplete: element.getAttribute('autocomplete') || '',
        required: Boolean(element.required || element.getAttribute('aria-required') === 'true'),
        aria: ariaAttributesFor(element, labelledByText),
        validationAttributes: validationAttributesFor(element),
        options: optionPayload(element)
      };
    });
}
"""
