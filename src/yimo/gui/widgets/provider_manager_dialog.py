from __future__ import annotations

from typing import List, Optional

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from yimo.models.config import ProviderConfig
from yimo.utils.constants import OPENAI_MODELS
from yimo.i18n.manager import I18nManager


class ProviderEditorDialog(QDialog):
    def __init__(self, provider: ProviderConfig, existing_names: set[str], i18n: I18nManager, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(self.i18n.t("pm.edit_title"))
        self.resize(520, 320)

        self._provider = provider.model_copy(deep=True)
        self._existing_names = existing_names

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(self._provider.name)
        self.base_url_edit = QLineEdit(self._provider.base_url)
        self.api_key_edit = QLineEdit(self._provider.api_key)
        self.api_key_edit.setEchoMode(QLineEdit.Password)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(OPENAI_MODELS)
        if self._provider.model and self._provider.model not in OPENAI_MODELS:
            self.model_combo.addItem(self._provider.model)
        self.model_combo.setCurrentText(self._provider.model)

        self.rpm_spin = QSpinBox()
        self.rpm_spin.setRange(-1, 10000)
        self.rpm_spin.setSuffix(" req/min")
        self.rpm_spin.setValue(int(self._provider.rpm_limit))
        self.rpm_spin.setToolTip(self.i18n.t("pm.rpm.tooltip"))

        form.addRow(self.i18n.t("pm.form.name"), self.name_edit)
        form.addRow(self.i18n.t("pm.form.base_url"), self.base_url_edit)
        form.addRow(self.i18n.t("pm.form.api_key"), self.api_key_edit)
        form.addRow(self.i18n.t("pm.form.model"), self.model_combo)
        form.addRow(self.i18n.t("pm.form.rpm"), self.rpm_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setProperty("variant", "primary")
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn is not None:
            cancel_btn.setProperty("variant", "ghost")
        layout.addWidget(buttons)

    def _validate(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError(self.i18n.t("pm.err.name_required"))
        if name in self._existing_names:
            raise ValueError(self.i18n.t("pm.err.duplicate", name=name))

        base_url = self.base_url_edit.text().strip()
        if not base_url:
            raise ValueError(self.i18n.t("pm.err.base_url_required"))

        model = self.model_combo.currentText().strip()
        if not model:
            raise ValueError(self.i18n.t("pm.err.model_required"))

    def accept(self):
        try:
            self._validate()
        except Exception as e:
            QMessageBox.warning(self, self.i18n.t("settings.validation.title"), str(e))
            return

        self._provider.name = self.name_edit.text().strip()
        self._provider.base_url = self.base_url_edit.text().strip()
        self._provider.api_key = self.api_key_edit.text()
        self._provider.model = self.model_combo.currentText().strip()
        self._provider.rpm_limit = int(self.rpm_spin.value())
        super().accept()

    def get_provider(self) -> ProviderConfig:
        return self._provider.model_copy(deep=True)


class ProviderManagerDialog(QDialog):
    def __init__(self, providers: List[ProviderConfig], i18n: I18nManager, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(self.i18n.t("pm.manage_title"))
        self.resize(780, 420)

        self._providers: List[ProviderConfig] = [p.model_copy(deep=True) for p in providers]
        if not self._providers:
            self._providers = [ProviderConfig(name="default")]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        help_label = QLabel(self.i18n.t("pm.help"))
        help_label.setProperty("role", "muted")
        layout.addWidget(help_label)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                self.i18n.t("pm.table.name"),
                self.i18n.t("pm.table.base_url"),
                self.i18n.t("pm.table.model"),
                self.i18n.t("pm.table.rpm"),
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_add = QPushButton(self.i18n.t("pm.btn.add"))
        self.btn_edit = QPushButton(self.i18n.t("pm.btn.edit"))
        self.btn_remove = QPushButton(self.i18n.t("pm.btn.remove"))
        self.btn_add.setProperty("variant", "primary")
        self.btn_edit.setProperty("variant", "secondary")
        self.btn_remove.setProperty("variant", "danger")
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch(1)
        layout.addWidget(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setProperty("variant", "primary")
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn is not None:
            cancel_btn.setProperty("variant", "ghost")
        layout.addWidget(buttons)

        self.btn_add.clicked.connect(self.add_provider)
        self.btn_edit.clicked.connect(self.edit_provider)
        self.btn_remove.clicked.connect(self.remove_provider)

        self._refresh_table(select_row=0)

    def _refresh_table(self, select_row: Optional[int] = None) -> None:
        self.table.setRowCount(len(self._providers))
        for row, provider in enumerate(self._providers):
            self.table.setItem(row, 0, QTableWidgetItem(provider.name))
            self.table.setItem(row, 1, QTableWidgetItem(provider.base_url))
            self.table.setItem(row, 2, QTableWidgetItem(provider.model))
            self.table.setItem(row, 3, QTableWidgetItem(str(int(provider.rpm_limit))))

        if select_row is not None and self._providers:
            row = max(0, min(select_row, len(self._providers) - 1))
            self.table.selectRow(row)

    def _selected_index(self) -> Optional[int]:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return None
        return selection[0].row()

    def _unique_name(self, base: str = "provider") -> str:
        existing = {p.name for p in self._providers if p.name}
        if base not in existing:
            return base
        i = 2
        while f"{base}{i}" in existing:
            i += 1
        return f"{base}{i}"

    def add_provider(self) -> None:
        new_provider = ProviderConfig(name=self._unique_name())
        existing_names = {p.name for p in self._providers if p.name}
        dialog = ProviderEditorDialog(
            new_provider,
            existing_names=existing_names - {new_provider.name},
            i18n=self.i18n,
            parent=self,
        )
        if dialog.exec():
            self._providers.append(dialog.get_provider())
            self._refresh_table(select_row=len(self._providers) - 1)

    def edit_provider(self) -> None:
        idx = self._selected_index()
        if idx is None:
            QMessageBox.information(self, self.i18n.t("info.title"), self.i18n.t("pm.select_to_edit"))
            return

        provider = self._providers[idx]
        existing_names = {p.name for p in self._providers if p.name} - {provider.name}
        dialog = ProviderEditorDialog(provider, existing_names=existing_names, i18n=self.i18n, parent=self)
        if dialog.exec():
            self._providers[idx] = dialog.get_provider()
            self._refresh_table(select_row=idx)

    def remove_provider(self) -> None:
        idx = self._selected_index()
        if idx is None:
            QMessageBox.information(self, self.i18n.t("info.title"), self.i18n.t("pm.select_to_remove"))
            return
        if len(self._providers) <= 1:
            QMessageBox.warning(self, self.i18n.t("settings.validation.title"), self.i18n.t("pm.err.need_one"))
            return

        provider = self._providers[idx]
        reply = QMessageBox.question(
            self,
            self.i18n.t("pm.remove.title"),
            self.i18n.t("pm.remove.confirm", name=provider.name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._providers.pop(idx)
        self._refresh_table(select_row=min(idx, len(self._providers) - 1))

    def _validate(self) -> None:
        if not self._providers:
            raise ValueError(self.i18n.t("pm.err.need_one"))
        names: set[str] = set()
        for provider in self._providers:
            if not provider.name:
                raise ValueError(self.i18n.t("pm.err.name_required"))
            if provider.name in names:
                raise ValueError(self.i18n.t("pm.err.duplicate", name=provider.name))
            if not provider.base_url:
                raise ValueError(self.i18n.t("pm.err.base_url_required_for", name=provider.name))
            if not provider.model:
                raise ValueError(self.i18n.t("pm.err.model_required_for", name=provider.name))
            names.add(provider.name)

    def accept(self):
        try:
            self._validate()
        except Exception as e:
            QMessageBox.warning(self, self.i18n.t("settings.validation.title"), str(e))
            return
        super().accept()

    def get_providers(self) -> List[ProviderConfig]:
        return [p.model_copy(deep=True) for p in self._providers]
