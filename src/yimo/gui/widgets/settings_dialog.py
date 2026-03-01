from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from yimo.models.config import AppConfig, ProviderConfig
from yimo.gui.widgets.provider_manager_dialog import ProviderManagerDialog
from yimo.utils.constants import DEFAULT_SYSTEM_PROMPT


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.config = config
        self.resize(650, 720)

        self._providers_working = [p.model_copy(deep=True) for p in (config.providers or [])]
        if not self._providers_working:
            self._providers_working = [ProviderConfig(name="default")]

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Provider row: choose active + open manager dialog
        provider_row = QWidget()
        provider_row_layout = QHBoxLayout(provider_row)
        provider_row_layout.setContentsMargins(0, 0, 0, 0)

        self.provider_combo = QComboBox()
        provider_row_layout.addWidget(self.provider_combo, 1)

        self.btn_manage_providers = QPushButton("Manage Providers...")
        self.btn_manage_providers.clicked.connect(self.open_provider_manager)
        provider_row_layout.addWidget(self.btn_manage_providers)

        self._refresh_provider_combo(preferred_active_name=config.active_provider)

        # Global fields
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 20)
        self.concurrency_spin.setValue(self.config.max_concurrency)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(self.config.max_retries)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.config.temperature)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 600)
        self.timeout_spin.setValue(self.config.request_timeout)
        self.timeout_spin.setSuffix(" s")

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlainText(self.config.system_prompt)
        self.prompt_edit.setPlaceholderText("Enter System Prompt...")

        self.btn_reset_prompt = QPushButton("Reset to Default")
        self.btn_reset_prompt.clicked.connect(self.reset_prompt)

        form_layout.addRow("Provider:", provider_row)
        form_layout.addRow("Max Concurrency:", self.concurrency_spin)
        form_layout.addRow("Max Retries:", self.retries_spin)
        form_layout.addRow("Temperature:", self.temp_spin)
        form_layout.addRow("Request Timeout:", self.timeout_spin)

        prompt_container = QWidget()
        prompt_layout = QVBoxLayout(prompt_container)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.addWidget(self.prompt_edit)
        prompt_layout.addWidget(self.btn_reset_prompt)
        form_layout.addRow("System Prompt:", prompt_container)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def reset_prompt(self):
        self.prompt_edit.setPlainText(DEFAULT_SYSTEM_PROMPT)

    def _refresh_provider_combo(self, preferred_active_name: str | None = None) -> None:
        self.provider_combo.blockSignals(True)
        try:
            self.provider_combo.clear()
            self.provider_combo.addItems([p.name for p in self._providers_working])

            if not self._providers_working:
                return

            active_name = preferred_active_name or self._providers_working[0].name
            index = next((i for i, p in enumerate(self._providers_working) if p.name == active_name), 0)
            self.provider_combo.setCurrentIndex(index)
        finally:
            self.provider_combo.blockSignals(False)

    def open_provider_manager(self):
        dialog = ProviderManagerDialog([p.model_copy(deep=True) for p in self._providers_working], self)
        if dialog.exec():
            updated = dialog.get_providers()
            if not updated:
                QMessageBox.warning(self, "Validation Error", "At least one provider is required.")
                return
            self._providers_working = updated
            self._refresh_provider_combo(preferred_active_name=self.provider_combo.currentText())

    def _validate(self) -> None:
        if not self._providers_working:
            raise ValueError("At least one provider is required.")

        names: set[str] = set()
        for provider in self._providers_working:
            if not provider.name:
                raise ValueError("Provider name is required.")
            if provider.name in names:
                raise ValueError(f"Duplicate provider name: {provider.name}")
            names.add(provider.name)

    def accept(self):
        try:
            self._validate()
        except Exception as e:
            QMessageBox.warning(self, "Validation Error", str(e))
            return
        super().accept()

    def get_new_config(self) -> AppConfig:
        active_provider_name = self.provider_combo.currentText().strip()
        if not active_provider_name and self._providers_working:
            active_provider_name = self._providers_working[0].name

        # Ensure active provider still exists.
        if not any(p.name == active_provider_name for p in self._providers_working):
            active_provider_name = self._providers_working[0].name

        return AppConfig(
            active_provider=active_provider_name,
            providers=[p.model_copy(deep=True) for p in self._providers_working],
            max_concurrency=self.concurrency_spin.value(),
            max_retries=self.retries_spin.value(),
            temperature=float(self.temp_spin.value()),
            request_timeout=int(self.timeout_spin.value()),
            system_prompt=self.prompt_edit.toPlainText(),
        )
