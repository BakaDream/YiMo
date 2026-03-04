from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from yimo.models.config import AppConfig, ProviderConfig
from yimo.gui.widgets.provider_manager_dialog import ProviderEditorDialog
from yimo.utils.constants import DEFAULT_RAW_SYSTEM_PROMPT, DEFAULT_STRUCTURED_SYSTEM_PROMPT
from yimo.i18n.manager import I18nManager


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, i18n: I18nManager, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(self.i18n.t("settings.title"))
        self.config = config
        self.resize(650, 720)

        self._providers_working = [p.model_copy(deep=True) for p in (config.providers or [])]
        if not self._providers_working:
            self._providers_working = [ProviderConfig(name="default")]

        layout = QVBoxLayout(self)

        # Provider controls (embedded in Providers tab)
        self.provider_combo = QComboBox()
        self._refresh_provider_combo(preferred_active_name=config.active_provider)

        # Translation mode
        self.translation_mode_combo = QComboBox()
        self.translation_mode_combo.addItem(self.i18n.t("settings.translation_mode.raw"), "raw_markdown")
        self.translation_mode_combo.addItem(self.i18n.t("settings.translation_mode.structured"), "structured_graph")
        current_mode = getattr(self.config, "translation_mode", "raw_markdown") or "raw_markdown"
        idx_mode = self.translation_mode_combo.findData(current_mode)
        if idx_mode >= 0:
            self.translation_mode_combo.setCurrentIndex(idx_mode)

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

        self.raw_prompt_edit = QPlainTextEdit()
        self.raw_prompt_edit.setPlainText(getattr(self.config, "raw_system_prompt", DEFAULT_RAW_SYSTEM_PROMPT))
        self.raw_prompt_edit.setPlaceholderText(self.i18n.t("settings.prompt.raw.placeholder"))
        self.raw_prompt_edit.setMinimumHeight(140)

        self.btn_reset_raw_prompt = QPushButton(self.i18n.t("settings.prompt.reset_raw"))
        self.btn_reset_raw_prompt.setProperty("variant", "ghost")
        self.btn_reset_raw_prompt.clicked.connect(self.reset_raw_prompt)

        self.structured_prompt_edit = QPlainTextEdit()
        self.structured_prompt_edit.setPlainText(getattr(self.config, "structured_system_prompt", DEFAULT_STRUCTURED_SYSTEM_PROMPT))
        self.structured_prompt_edit.setPlaceholderText(self.i18n.t("settings.prompt.structured.placeholder"))
        self.structured_prompt_edit.setMinimumHeight(140)

        self.structured_prompt_help = QLabel(self.i18n.t("settings.structured.prompt.help"))
        self.structured_prompt_help.setWordWrap(True)
        self.structured_prompt_help.setProperty("role", "muted")

        self.btn_reset_structured_prompt = QPushButton(self.i18n.t("settings.prompt.reset_structured"))
        self.btn_reset_structured_prompt.setProperty("variant", "ghost")
        self.btn_reset_structured_prompt.clicked.connect(self.reset_structured_prompt)

        # Structured translation tuning (token-based; no char-based fallback)
        self.structured_chunk_tokens_spin = QSpinBox()
        self.structured_chunk_tokens_spin.setRange(100, 100000)
        self.structured_chunk_tokens_spin.setValue(int(getattr(self.config, "structured_chunk_tokens", 2000)))

        self.structured_memory_max_tokens_spin = QSpinBox()
        self.structured_memory_max_tokens_spin.setRange(0, 100000)
        self.structured_memory_max_tokens_spin.setValue(int(getattr(self.config, "structured_memory_max_tokens", 300)))

        self.structured_max_repair_attempts_spin = QSpinBox()
        self.structured_max_repair_attempts_spin.setRange(0, 10)
        self.structured_max_repair_attempts_spin.setValue(int(getattr(self.config, "structured_max_repair_attempts", 2)))

        self.structured_group = QGroupBox(self.i18n.t("settings.translation_mode.structured"))
        structured_form = QFormLayout(self.structured_group)
        structured_form.setContentsMargins(0, 0, 0, 0)
        structured_form.addRow(self.i18n.t("settings.structured.chunk_tokens"), self.structured_chunk_tokens_spin)
        structured_form.addRow(self.i18n.t("settings.structured.memory_max_tokens"), self.structured_memory_max_tokens_spin)
        structured_form.addRow(self.i18n.t("settings.structured.max_repair_attempts"), self.structured_max_repair_attempts_spin)

        # Front Matter settings
        fm_keys = set([k.lower() for k in (getattr(self.config, "front_matter_translate_keys", None) or ["title", "tags"])])
        self.fm_cb_title = QCheckBox(self.i18n.t("settings.fm.title"))
        self.fm_cb_title.setChecked("title" in fm_keys)
        self.fm_cb_tags = QCheckBox(self.i18n.t("settings.fm.tags"))
        self.fm_cb_tags.setChecked("tags" in fm_keys)
        self.fm_cb_description = QCheckBox(self.i18n.t("settings.fm.description"))
        self.fm_cb_description.setChecked("description" in fm_keys)
        self.fm_cb_summary = QCheckBox(self.i18n.t("settings.fm.summary"))
        self.fm_cb_summary.setChecked("summary" in fm_keys)
        self.fm_cb_categories = QCheckBox(self.i18n.t("settings.fm.categories"))
        self.fm_cb_categories.setChecked("categories" in fm_keys)

        self.fm_custom_edit = QLineEdit()
        self.fm_custom_edit.setText(getattr(self.config, "front_matter_custom_keys", "") or "")
        self.fm_custom_edit.setPlaceholderText(self.i18n.t("settings.fm.custom.placeholder"))

        fm_container = QWidget()
        fm_layout = QVBoxLayout(fm_container)
        fm_layout.setContentsMargins(0, 0, 0, 0)
        fm_layout.setSpacing(6)
        fm_layout.addWidget(self.fm_cb_title)
        fm_layout.addWidget(self.fm_cb_tags)
        fm_layout.addWidget(self.fm_cb_description)
        fm_layout.addWidget(self.fm_cb_summary)
        fm_layout.addWidget(self.fm_cb_categories)
        fm_layout.addWidget(QLabel(self.i18n.t("settings.fm.custom")))
        fm_layout.addWidget(self.fm_custom_edit)
        fm_help = QLabel(self.i18n.t("settings.front_matter.help"))
        fm_help.setWordWrap(True)
        fm_help.setProperty("role", "muted")
        fm_layout.addWidget(fm_help)

        raw_prompt_container = QWidget()
        raw_prompt_layout = QVBoxLayout(raw_prompt_container)
        raw_prompt_layout.setContentsMargins(0, 0, 0, 0)
        raw_prompt_layout.addWidget(self.raw_prompt_edit)
        raw_prompt_layout.addWidget(self.btn_reset_raw_prompt)

        structured_prompt_container = QWidget()
        structured_prompt_layout = QVBoxLayout(structured_prompt_container)
        structured_prompt_layout.setContentsMargins(0, 0, 0, 0)
        structured_prompt_layout.addWidget(self.structured_prompt_edit)
        structured_prompt_layout.addWidget(self.structured_prompt_help)
        structured_prompt_layout.addWidget(self.btn_reset_structured_prompt)

        # Advanced
        self.adv_translate_link_text = QCheckBox(self.i18n.t("settings.advanced.translate_link_text"))
        self.adv_translate_link_text.setChecked(bool(getattr(self.config, "translate_link_text", True)))

        self.adv_translate_image_alt = QCheckBox(self.i18n.t("settings.advanced.translate_image_alt"))
        self.adv_translate_image_alt.setChecked(bool(getattr(self.config, "translate_image_alt", False)))

        self.adv_code_like_short_line_max_chars = QSpinBox()
        self.adv_code_like_short_line_max_chars.setRange(20, 200)
        self.adv_code_like_short_line_max_chars.setValue(int(getattr(self.config, "code_like_short_line_max_chars", 80)))

        # Tabs + scroll
        self.tabs = QTabWidget()

        def wrap_scroll(page: QWidget) -> QScrollArea:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.NoFrame)
            area.setWidget(page)
            return area

        # Providers tab
        providers_page = QWidget()
        providers_layout = QVBoxLayout(providers_page)
        providers_layout.setContentsMargins(0, 0, 0, 0)
        providers_layout.setSpacing(12)

        providers_form = QFormLayout()
        providers_form.setContentsMargins(0, 0, 0, 0)
        providers_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        providers_form.addRow(self.i18n.t("settings.provider"), self.provider_combo)
        providers_layout.addLayout(providers_form)

        providers_help = QLabel(self.i18n.t("pm.help"))
        providers_help.setWordWrap(True)
        providers_help.setProperty("role", "muted")
        providers_layout.addWidget(providers_help)

        self.providers_table = QTableWidget()
        self.providers_table.setColumnCount(4)
        self.providers_table.setHorizontalHeaderLabels(
            [
                self.i18n.t("pm.table.name"),
                self.i18n.t("pm.table.base_url"),
                self.i18n.t("pm.table.model"),
                self.i18n.t("pm.table.rpm"),
            ]
        )
        self.providers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.providers_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.providers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.providers_table.setAlternatingRowColors(True)
        providers_layout.addWidget(self.providers_table, 1)

        provider_btn_row = QWidget()
        provider_btn_layout = QHBoxLayout(provider_btn_row)
        provider_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_add_provider = QPushButton(self.i18n.t("pm.btn.add"))
        self.btn_edit_provider = QPushButton(self.i18n.t("pm.btn.edit"))
        self.btn_remove_provider = QPushButton(self.i18n.t("pm.btn.remove"))
        self.btn_add_provider.setProperty("variant", "primary")
        self.btn_edit_provider.setProperty("variant", "secondary")
        self.btn_remove_provider.setProperty("variant", "danger")
        provider_btn_layout.addWidget(self.btn_add_provider)
        provider_btn_layout.addWidget(self.btn_edit_provider)
        provider_btn_layout.addWidget(self.btn_remove_provider)
        provider_btn_layout.addStretch(1)

        providers_layout.addWidget(provider_btn_row)

        # Translation tab
        translation_page = QWidget()
        translation_form = QFormLayout(translation_page)
        translation_form.setContentsMargins(0, 0, 0, 0)
        translation_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        translation_form.addRow(self.i18n.t("settings.translation_mode"), self.translation_mode_combo)
        translation_form.addRow(self.i18n.t("settings.max_concurrency"), self.concurrency_spin)
        translation_form.addRow(self.i18n.t("settings.max_retries"), self.retries_spin)
        translation_form.addRow(self.i18n.t("settings.temperature"), self.temp_spin)
        translation_form.addRow(self.i18n.t("settings.request_timeout"), self.timeout_spin)
        translation_form.addRow(self.i18n.t("settings.raw_system_prompt"), raw_prompt_container)
        translation_form.addRow(self.i18n.t("settings.structured_system_prompt"), structured_prompt_container)
        translation_form.addRow(self.structured_group)

        # Markdown tab
        markdown_page = QWidget()
        markdown_form = QFormLayout(markdown_page)
        markdown_form.setContentsMargins(0, 0, 0, 0)
        markdown_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        markdown_form.addRow(self.i18n.t("settings.front_matter"), fm_container)

        # Advanced tab
        advanced_page = QWidget()
        advanced_form = QFormLayout(advanced_page)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        advanced_form.addRow(self.adv_translate_link_text)
        advanced_form.addRow(self.adv_translate_image_alt)
        advanced_form.addRow(self.i18n.t("settings.advanced.code_like_short_line_max_chars"), self.adv_code_like_short_line_max_chars)

        self.tabs.addTab(wrap_scroll(providers_page), self.i18n.t("settings.tab.providers"))
        self.tabs.addTab(wrap_scroll(translation_page), self.i18n.t("settings.tab.translation"))
        self.tabs.addTab(wrap_scroll(markdown_page), self.i18n.t("settings.tab.markdown"))
        self.tabs.addTab(wrap_scroll(advanced_page), self.i18n.t("settings.tab.advanced"))

        card = QFrame()
        card.setProperty("variant", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)
        card_layout.addWidget(self.tabs)

        layout.addWidget(card)

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

        self.translation_mode_combo.currentIndexChanged.connect(self._sync_structured_controls_enabled)
        self._sync_structured_controls_enabled()

        self.btn_add_provider.clicked.connect(self.add_provider_inline)
        self.btn_edit_provider.clicked.connect(self.edit_provider_inline)
        self.btn_remove_provider.clicked.connect(self.remove_provider_inline)
        self.provider_combo.currentIndexChanged.connect(self._sync_provider_table_selection_from_combo)
        self.providers_table.itemSelectionChanged.connect(self._sync_provider_combo_from_table_selection)

        self._refresh_provider_table(select_row=self.provider_combo.currentIndex())

    def _sync_structured_controls_enabled(self) -> None:
        mode = self.translation_mode_combo.currentData() or getattr(self.config, "translation_mode", "raw_markdown")
        enabled = mode == "structured_graph"
        self.structured_group.setEnabled(enabled)

    def reset_raw_prompt(self):
        self.raw_prompt_edit.setPlainText(DEFAULT_RAW_SYSTEM_PROMPT)

    def reset_structured_prompt(self):
        self.structured_prompt_edit.setPlainText(DEFAULT_STRUCTURED_SYSTEM_PROMPT)

    def _refresh_provider_table(self, select_row: int | None = None) -> None:
        self.providers_table.setRowCount(len(self._providers_working))
        for row, provider in enumerate(self._providers_working):
            self.providers_table.setItem(row, 0, QTableWidgetItem(provider.name))
            self.providers_table.setItem(row, 1, QTableWidgetItem(provider.base_url))
            self.providers_table.setItem(row, 2, QTableWidgetItem(provider.model))
            self.providers_table.setItem(row, 3, QTableWidgetItem(str(int(provider.rpm_limit))))

        if select_row is not None and self._providers_working:
            row = max(0, min(select_row, len(self._providers_working) - 1))
            self.providers_table.selectRow(row)

    def _selected_provider_index(self) -> int | None:
        selection = self.providers_table.selectionModel().selectedRows()
        if not selection:
            return None
        return selection[0].row()

    def _unique_provider_name(self, base: str = "provider") -> str:
        existing = {p.name for p in self._providers_working if p.name}
        if base not in existing:
            return base
        i = 2
        while f"{base}{i}" in existing:
            i += 1
        return f"{base}{i}"

    def _sync_provider_table_selection_from_combo(self) -> None:
        idx = self.provider_combo.currentIndex()
        if idx >= 0:
            self.providers_table.selectRow(idx)

    def _sync_provider_combo_from_table_selection(self) -> None:
        idx = self._selected_provider_index()
        if idx is None or idx < 0:
            return
        if idx == self.provider_combo.currentIndex():
            return
        self.provider_combo.blockSignals(True)
        try:
            self.provider_combo.setCurrentIndex(idx)
        finally:
            self.provider_combo.blockSignals(False)

    def add_provider_inline(self) -> None:
        new_provider = ProviderConfig(name=self._unique_provider_name())
        existing_names = {p.name for p in self._providers_working if p.name}
        dialog = ProviderEditorDialog(
            new_provider,
            existing_names=existing_names - {new_provider.name},
            i18n=self.i18n,
            parent=self,
        )
        if not dialog.exec():
            return
        self._providers_working.append(dialog.get_provider())
        active_name = self.provider_combo.currentText().strip()
        self._refresh_provider_combo(preferred_active_name=active_name)
        self._refresh_provider_table(select_row=len(self._providers_working) - 1)

    def edit_provider_inline(self) -> None:
        idx = self._selected_provider_index()
        if idx is None:
            QMessageBox.information(self, self.i18n.t("info.title"), self.i18n.t("pm.select_to_edit"))
            return

        provider = self._providers_working[idx]
        existing_names = {p.name for p in self._providers_working if p.name} - {provider.name}
        dialog = ProviderEditorDialog(provider, existing_names=existing_names, i18n=self.i18n, parent=self)
        if not dialog.exec():
            return

        edited = dialog.get_provider()
        active_name = self.provider_combo.currentText().strip()
        if active_name == provider.name:
            active_name = edited.name

        self._providers_working[idx] = edited
        self._refresh_provider_combo(preferred_active_name=active_name)
        self._refresh_provider_table(select_row=idx)

    def remove_provider_inline(self) -> None:
        idx = self._selected_provider_index()
        if idx is None:
            QMessageBox.information(self, self.i18n.t("info.title"), self.i18n.t("pm.select_to_remove"))
            return
        if len(self._providers_working) <= 1:
            QMessageBox.warning(self, self.i18n.t("settings.validation.title"), self.i18n.t("pm.err.need_one"))
            return

        provider = self._providers_working[idx]
        reply = QMessageBox.question(
            self,
            self.i18n.t("pm.remove.title"),
            self.i18n.t("pm.remove.confirm", name=provider.name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        active_name = self.provider_combo.currentText().strip()
        removed = self._providers_working.pop(idx)
        if active_name == removed.name:
            active_name = self._providers_working[0].name if self._providers_working else ""

        self._refresh_provider_combo(preferred_active_name=active_name)
        self._refresh_provider_table(select_row=min(idx, max(0, len(self._providers_working) - 1)))

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
            QMessageBox.warning(self, self.i18n.t("settings.validation.title"), str(e))
            return
        super().accept()

    def get_new_config(self) -> AppConfig:
        active_provider_name = self.provider_combo.currentText().strip()
        if not active_provider_name and self._providers_working:
            active_provider_name = self._providers_working[0].name

        # Ensure active provider still exists.
        if not any(p.name == active_provider_name for p in self._providers_working):
            active_provider_name = self._providers_working[0].name

        fm_keys: list[str] = []
        if self.fm_cb_title.isChecked():
            fm_keys.append("title")
        if self.fm_cb_tags.isChecked():
            fm_keys.append("tags")
        if self.fm_cb_description.isChecked():
            fm_keys.append("description")
        if self.fm_cb_summary.isChecked():
            fm_keys.append("summary")
        if self.fm_cb_categories.isChecked():
            fm_keys.append("categories")

        return AppConfig(
            active_provider=active_provider_name,
            ui_language=self.config.ui_language,
            source_language=getattr(self.config, "source_language", "English"),
            target_language=getattr(self.config, "target_language", "简体中文"),
            providers=[p.model_copy(deep=True) for p in self._providers_working],
            max_concurrency=self.concurrency_spin.value(),
            max_retries=self.retries_spin.value(),
            temperature=float(self.temp_spin.value()),
            request_timeout=int(self.timeout_spin.value()),
            raw_system_prompt=self.raw_prompt_edit.toPlainText(),
            structured_system_prompt=self.structured_prompt_edit.toPlainText(),
            translation_mode=self.translation_mode_combo.currentData() or getattr(self.config, "translation_mode", "raw_markdown"),
            structured_chunk_tokens=int(self.structured_chunk_tokens_spin.value()),
            structured_memory_max_tokens=int(self.structured_memory_max_tokens_spin.value()),
            structured_max_repair_attempts=int(self.structured_max_repair_attempts_spin.value()),
            translate_link_text=bool(self.adv_translate_link_text.isChecked()),
            translate_image_alt=bool(self.adv_translate_image_alt.isChecked()),
            code_like_short_line_max_chars=int(self.adv_code_like_short_line_max_chars.value()),
            front_matter_translate_keys=fm_keys,
            front_matter_custom_keys=self.fm_custom_edit.text(),
            front_matter_denylist_keys=getattr(self.config, "front_matter_denylist_keys", ["slug", "url", "permalink", "date", "draft", "layout", "type", "id"]),
        )
