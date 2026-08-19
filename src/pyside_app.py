from __future__ import annotations

import argparse
import datetime
import os
import sys
import traceback
from typing import Dict, List, Optional


def build_arg_parser():
    p = argparse.ArgumentParser(description="Beat Banger Legacy -> Release conversion GUI")
    p.add_argument("--gui", action="store_true", help="Launch the PySide6 conversion interface")
    p.add_argument("input_mod", nargs="?", default="",
                   help="Path to the Legacy mod folder (containing chart.cfg)")
    p.add_argument("output_mod", nargs="?", default=None,
                   help="Where to write the Release mod. Defaults to '<input_mod>_Release' next to the input.")
    p.add_argument("--assets-dir", default=None,
                   help="Only needed if Legacy assets live outside input_mod. Defaults to input_mod.")
    p.add_argument("--no-copy-assets", action="store_true")
    p.add_argument("--no-interactive", action="store_true",
                   help="Don't prompt for effect sprite sheet layout (falls back to overrides/warnings only)")
    p.add_argument("--no-last-transition", action="store_true",
                   help="Omit last_transition from the final timeline frame")
    p.add_argument("--scenario-name", default=None,
                   help="Name for the single scenario folder (defaults to the Legacy chart's 'name' field)")
    return p


def _default_output_for(input_mod: str) -> str:
    if not input_mod:
        return ""
    input_mod = os.path.abspath(input_mod)
    return input_mod.rstrip(os.sep) + "_Release"


def launch_gui():
    try:
        from PySide6.QtCore import Qt, QThread, Signal, QSize
        from PySide6.QtGui import QPixmap, QFont, QTextCursor, QColor, QIcon
        from PySide6.QtWidgets import (
            QApplication,
            QWidget,
            QMainWindow,
            QVBoxLayout,
            QHBoxLayout,
            QGridLayout,
            QFormLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QCheckBox,
            QGroupBox,
            QScrollArea,
            QFrame,
            QFileDialog,
            QMessageBox,
            QTabWidget,
            QPlainTextEdit,
            QListWidget,
            QListWidgetItem,
            QTableWidget,
            QTableWidgetItem,
            QSplitter,
            QStatusBar,
            QHeaderView,
            QSizePolicy,
        )
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "PySide6 is not available in this Python installation. "
            "Install it with: pip install PySide6"
        ) from exc

    from .mod_library import discover_mods, load_settings, save_settings

    # ------------------------------------------------------------------
    # Background worker: runs one conversion off the UI thread.
    # ------------------------------------------------------------------
    class ConversionWorker(QThread):
        finished_ok = Signal(dict, dict, str)
        failed = Signal(str, str)

        def __init__(self, input_mod, output_mod, assets_dir, no_copy_assets,
                     no_interactive, include_last_transition, scenario_name, parent=None):
            super().__init__(parent)
            self.input_mod = input_mod
            self.output_mod = output_mod
            self.assets_dir = assets_dir
            self.no_copy_assets = no_copy_assets
            self.no_interactive = no_interactive
            self.include_last_transition = include_last_transition
            self.scenario_name = scenario_name

        def run(self):
            try:
                from .convert_mod import build_release_mod

                summary, issues = build_release_mod(
                    self.input_mod,
                    self.output_mod,
                    assets_dir=self.assets_dir,
                    include_last_transition=self.include_last_transition,
                    copy_assets_flag=not self.no_copy_assets,
                    scenario_name=self.scenario_name,
                    interactive_sheets=not self.no_interactive,
                )
                debug_text = ""
                debug_path = summary.get("debug") if isinstance(summary, dict) else None
                if debug_path and os.path.isfile(debug_path):
                    try:
                        with open(debug_path, "r", encoding="utf-8") as handle:
                            debug_text = handle.read()
                    except OSError as exc:
                        debug_text = f"(Could not read debug file: {exc})"
                self.finished_ok.emit(summary, issues, debug_text)
            except Exception as exc:  # noqa: BLE001 - surfaced in the GUI
                self.failed.emit(f"{type(exc).__name__}: {exc}", traceback.format_exc())

    # ------------------------------------------------------------------
    # One card per discovered Legacy mod.
    # ------------------------------------------------------------------
    class ModCard(QFrame):
        convert_requested = Signal(dict)

        THUMB_SIZE = QSize(128, 96)

        def __init__(self, mod_info: Dict[str, object], parent=None):
            super().__init__(parent)
            self.mod_info = mod_info
            self.setFrameShape(QFrame.StyledPanel)
            self.setFrameShadow(QFrame.Raised)
            self.setObjectName("modCard")

            layout = QHBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)

            thumb_label = QLabel()
            thumb_label.setFixedSize(self.THUMB_SIZE)
            thumb_label.setAlignment(Qt.AlignCenter)
            thumb_label.setStyleSheet("background-color: #22252b; border: 1px solid #3a3f47; border-radius: 4px;")
            thumb_path = mod_info.get("thumb")
            pixmap = None
            if thumb_path:
                candidate = QPixmap(str(thumb_path))
                if not candidate.isNull():
                    pixmap = candidate
            if pixmap is not None:
                thumb_label.setPixmap(
                    pixmap.scaled(self.THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            else:
                thumb_label.setText("No\nthumbnail")
            layout.addWidget(thumb_label)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(4)

            name_label = QLabel(str(mod_info.get("name") or "Untitled mod"))
            name_font = QFont()
            name_font.setBold(True)
            name_font.setPointSize(name_font.pointSize() + 1)
            name_label.setFont(name_font)
            info_layout.addWidget(name_label)

            subtitle = str(mod_info.get("song_title") or mod_info.get("artist") or "Legacy mod")
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet("color: #9aa0a6;")
            info_layout.addWidget(subtitle_label)

            path_label = QLabel(str(mod_info.get("path") or ""))
            path_label.setWordWrap(True)
            path_label.setStyleSheet("color: #6f7580; font-size: 10px;")
            info_layout.addWidget(path_label)

            info_layout.addStretch(1)

            self.convert_button = QPushButton("Convert to Release")
            self.convert_button.clicked.connect(lambda: self.convert_requested.emit(self.mod_info))
            info_layout.addWidget(self.convert_button, alignment=Qt.AlignLeft)

            layout.addLayout(info_layout, 1)

        def set_busy(self, busy: bool, label: Optional[str] = None):
            self.convert_button.setEnabled(not busy)
            self.convert_button.setText(label or ("Converting..." if busy else "Convert to Release"))

    # ------------------------------------------------------------------
    # The improved in-app debugger: per-run history + categorized
    # summary/warnings/errors + a searchable raw diagnostic log.
    # ------------------------------------------------------------------
    class DebuggerPanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._runs: List[Dict[str, object]] = []

            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)

            splitter = QSplitter(Qt.Horizontal)
            root.addWidget(splitter)

            # -- left: run history -----------------------------------
            history_box = QWidget()
            history_layout = QVBoxLayout(history_box)
            history_layout.setContentsMargins(4, 4, 4, 4)
            history_layout.addWidget(QLabel("Conversion history"))
            self.history_list = QListWidget()
            self.history_list.currentRowChanged.connect(self._on_history_selected)
            history_layout.addWidget(self.history_list)
            clear_btn = QPushButton("Clear history")
            clear_btn.clicked.connect(self.clear_history)
            history_layout.addWidget(clear_btn)
            splitter.addWidget(history_box)

            # -- right: detail tabs ------------------------------------
            self.tabs = QTabWidget()
            splitter.addWidget(self.tabs)
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setSizes([220, 700])

            # Summary tab
            self.summary_table = QTableWidget(0, 2)
            self.summary_table.setHorizontalHeaderLabels(["Field", "Value"])
            self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.summary_table.verticalHeader().setVisible(False)
            self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.tabs.addTab(self.summary_table, "Summary")

            # Warnings tab
            self.warnings_list = QListWidget()
            self.tabs.addTab(self.warnings_list, "Warnings")

            # Errors tab
            self.errors_list = QListWidget()
            self.tabs.addTab(self.errors_list, "Errors")

            # Raw debug log tab, with search
            raw_tab = QWidget()
            raw_layout = QVBoxLayout(raw_tab)
            raw_layout.setContentsMargins(4, 4, 4, 4)
            search_row = QHBoxLayout()
            self.search_box = QLineEdit()
            self.search_box.setPlaceholderText("Search the raw diagnostic log...")
            self.search_box.returnPressed.connect(self._find_next)
            search_row.addWidget(self.search_box)
            find_next_btn = QPushButton("Find next")
            find_next_btn.clicked.connect(self._find_next)
            search_row.addWidget(find_next_btn)
            find_prev_btn = QPushButton("Find previous")
            find_prev_btn.clicked.connect(self._find_prev)
            search_row.addWidget(find_prev_btn)
            self.search_status = QLabel("")
            search_row.addWidget(self.search_status)
            search_row.addStretch(1)
            raw_layout.addLayout(search_row)

            self.raw_log = QPlainTextEdit()
            self.raw_log.setReadOnly(True)
            mono = QFont("Consolas")
            mono.setStyleHint(QFont.Monospace)
            mono.setPointSize(9)
            self.raw_log.setFont(mono)
            raw_layout.addWidget(self.raw_log)
            self.tabs.addTab(raw_tab, "Raw debug log")

            self.clear()

        # -- helpers ---------------------------------------------------
        def _find_next(self):
            term = self.search_box.text()
            if not term:
                return
            found = self.raw_log.find(term)
            if not found:
                cursor = self.raw_log.textCursor()
                cursor.movePosition(QTextCursor.Start)
                self.raw_log.setTextCursor(cursor)
                found = self.raw_log.find(term)
            self.search_status.setText("" if found else "Not found")

        def _find_prev(self):
            term = self.search_box.text()
            if not term:
                return
            found = self.raw_log.find(term, QPlainTextEdit.FindBackward)
            if not found:
                cursor = self.raw_log.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.raw_log.setTextCursor(cursor)
                found = self.raw_log.find(term, QPlainTextEdit.FindBackward)
            self.search_status.setText("" if found else "Not found")

        def clear(self):
            self.summary_table.setRowCount(0)
            self.warnings_list.clear()
            self.errors_list.clear()
            self.raw_log.setPlainText("Run a conversion to see diagnostics here.")

        def clear_history(self):
            self._runs = []
            self.history_list.clear()
            self.clear()

        def _set_summary_table(self, rows):
            self.summary_table.setRowCount(len(rows))
            for row, (key, value) in enumerate(rows):
                self.summary_table.setItem(row, 0, QTableWidgetItem(str(key)))
                item = QTableWidgetItem(str(value))
                if key in ("errors",) and str(value) not in ("0", ""):
                    item.setForeground(QColor("#e05252"))
                elif key in ("warnings",) and str(value) not in ("0", ""):
                    item.setForeground(QColor("#d6a54a"))
                self.summary_table.setItem(row, 1, item)

        def _populate(self, run: Dict[str, object]):
            if run["status"] == "ok":
                summary = run["summary"] or {}
                issues = run["issues"] or {}
                self._set_summary_table(list(summary.items()))
                self.warnings_list.clear()
                for w in issues.get("warnings", []):
                    QListWidgetItem(f"⚠ {w}", self.warnings_list)
                self.errors_list.clear()
                for e in issues.get("errors", []):
                    item = QListWidgetItem(f"✖ {e}")
                    item.setForeground(QColor("#e05252"))
                    self.errors_list.addItem(item)
                self.raw_log.setPlainText(run.get("debug_text") or "(No raw debug log was produced.)")
            else:
                self._set_summary_table([
                    ("status", "FAILED"),
                    ("mod", run["mod_name"]),
                    ("error", run["error_summary"]),
                ])
                self.warnings_list.clear()
                self.errors_list.clear()
                item = QListWidgetItem(f"✖ {run['error_summary']}")
                item.setForeground(QColor("#e05252"))
                self.errors_list.addItem(item)
                self.raw_log.setPlainText(run.get("traceback_text") or "")

        def _on_history_selected(self, row: int):
            if 0 <= row < len(self._runs):
                self._populate(self._runs[row])

        def add_success(self, mod_name: str, summary: dict, issues: dict, debug_text: str):
            run = {
                "status": "ok",
                "mod_name": mod_name,
                "summary": summary,
                "issues": issues,
                "debug_text": debug_text,
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            }
            self._runs.append(run)
            errors_n = len((issues or {}).get("errors", []))
            warnings_n = len((issues or {}).get("warnings", []))
            status_icon = "✖" if errors_n else ("⚠" if warnings_n else "✔")
            entry = QListWidgetItem(f"{status_icon} {run['timestamp']}  {mod_name}")
            if errors_n:
                entry.setForeground(QColor("#e05252"))
            elif warnings_n:
                entry.setForeground(QColor("#d6a54a"))
            else:
                entry.setForeground(QColor("#57b06a"))
            self.history_list.addItem(entry)
            self.history_list.setCurrentRow(self.history_list.count() - 1)

        def add_failure(self, mod_name: str, error_summary: str, traceback_text: str):
            run = {
                "status": "failed",
                "mod_name": mod_name,
                "error_summary": error_summary,
                "traceback_text": traceback_text,
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            }
            self._runs.append(run)
            entry = QListWidgetItem(f"✖ {run['timestamp']}  {mod_name}")
            entry.setForeground(QColor("#e05252"))
            self.history_list.addItem(entry)
            self.history_list.setCurrentRow(self.history_list.count() - 1)

    # ------------------------------------------------------------------
    # Main window
    # ------------------------------------------------------------------
    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Beat Banger Legacy → Release Converter")
            self.resize(1100, 760)
            self.setMinimumSize(880, 600)

            self.settings = load_settings()
            self._workers: List[ConversionWorker] = []
            self._cards: List[ModCard] = []

            central = QWidget()
            self.setCentralWidget(central)
            outer = QVBoxLayout(central)
            outer.setContentsMargins(12, 12, 12, 12)

            # -- header: library chooser --------------------------------
            header = QHBoxLayout()
            header.addWidget(QLabel("Legacy mods folder"))
            self.library_edit = QLineEdit(str(self.settings.get("legacy_library") or ""))
            header.addWidget(self.library_edit, 1)
            choose_btn = QPushButton("Choose folder")
            choose_btn.clicked.connect(self.choose_library)
            header.addWidget(choose_btn)
            refresh_btn = QPushButton("Refresh")
            refresh_btn.clicked.connect(self.refresh_mods)
            header.addWidget(refresh_btn)
            outer.addLayout(header)

            # -- options --------------------------------------------------
            options_box = QGroupBox("Conversion options")
            options_layout = QVBoxLayout(options_box)

            checks_row = QHBoxLayout()
            self.no_copy_assets_cb = QCheckBox("Skip copying assets")
            checks_row.addWidget(self.no_copy_assets_cb)
            self.no_interactive_cb = QCheckBox("Skip interactive sheet prompts")
            checks_row.addWidget(self.no_interactive_cb)
            self.include_last_transition_cb = QCheckBox("Include final last_transition")
            self.include_last_transition_cb.setChecked(True)
            checks_row.addWidget(self.include_last_transition_cb)
            checks_row.addStretch(1)
            options_layout.addLayout(checks_row)

            form_row = QFormLayout()
            assets_row = QHBoxLayout()
            self.assets_dir_edit = QLineEdit()
            assets_row.addWidget(self.assets_dir_edit)
            assets_browse = QPushButton("Browse…")
            assets_browse.clicked.connect(self._choose_assets_dir)
            assets_row.addWidget(assets_browse)
            form_row.addRow("Assets dir (optional)", assets_row)

            self.scenario_name_edit = QLineEdit()
            form_row.addRow("Scenario name (optional)", self.scenario_name_edit)
            options_layout.addLayout(form_row)

            outer.addWidget(options_box)

            # -- mod grid ---------------------------------------------------
            grid_box = QGroupBox("Legacy mods")
            grid_box_layout = QVBoxLayout(grid_box)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.cards_host = QWidget()
            self.cards_layout = QGridLayout(self.cards_host)
            self.cards_layout.setAlignment(Qt.AlignTop)
            self.scroll_area.setWidget(self.cards_host)
            grid_box_layout.addWidget(self.scroll_area)
            outer.addWidget(grid_box, 2)

            # -- bottom: activity log + debugger -----------------------
            bottom_tabs = QTabWidget()

            self.log_box = QPlainTextEdit()
            self.log_box.setReadOnly(True)
            mono = QFont("Consolas")
            mono.setStyleHint(QFont.Monospace)
            mono.setPointSize(9)
            self.log_box.setFont(mono)
            bottom_tabs.addTab(self.log_box, "Activity log")

            self.debugger = DebuggerPanel()
            bottom_tabs.addTab(self.debugger, "Debugger")

            outer.addWidget(bottom_tabs, 2)

            # -- status bar ---------------------------------------------
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage("Select a Legacy mods folder.")

            saved_root = str(self.settings.get("legacy_library") or "")
            if saved_root and os.path.isdir(saved_root):
                self.refresh_mods()
            else:
                self.render_mod_grid([])

        # -- library handling ---------------------------------------------
        def _choose_assets_dir(self):
            path = QFileDialog.getExistingDirectory(self, "Select assets directory")
            if path:
                self.assets_dir_edit.setText(path)

        def choose_library(self):
            path = QFileDialog.getExistingDirectory(self, "Select Legacy mods folder")
            if path:
                self.library_edit.setText(path)
                self.refresh_mods()

        def refresh_mods(self):
            root_path = self.library_edit.text().strip()
            if not root_path:
                QMessageBox.critical(self, "Missing folder", "Select the folder that contains your Legacy mods first.")
                return
            if not os.path.isdir(root_path):
                QMessageBox.critical(self, "Invalid folder", "The selected Legacy mods folder does not exist.")
                return
            self.settings["legacy_library"] = os.path.abspath(root_path)
            try:
                save_settings(self.settings)
            except OSError as exc:
                QMessageBox.warning(self, "Settings", f"Could not save the selected folder:\n{exc}")

            mods = discover_mods(root_path)
            self.render_mod_grid(mods)
            self.status_bar.showMessage(f"Found {len(mods)} Legacy mod(s) in {os.path.abspath(root_path)}")

        # -- mod grid -------------------------------------------------------
        def render_mod_grid(self, mods: List[Dict[str, object]]):
            while self.cards_layout.count():
                item = self.cards_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._cards = []

            if not mods:
                placeholder = QLabel("No Legacy mods found. Each mod should be a folder containing chart.cfg.")
                placeholder.setStyleSheet("color: #9aa0a6;")
                self.cards_layout.addWidget(placeholder, 0, 0)
                return

            columns = 3
            for index, mod_info in enumerate(mods):
                row, column = divmod(index, columns)
                card = ModCard(mod_info)
                card.convert_requested.connect(self.start_conversion)
                self.cards_layout.addWidget(card, row, column)
                self._cards.append(card)
            for c in range(columns):
                self.cards_layout.setColumnStretch(c, 1)

        # -- conversion -------------------------------------------------------
        def start_conversion(self, mod_info: Dict[str, object]):
            input_mod = str(mod_info["path"])
            output_mod = _default_output_for(input_mod)
            mod_name = str(mod_info.get("name") or os.path.basename(input_mod))

            self._append_log(f"\nStarting conversion for: {input_mod}")
            self._append_log(f"Output: {output_mod}")

            previous_status = self.status_bar.currentMessage()
            self.status_bar.showMessage(f"Converting {mod_name}...")

            card = self._card_for(mod_info)
            if card is not None:
                card.set_busy(True)

            worker = ConversionWorker(
                input_mod,
                output_mod,
                self.assets_dir_edit.text().strip() or None,
                self.no_copy_assets_cb.isChecked(),
                self.no_interactive_cb.isChecked(),
                self.include_last_transition_cb.isChecked(),
                self.scenario_name_edit.text().strip() or None,
            )
            worker.finished_ok.connect(
                lambda summary, issues, debug_text: self._on_conversion_finished(
                    mod_name, card, previous_status, summary, issues, debug_text, worker
                )
            )
            worker.failed.connect(
                lambda error_summary, traceback_text: self._on_conversion_failed(
                    mod_name, card, previous_status, error_summary, traceback_text, worker
                )
            )
            self._workers.append(worker)
            worker.start()

        def _card_for(self, mod_info: Dict[str, object]) -> Optional[ModCard]:
            for card in self._cards:
                if card.mod_info is mod_info:
                    return card
            return None

        def _append_log(self, text: str):
            self.log_box.appendPlainText(text)
            self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

        def _cleanup_worker(self, worker):
            if worker in self._workers:
                self._workers.remove(worker)

        def _on_conversion_finished(self, mod_name, card, previous_status, summary, issues, debug_text, worker):
            self._append_log("\n=== Conversion completed ===")
            self._append_log(f"Summary:\n{summary}")
            self._append_log(f"Warnings/errors:\n{issues}")
            self.debugger.add_success(mod_name, summary, issues, debug_text)
            if card is not None:
                card.set_busy(False)
            self.status_bar.showMessage(previous_status or "Conversion finished.")
            self._cleanup_worker(worker)
            self.refresh_mods()

        def _on_conversion_failed(self, mod_name, card, previous_status, error_summary, traceback_text, worker):
            self._append_log("\n=== Conversion failed ===")
            self._append_log(error_summary)
            self._append_log(traceback_text)
            self.debugger.add_failure(mod_name, error_summary, traceback_text)
            if card is not None:
                card.set_busy(False)
            self.status_bar.showMessage(previous_status or "Conversion failed.")
            self._cleanup_worker(worker)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    app.exec()


def main():
    args = build_arg_parser().parse_args()
    if args.gui:
        launch_gui()
        return 0

    if not args.input_mod:
        raise SystemExit("You must provide an input mod directory or use --gui to open the graphical interface.")

    from .convert_mod import build_release_mod

    input_mod = os.path.abspath(args.input_mod)
    output_mod = args.output_mod or _default_output_for(input_mod)
    summary, issues = build_release_mod(
        input_mod,
        output_mod,
        assets_dir=args.assets_dir,
        include_last_transition=not args.no_last_transition,
        copy_assets_flag=not args.no_copy_assets,
        scenario_name=args.scenario_name,
        interactive_sheets=not args.no_interactive,
    )
    print({"summary": summary, "issues": issues})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
