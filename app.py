import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from dialogs import RuleDialog, TermDialog, VariableDialog
from model import FuzzyDatabase, default_database


class FuzzyEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Редактор нечіткої бази знань — варіант 9")
        self.geometry("1200x720")
        self.minsize(980, 600)
        self.database = default_database()
        self.current_file = None
        self.input_entries = {}
        self._create_menu()
        self._create_widgets()
        self.refresh()

    def _create_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        for label, command in (
            ("Нова база", self.new_database),
            ("Відкрити…", self.open_database),
            ("Зберегти", self.save_database),
            ("Зберегти як…", lambda: self.save_database(True)),
        ):
            file_menu.add_command(label=label, command=command)
        menu.add_cascade(label="Файл", menu=file_menu)
        menu.add_command(label="Перевірити базу", command=self.validate_database)
        self.config(menu=menu)

    @staticmethod
    def buttons(parent, items):
        frame = ttk.Frame(parent)
        for label, command in items:
            ttk.Button(frame, text=label, command=command).pack(side="left", padx=(0, 5))
        return frame

    def _create_widgets(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=3)
        root.rowconfigure(0, weight=1)

        variables = ttk.LabelFrame(root, text="Змінні", padding=7)
        variables.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        variables.rowconfigure(0, weight=1)
        variables.columnconfigure(0, weight=1)
        self.variable_tree = ttk.Treeview(variables, show="tree", selectmode="browse")
        self.variable_tree.grid(row=0, column=0, sticky="nsew")
        self.variable_tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_terms())
        self.buttons(variables, [
            ("Додати", self.add_variable), ("Змінити", self.edit_variable), ("Видалити", self.delete_variable)
        ]).grid(row=1, column=0, sticky="w", pady=(7, 0))

        terms = ttk.LabelFrame(root, text="Терми", padding=7)
        terms.grid(row=0, column=1, sticky="nsew", padx=5)
        terms.rowconfigure(0, weight=1)
        terms.columnconfigure(0, weight=1)
        self.term_tree = ttk.Treeview(terms, columns=("a", "b", "c"), show="tree headings")
        self.term_tree.heading("#0", text="Назва")
        for name in ("a", "b", "c"):
            self.term_tree.heading(name, text=name)
            self.term_tree.column(name, width=45, anchor="center")
        self.term_tree.grid(row=0, column=0, sticky="nsew")
        self.buttons(terms, [
            ("Додати", self.add_term), ("Змінити", self.edit_term), ("Видалити", self.delete_term)
        ]).grid(row=1, column=0, sticky="w", pady=(7, 0))

        right = ttk.Frame(root)
        right.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=2)

        rules = ttk.LabelFrame(right, text="Нечіткі правила", padding=7)
        rules.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        rules.rowconfigure(0, weight=1)
        rules.columnconfigure(0, weight=1)
        self.rule_tree = ttk.Treeview(rules, show="headings", selectmode="browse")
        self.rule_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(rules, orient="horizontal", command=self.rule_tree.xview)
        scroll.grid(row=1, column=0, sticky="ew")
        self.rule_tree.configure(xscrollcommand=scroll.set)
        self.buttons(rules, [
            ("Додати правило", self.add_rule), ("Змінити", self.edit_rule), ("Видалити", self.delete_rule)
        ]).grid(row=2, column=0, sticky="w", pady=(7, 0))

        self.inference = ttk.LabelFrame(right, text="Нечіткий висновок", padding=7)
        self.inference.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=4).pack(side="bottom", fill="x")

    def selected_variable(self):
        selection = self.variable_tree.selection()
        if not selection:
            return None
        item = selection[0]
        if item == "output":
            return self.database.output, True
        if item.startswith("input:"):
            return self.database.inputs[item[6:]], False
        return None

    def refresh(self):
        self.variable_tree.delete(*self.variable_tree.get_children())
        parent = self.variable_tree.insert("", "end", iid="inputs", text="Вхідні змінні", open=True)
        for name, variable in self.database.inputs.items():
            text = f"{name} [{variable.minimum:g}…{variable.maximum:g} {variable.unit}]"
            self.variable_tree.insert(parent, "end", iid="input:" + name, text=text)
        self.variable_tree.insert("", "end", iid="output", text="Вихід: " + self.database.output.name)
        if self.database.inputs:
            self.variable_tree.selection_set("input:" + next(iter(self.database.inputs)))
        self.refresh_terms()
        self.refresh_rules()
        self.refresh_inference()
        self.status.set(f"Вхідних змінних: {len(self.database.inputs)} | Правил: {len(self.database.rules)}")

    def refresh_terms(self):
        self.term_tree.delete(*self.term_tree.get_children())
        selected = self.selected_variable()
        if selected:
            for term in selected[0].terms.values():
                self.term_tree.insert("", "end", iid=term.name, text=term.name, values=(f"{term.a:g}", f"{term.b:g}", f"{term.c:g}"))

    def refresh_rules(self):
        columns = [*self.database.inputs, "ТО"]
        self.rule_tree.configure(columns=columns)
        for name in columns:
            self.rule_tree.heading(name, text=name)
            self.rule_tree.column(name, width=115, anchor="center")
        self.rule_tree.delete(*self.rule_tree.get_children())
        for index, rule in enumerate(self.database.rules):
            values = [rule.conditions.get(name, "—") for name in self.database.inputs]
            self.rule_tree.insert("", "end", iid=str(index), values=[*values, rule.output_term])

    def refresh_inference(self):
        for child in self.inference.winfo_children():
            child.destroy()
        self.input_entries = {}
        for row, (name, variable) in enumerate(self.database.inputs.items()):
            label = f"{name}, {variable.unit}:" if variable.unit else name + ":"
            ttk.Label(self.inference, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            entry = ttk.Entry(self.inference, width=14)
            entry.insert(0, f"{(variable.minimum + variable.maximum) / 2:g}")
            entry.grid(row=row, column=1, sticky="w", pady=2)
            self.input_entries[name] = entry
        row = len(self.input_entries)
        ttk.Button(self.inference, text="Виконати висновок", command=self.run_inference).grid(row=row, column=0, columnspan=2, sticky="w", pady=6)
        self.result = ttk.Label(self.inference, text="Результат: —", font=("Segoe UI", 11, "bold"))
        self.result.grid(row=row + 1, column=0, columnspan=3, sticky="w")
        self.details = ttk.Label(self.inference, justify="left")
        self.details.grid(row=row + 2, column=0, columnspan=3, sticky="w")

    def add_variable(self):
        dialog = VariableDialog(self)
        if dialog.result:
            self._attempt(lambda: self.database.add_input(dialog.result))

    def edit_variable(self):
        selected = self.selected_variable()
        if not selected or selected[1]:
            messagebox.showinfo("Змінна", "Виберіть вхідну змінну.", parent=self)
            return
        old = selected[0]
        dialog = VariableDialog(self, old)
        if dialog.result:
            self._attempt(lambda: self.database.replace_input(old.name, dialog.result))

    def delete_variable(self):
        selected = self.selected_variable()
        if selected and not selected[1] and messagebox.askyesno("Видалення", f"Видалити «{selected[0].name}»?", parent=self):
            self.database.remove_input(selected[0].name)
            self.refresh()

    def add_term(self):
        selected = self.selected_variable()
        if not selected:
            return
        dialog = TermDialog(self, selected[0])
        if dialog.result:
            self._attempt(lambda: selected[0].add_term(dialog.result))

    def edit_term(self):
        selected, term_selection = self.selected_variable(), self.term_tree.selection()
        if not selected or not term_selection:
            return
        variable, old_name = selected[0], term_selection[0]
        dialog = TermDialog(self, variable, variable.terms[old_name])
        if dialog.result:
            def change():
                variable.replace_term(old_name, dialog.result)
                self.database.update_term_references(variable.name, old_name, dialog.result.name)
            self._attempt(change)

    def delete_term(self):
        selected, term_selection = self.selected_variable(), self.term_tree.selection()
        if not selected or not term_selection:
            return
        variable, term_name = selected[0], term_selection[0]
        if messagebox.askyesno("Видалення", f"Видалити терм «{term_name}» і пов'язані правила?", parent=self):
            self.database.update_term_references(variable.name, term_name, None)
            del variable.terms[term_name]
            self.refresh()

    def add_rule(self):
        dialog = RuleDialog(self, self.database)
        if dialog.result:
            self._attempt(lambda: self.database.add_rule(dialog.result))

    def edit_rule(self):
        selection = self.rule_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        dialog = RuleDialog(self, self.database, self.database.rules[index])
        if dialog.result:
            self.database.rules[index] = dialog.result
            self.refresh_rules()

    def delete_rule(self):
        selection = self.rule_tree.selection()
        if selection:
            del self.database.rules[int(selection[0])]
            self.refresh()

    def run_inference(self):
        try:
            values = {name: float(entry.get().replace(",", ".")) for name, entry in self.input_entries.items()}
            value, degrees, activations = self.database.infer(values)
            self.result.configure(text=f"Результат: {value:.2f} {self.database.output.unit}")
            summary = ", ".join(f"{name}: {degree:.3f}" for name, degree in degrees.items())
            self.details.configure(text=f"Ступені: {summary}\nАктивовано правил: {sum(x > 0 for x in activations)}")
        except ValueError as error:
            messagebox.showerror("Помилка висновку", str(error), parent=self)

    def validate_database(self):
        errors = self.database.validate()
        messagebox.showerror("Перевірка", "\n".join(errors), parent=self) if errors else messagebox.showinfo("Перевірка", "Формальних помилок не виявлено.", parent=self)

    def new_database(self):
        self.database, self.current_file = default_database(), None
        self.refresh()

    def open_database(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.database, self.current_file = FuzzyDatabase.load(path), Path(path)
                self.refresh()
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                messagebox.showerror("Помилка відкриття", str(error), parent=self)

    def save_database(self, save_as=False):
        if save_as or not self.current_file:
            path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=[("JSON", "*.json")])
            if not path:
                return
            self.current_file = Path(path)
        try:
            self.database.save(self.current_file)
            self.status.set("Збережено: " + str(self.current_file))
        except OSError as error:
            messagebox.showerror("Помилка збереження", str(error), parent=self)

    def _attempt(self, action):
        try:
            action()
            self.refresh()
        except (KeyError, ValueError) as error:
            messagebox.showerror("Помилка", str(error), parent=self)
