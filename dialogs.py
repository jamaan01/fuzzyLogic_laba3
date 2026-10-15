from collections import OrderedDict
from tkinter import messagebox, simpledialog, ttk

from model import FuzzyRule, FuzzyVariable, Term


ANY = "— не враховувати —"


class FieldsDialog(simpledialog.Dialog):
    fields = ()

    def body(self, master):
        self.entries = {}
        for row, (key, label, value) in enumerate(self.fields):
            ttk.Label(master, text=label + ":").grid(row=row, column=0, sticky="w", padx=6, pady=5)
            entry = ttk.Entry(master, width=30)
            entry.insert(0, value)
            entry.grid(row=row, column=1, padx=6, pady=5)
            self.entries[key] = entry
        return next(iter(self.entries.values()))

    def fail(self, error):
        messagebox.showerror("Некоректні дані", str(error), parent=self)
        return False


class VariableDialog(FieldsDialog):
    def __init__(self, parent, variable=None):
        self.source = variable
        self.fields = (
            ("name", "Назва", variable.name if variable else ""),
            ("minimum", "Мінімум", f"{variable.minimum:g}" if variable else "0"),
            ("maximum", "Максимум", f"{variable.maximum:g}" if variable else "100"),
            ("unit", "Одиниця", variable.unit if variable else ""),
        )
        self.result = None
        super().__init__(parent, "Параметри змінної")

    def validate(self):
        try:
            result = FuzzyVariable(
                self.entries["name"].get(),
                self.entries["minimum"].get(),
                self.entries["maximum"].get(),
                self.entries["unit"].get(),
            )
            if self.source:
                for term in self.source.terms.values():
                    result.check_term(term)
            self.result = result
            return True
        except ValueError as error:
            return self.fail(error)


class TermDialog(FieldsDialog):
    def __init__(self, parent, variable, term=None):
        self.variable = variable
        values = term or Term("Новий терм", variable.minimum, (variable.minimum + variable.maximum) / 2, variable.maximum)
        self.fields = (
            ("name", "Назва", values.name),
            ("a", "a", f"{values.a:g}"),
            ("b", "b", f"{values.b:g}"),
            ("c", "c", f"{values.c:g}"),
        )
        self.result = None
        super().__init__(parent, "Параметри терма")

    def validate(self):
        try:
            term = Term(*(self.entries[key].get() for key in ("name", "a", "b", "c")))
            self.variable.check_term(term)
            self.result = term
            return True
        except ValueError as error:
            return self.fail(error)


class RuleDialog(simpledialog.Dialog):
    def __init__(self, parent, database, rule=None):
        self.database, self.source, self.result = database, rule, None
        super().__init__(parent, "Нечітке правило")

    def body(self, master):
        ttk.Label(master, text="ЯКЩО", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.boxes = OrderedDict()
        for row, (name, variable) in enumerate(self.database.inputs.items(), 1):
            ttk.Label(master, text=name + ":").grid(row=row, column=0, sticky="w", padx=6, pady=4)
            box = ttk.Combobox(master, state="readonly", width=27, values=[ANY, *variable.terms])
            box.set(self.source.conditions.get(name, ANY) if self.source else ANY)
            box.grid(row=row, column=1, padx=6, pady=4)
            self.boxes[name] = box
        row = len(self.boxes) + 1
        ttk.Label(master, text="ТО", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=6, pady=8)
        self.output = ttk.Combobox(master, state="readonly", width=27, values=list(self.database.output.terms))
        self.output.grid(row=row, column=1, padx=6, pady=8)
        self.output.set(self.source.output_term if self.source else next(iter(self.database.output.terms), ""))
        return next(iter(self.boxes.values()), self.output)

    def validate(self):
        try:
            conditions = OrderedDict((name, box.get()) for name, box in self.boxes.items() if box.get() != ANY)
            self.result = FuzzyRule(conditions, self.output.get())
            self.database.validate_rule(self.result)
            return True
        except ValueError as error:
            messagebox.showerror("Некоректне правило", str(error), parent=self)
            return False
