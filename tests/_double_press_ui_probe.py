"""Drive the real action, double-press and Actions Ring pickers offscreen and report what happened as JSON.

Run by tests/test_double_press_ui.py in a subprocess: QML needs a
QApplication, and other tests in the same process create a
QCoreApplication first, which would rule one out.

The probe loads the real ScrollPage.qml and MousePage.qml with a real
Backend (backed by a fake engine), clicks the controls the way a user does,
and records every config the Backend saves.
"""

import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt, QUrl, Q_ARG  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import _app_log_guard  # noqa: E402,F401  (before main_qml: keeps the real log clean)

import main_qml  # noqa: E402  (sets the Material style the pages use)
from core.config import DEFAULT_CONFIG  # noqa: E402
from test_backend import _FakeEngine  # noqa: E402
from ui.backend import Backend  # noqa: E402
from ui.locale_manager import LocaleManager  # noqa: E402

QML_DIR = ROOT / "ui" / "qml"
report = {"saved": [], "qml_errors": []}


def _settle():
    for _ in range(5):
        app.processEvents()
        QTest.qWait(20)


def _find_item(item, name):
    """Depth-first search of the visual item tree. Repeater delegates are
    visual children of their row but not QObject children, so findChild
    cannot see them."""
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = _find_item(child, name)
        if found is not None:
            return found
    return None


def _click(window, item, fx=0.5, fy=0.5):
    point = item.mapToScene(QPointF(item.width() * fx, item.height() * fy))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
    _settle()


def _load(page_type, backend, ui_state, locale):
    engine = QQmlApplicationEngine()
    engine.warnings.connect(
        lambda warnings: report["qml_errors"].extend(
            w.toString() for w in warnings
            if any(k in w.toString()
                   for k in ("doublePress", "double_press", "ActionAccordion"))
        )
    )
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("uiState", ui_state)
    ctx.setContextProperty("lm", locale)
    source = (
        "import QtQuick\nimport QtQuick.Window\n"
        "Window { width: 1000; height: 3200; visible: true\n"
        f"  {page_type} {{ objectName: \"page\"; anchors.fill: parent }} }}\n"
    )
    engine.loadData(source.encode(), QUrl.fromLocalFile(str(QML_DIR / "probe.qml")))
    _settle()
    window = engine.rootObjects()[0]
    return engine, window, window.findChild(QQuickItem, "page")


def main():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["profiles"]["default"]["mappings"]["xbutton2_double"] = "paste"

    def save(c):
        report["saved"].append(copy.deepcopy(c))

    with (
        patch("ui.backend.load_config", return_value=cfg),
        patch("ui.backend.save_config", side_effect=save),
        patch("core.config.save_config", side_effect=save),
        patch("ui.backend.supports_login_startup", return_value=False),
    ):
        fake_engine = _FakeEngine()
        fake_engine.smart_shift_force_supported = False
        report["engine_reloads"] = 0

        def reload_mappings():
            report["engine_reloads"] += 1

        fake_engine.reload_mappings = reload_mappings
        backend = Backend(engine=fake_engine)
        ui_state = main_qml.UiState(app)
        locale = LocaleManager()

        # ── Settings card ───────────────────────────────────────────
        engine, window, page = _load("ScrollPage", backend, ui_state, locale)
        card = page.findChild(QObject, "doublePressCard")
        desc = page.findChild(QObject, "doublePressModeDesc")
        report["card_visible"] = bool(card and card.property("visible"))
        report["desc_instant"] = desc.property("text")
        _click(window, _find_item(page, "doublePressMode_wait"))
        report["mode_after_click"] = backend.doublePressMode
        report["desc_wait"] = desc.property("text")
        slider = page.findChild(QObject, "doublePressWindowSlider")
        _click(window, slider, fx=0.95)
        report["window_after_click"] = backend.doublePressWindowMs
        report["window_label"] = page.findChild(
            QObject, "doublePressWindowLabel").property("text")
        engine.deleteLater()
        _settle()

        # ── Button panel ────────────────────────────────────────────
        engine, window, page = _load("MousePage", backend, ui_state, locale)
        page.setProperty("selectedButton", "xbutton2")
        # The action panel animates open (250 ms height Behavior); click only
        # once it has settled, or the click lands where the header used to be.
        QTest.qWait(600)
        _settle()
        section = _find_item(page, "doublePressSection")
        header = _find_item(page, "doublePressHeader")
        body = _find_item(page, "doublePressBody")
        current = _find_item(page, "doublePressCurrent")
        report["section_visible_forward"] = section.isVisible()
        report["current_forward"] = current.property("text")
        report["body_visible_collapsed"] = body.isVisible()
        _click(window, header)
        report["body_visible_expanded"] = body.isVisible()
        paste_chip = _find_item(page, "doublePressChip_paste")
        report["current_category_open"] = paste_chip.isVisible()
        copy_category = next(c["category"] for c in backend.actionCategories
                             if any(a["id"] == "copy" for a in c["actions"]))
        copy_chip = _find_item(page, "doublePressChip_copy")
        if not copy_chip.isVisible():
            _click(window, _find_item(page, "doublePressCategory_" + copy_category))
        _click(window, copy_chip)
        report["double_after_pick"] = backend.doublePressActionFor("default", "xbutton2")
        report["current_after_pick"] = current.property("text")
        report["single_after_pick"] = (
            backend._cfg["profiles"]["default"]["mappings"]["xbutton2"])
        _click(window, header)
        report["body_visible_recollapsed"] = body.isVisible()

        # ── Main action: the same accordion ─────────────────────────
        a_header = _find_item(page, "actionHeader")
        a_body = _find_item(page, "actionBody")
        a_current = _find_item(page, "actionCurrent")
        report["action_current_forward"] = a_current.property("text")
        report["action_body_visible_collapsed"] = a_body.isVisible()
        _click(window, a_header)
        report["action_body_visible_expanded"] = a_body.isVisible()
        report["action_current_category_open"] = _find_item(
            page, "actionChip_mouse_forward_click").isVisible()
        cut_category = next(c["category"] for c in backend.actionCategories
                            if any(a["id"] == "cut" for a in c["actions"]))
        cut_chip = _find_item(page, "actionChip_cut")
        if not cut_chip.isVisible():
            _click(window, _find_item(page, "actionCategory_" + cut_category))
        _click(window, cut_chip)
        report["action_after_pick"] = (
            backend._cfg["profiles"]["default"]["mappings"]["xbutton2"])
        report["action_current_after_pick"] = a_current.property("text")
        report["double_after_action_pick"] = backend.doublePressActionFor(
            "default", "xbutton2")
        page.setProperty("selectedButton", "xbutton1")
        _settle()
        report["action_body_collapsed_on_new_button"] = not a_body.isVisible()
        page.setProperty("selectedButton", "hscroll_left")
        _settle()
        report["section_visible_hscroll"] = bool(section.property("visible"))
        engine.deleteLater()
        _settle()

        # ── Actions Ring slots: one accordion per slot, one open at once ─
        engine, window, page = _load("ActionsRingConfig", backend, ui_state, locale)
        slot1_header = _find_item(page, "ringSlot1Header")
        slot1_body = _find_item(page, "ringSlot1Body")
        report["ring_slot1_collapsed"] = not slot1_body.isVisible()
        _click(window, slot1_header)
        report["ring_slot1_expanded"] = slot1_body.isVisible()
        copy_chip = _find_item(page, "ringSlot1Chip_copy")
        if not copy_chip.isVisible():
            _click(window, _find_item(page, "ringSlot1Category_" + copy_category))
        _click(window, copy_chip)
        report["ring_slots_after_pick"] = list(backend.actionsRingSlots)
        report["ring_slot1_current"] = _find_item(
            page, "ringSlot1Current").property("text")
        _click(window, _find_item(page, "ringSlot2Header"))
        report["ring_slot2_expanded"] = _find_item(page, "ringSlot2Body").isVisible()
        report["ring_slot1_closed_by_slot2"] = not slot1_body.isVisible()
        engine.deleteLater()
        _settle()

    report["saved"] = [
        {
            "double_press_mode": c["settings"].get("double_press_mode"),
            "double_press_window_ms": c["settings"].get("double_press_window_ms"),
            "xbutton2_double": c["profiles"]["default"]["mappings"].get("xbutton2_double"),
            "xbutton2": c["profiles"]["default"]["mappings"].get("xbutton2"),
        }
        for c in report["saved"]
    ]
    print("PROBE_REPORT " + json.dumps(report))


if __name__ == "__main__":
    main()
