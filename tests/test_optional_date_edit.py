import pytest
from PySide6.QtCore import QDate

pytest.importorskip("pytestqt")


def _optional_date_edit_cls():
    try:
        from magazyn.ui.tabs_deliveries import OptionalDateEdit
        return OptionalDateEdit
    except ImportError as exc:
        pytest.skip(f"PySide6 UI dependencies unavailable in this environment: {exc}")


def test_optional_date_edit_starts_with_empty_sentinel(qtbot):
    OptionalDateEdit = _optional_date_edit_cls()
    w = OptionalDateEdit()
    qtbot.addWidget(w)

    assert w.date() == w.minimumDate()
    assert w.minimumDate() == QDate(2024, 12, 31)


def test_optional_date_edit_clamps_manual_date_before_2025(qtbot):
    OptionalDateEdit = _optional_date_edit_cls()
    w = OptionalDateEdit()
    qtbot.addWidget(w)

    w.setDate(QDate(2024, 5, 1))
    assert w.date() == QDate(2025, 1, 1)


def test_optional_date_edit_keeps_sentinel_state(qtbot):
    OptionalDateEdit = _optional_date_edit_cls()
    w = OptionalDateEdit()
    qtbot.addWidget(w)

    w.setDate(w.minimumDate())
    assert w.date() == w.minimumDate()
