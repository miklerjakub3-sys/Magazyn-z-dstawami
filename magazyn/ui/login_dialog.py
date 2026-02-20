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


class LoginDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Logowanie")
        self.setModal(True)
        self.resize(420, 220)

        root = QVBoxLayout(self)
        title = QLabel("Zaloguj się do programu")
        title.setProperty("title", True)
        root.addWidget(title)

        form = QFormLayout()
        self.in_login = QLineEdit()
        self.in_login.setPlaceholderText("Login")
        self.in_password = QLineEdit()
        self.in_password.setEchoMode(QLineEdit.Password)
        self.in_password.setPlaceholderText("Hasło")
        self.chk_remember = QCheckBox("Zapamiętaj mnie")

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
