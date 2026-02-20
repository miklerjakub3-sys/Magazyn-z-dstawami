from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .splash import get_logo_pixmap


class LoginDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Logowanie")
        self.setModal(True)
        self.resize(560, 320)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(10)

        logo = QLabel()
        pm = get_logo_pixmap(height=88)
        if not pm.isNull():
            logo.setPixmap(pm)
        root.addWidget(logo)

        title = QLabel("Magazyn z dostawami")
        title.setProperty("title", True)
        root.addWidget(title)

        subtitle = QLabel("Logowanie")
        subtitle.setProperty("subtitle", True)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        self.in_login = QLineEdit()
        self.in_login.setPlaceholderText("Login")
        self.in_password = QLineEdit()
        self.in_password.setEchoMode(QLineEdit.Password)
        self.in_password.setPlaceholderText("Hasło")
        self.chk_remember = QCheckBox("Zapamiętaj mnie")
        self.chk_remember.setEnabled(False)
        self.chk_remember.setToolTip("Opcja tymczasowo wyłączona ze względów bezpieczeństwa.")

        form.addRow("Login:", self.in_login)
        form.addRow("Hasło:", self.in_password)
        root.addLayout(form)
        root.addWidget(self.chk_remember)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_cancel = QPushButton("Anuluj")
        self.btn_login = QPushButton("Zaloguj")
        self.btn_login.setProperty("role", "primary")
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_login)
        root.addLayout(row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_login.clicked.connect(self.accept)

    def credentials(self):
        return self.in_login.text().strip(), self.in_password.text(), bool(self.chk_remember.isChecked())
