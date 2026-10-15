from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Term:
    name: str
    a: float
    b: float
    c: float

    def __post_init__(self):
        self.name = self.name.strip()
        self.a, self.b, self.c = map(float, (self.a, self.b, self.c))
        if not self.name or not self.a <= self.b <= self.c or self.a == self.c:
            raise ValueError("Терм має назву та параметри a ≤ b ≤ c з ненульовою шириною.")

    def membership(self, value: float) -> float:
        x = float(value)
        if x < self.a or x > self.c:
            return 0.0
        if x == self.b:
            return 1.0
        if x < self.b:
            return (x - self.a) / (self.b - self.a)
        return (self.c - x) / (self.c - self.b)

    def to_dict(self):
        return vars(self).copy()

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class FuzzyVariable:
    name: str
    minimum: float
    maximum: float
    unit: str = ""
    terms: OrderedDict[str, Term] = field(default_factory=OrderedDict)

    def __post_init__(self):
        self.name, self.unit = self.name.strip(), self.unit.strip()
        self.minimum, self.maximum = float(self.minimum), float(self.maximum)
        if not self.name or self.minimum >= self.maximum:
            raise ValueError("Змінна має назву, а її мінімум повинен бути меншим за максимум.")

    def check_term(self, term: Term):
        if term.a < self.minimum or term.c > self.maximum:
            raise ValueError(f"Терм має бути в діапазоні [{self.minimum:g}; {self.maximum:g}].")

    def add_term(self, term: Term):
        self.check_term(term)
        if term.name in self.terms:
            raise ValueError(f"Терм «{term.name}» уже існує.")
        self.terms[term.name] = term

    def replace_term(self, old_name: str, term: Term):
        self.check_term(term)
        if old_name not in self.terms:
            raise ValueError("Терм не знайдено.")
        if term.name != old_name and term.name in self.terms:
            raise ValueError(f"Терм «{term.name}» уже існує.")
        self.terms = OrderedDict(
            (term.name, term) if name == old_name else (name, current)
            for name, current in self.terms.items()
        )

    def memberships(self, value: float):
        return {name: term.membership(value) for name, term in self.terms.items()}

    def to_dict(self):
        return {
            "name": self.name,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "unit": self.unit,
            "terms": [term.to_dict() for term in self.terms.values()],
        }

    @classmethod
    def from_dict(cls, data):
        variable = cls(data["name"], data["minimum"], data["maximum"], data.get("unit", ""))
        for term in data.get("terms", []):
            variable.add_term(Term.from_dict(term))
        return variable


@dataclass
class FuzzyRule:
    conditions: OrderedDict[str, str]
    output_term: str

    def __post_init__(self):
        self.conditions = OrderedDict((str(k).strip(), str(v).strip()) for k, v in self.conditions.items() if k and v)
        self.output_term = self.output_term.strip()
        if not self.conditions or not self.output_term:
            raise ValueError("Правило повинно містити умову та вихідний терм.")

    def to_dict(self):
        return {"conditions": dict(self.conditions), "output_term": self.output_term}

    @classmethod
    def from_dict(cls, data):
        return cls(OrderedDict(data["conditions"]), data["output_term"])


class FuzzyDatabase:
    FORMAT = "dynamic-fuzzy-kb-v1"

    def __init__(self, output: FuzzyVariable):
        self.inputs: OrderedDict[str, FuzzyVariable] = OrderedDict()
        self.output = output
        self.rules: list[FuzzyRule] = []

    def add_input(self, variable: FuzzyVariable):
        if variable.name in self.inputs or variable.name == self.output.name:
            raise ValueError(f"Змінна «{variable.name}» уже існує.")
        self.inputs[variable.name] = variable

    def replace_input(self, old_name: str, replacement: FuzzyVariable):
        old = self.inputs[old_name]
        for term in old.terms.values():
            replacement.add_term(term)
        if replacement.name != old_name and replacement.name in self.inputs:
            raise ValueError(f"Змінна «{replacement.name}» уже існує.")
        self.inputs = OrderedDict(
            (replacement.name, replacement) if name == old_name else (name, variable)
            for name, variable in self.inputs.items()
        )
        if replacement.name != old_name:
            for rule in self.rules:
                rule.conditions = OrderedDict(
                    (replacement.name if name == old_name else name, term)
                    for name, term in rule.conditions.items()
                )

    def remove_input(self, name: str):
        del self.inputs[name]
        for rule in self.rules:
            rule.conditions.pop(name, None)
        self.rules = [rule for rule in self.rules if rule.conditions]

    def validate_rule(self, rule: FuzzyRule):
        for variable_name, term_name in rule.conditions.items():
            if variable_name not in self.inputs or term_name not in self.inputs[variable_name].terms:
                raise ValueError(f"Некоректна умова: {variable_name} = {term_name}.")
        if rule.output_term not in self.output.terms:
            raise ValueError(f"Невідомий вихідний терм: {rule.output_term}.")

    def add_rule(self, rule: FuzzyRule):
        self.validate_rule(rule)
        if any(r.conditions == rule.conditions and r.output_term == rule.output_term for r in self.rules):
            raise ValueError("Таке правило вже існує.")
        self.rules.append(rule)

    def update_term_references(self, variable_name: str, old: str, new: str | None):
        kept = []
        for rule in self.rules:
            if variable_name == self.output.name:
                used = rule.output_term == old
                if used and new:
                    rule.output_term = new
            else:
                used = rule.conditions.get(variable_name) == old
                if used and new:
                    rule.conditions[variable_name] = new
            if not used or new:
                kept.append(rule)
        self.rules = kept

    def validate(self):
        errors = []
        if not self.inputs:
            errors.append("Немає вхідних змінних.")
        for variable in [*self.inputs.values(), self.output]:
            if not variable.terms:
                errors.append(f"Змінна «{variable.name}» не має термів.")
        for index, rule in enumerate(self.rules, 1):
            try:
                self.validate_rule(rule)
            except ValueError as error:
                errors.append(f"Правило {index}: {error}")
        return errors

    def infer(self, values: dict[str, float], steps: int = 400):
        missing = [name for name in self.inputs if name not in values]
        if missing:
            raise ValueError("Не задано значення: " + ", ".join(missing))
        if not self.rules or not self.output.terms:
            raise ValueError("Для висновку потрібні правила та вихідні терми.")
        fuzzified = {}
        for name, variable in self.inputs.items():
            value = float(values[name])
            if not variable.minimum <= value <= variable.maximum:
                raise ValueError(f"«{name}» має бути в діапазоні [{variable.minimum:g}; {variable.maximum:g}].")
            fuzzified[name] = variable.memberships(value)

        aggregated = {name: 0.0 for name in self.output.terms}
        activations = []
        for rule in self.rules:
            activation = min(fuzzified[name][term] for name, term in rule.conditions.items())
            activations.append(activation)
            aggregated[rule.output_term] = max(aggregated[rule.output_term], activation)

        numerator = denominator = 0.0
        for index in range(steps + 1):
            x = self.output.minimum + (self.output.maximum - self.output.minimum) * index / steps
            degree = max(min(aggregated[name], term.membership(x)) for name, term in self.output.terms.items())
            numerator += x * degree
            denominator += degree
        if denominator == 0:
            raise ValueError("Жодне правило не активувалося.")
        return numerator / denominator, aggregated, activations

    def to_dict(self):
        return {
            "format": self.FORMAT,
            "input_variables": [variable.to_dict() for variable in self.inputs.values()],
            "output_variable": self.output.to_dict(),
            "rules": [rule.to_dict() for rule in self.rules],
        }

    @classmethod
    def from_dict(cls, data):
        if data.get("format") != cls.FORMAT:
            raise ValueError("Непідтримуваний формат бази знань.")
        base = cls(FuzzyVariable.from_dict(data["output_variable"]))
        for variable in data.get("input_variables", []):
            base.add_input(FuzzyVariable.from_dict(variable))
        for rule in data.get("rules", []):
            base.add_rule(FuzzyRule.from_dict(rule))
        errors = base.validate()
        if errors:
            raise ValueError("\n".join(errors))
        return base

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def variable(name, minimum, maximum, unit, terms):
    result = FuzzyVariable(name, minimum, maximum, unit)
    for term in terms:
        result.add_term(Term(*term))
    return result


def default_database():
    base = FuzzyDatabase(variable("Потужність кондиціонування", 0, 100, "%", [
        ("Низька", 0, 0, 50), ("Середня", 25, 50, 75), ("Висока", 50, 100, 100)
    ]))
    for item in (
        variable("Температура", 0, 40, "°C", [("Низька", 0, 0, 20), ("Комфортна", 15, 22, 29), ("Висока", 24, 40, 40)]),
        variable("Вологість", 0, 100, "%", [("Низька", 0, 0, 45), ("Нормальна", 30, 50, 70), ("Висока", 55, 100, 100)]),
        variable("Кількість людей", 0, 30, "осіб", [("Мало", 0, 0, 10), ("Середньо", 5, 15, 25), ("Багато", 18, 30, 30)]),
    ):
        base.add_input(item)
    for conditions, output in (
        ({"Температура": "Низька", "Вологість": "Низька", "Кількість людей": "Мало"}, "Низька"),
        ({"Температура": "Комфортна", "Вологість": "Нормальна", "Кількість людей": "Мало"}, "Низька"),
        ({"Температура": "Комфортна", "Вологість": "Нормальна", "Кількість людей": "Середньо"}, "Середня"),
        ({"Температура": "Висока"}, "Висока"),
        ({"Вологість": "Висока", "Кількість людей": "Багато"}, "Висока"),
        ({"Температура": "Комфортна", "Кількість людей": "Багато"}, "Висока"),
        ({"Температура": "Низька", "Кількість людей": "Багато"}, "Середня"),
        ({"Вологість": "Висока", "Кількість людей": "Середньо"}, "Середня"),
    ):
        base.add_rule(FuzzyRule(OrderedDict(conditions), output))
    return base
