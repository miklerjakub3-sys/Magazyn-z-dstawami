from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..services import MagazynService
from .splash import get_logo_pixmap


class PasswordRecoveryDialog(QDialog):
    def __init__(self, svc: MagazynService, parent=None) -> None:
        super().__init__(parent)
        self.svc = svc
        self.setWindowTitle("Odzyskiwanie hasła administratora")
        self.resize(520, 280)

        root = QVBoxLayout(self)
        card = QFrame()
        card.setProperty("card", True)
        lay = QVBoxLayout(card)

        form = QFormLayout()
        self.in_email = QLineEdit()
        self.in_email.setPlaceholderText("E-mail administratora")
        self.in_code = QLineEdit()
        self.in_code.setPlaceholderText("Kod z e-maila")
        self.in_new_password = QLineEdit()
        self.in_new_password.setEchoMode(QLineEdit.Password)
        self.in_new_password.setPlaceholderText("Nowe hasło")
        form.addRow("E-mail:", self.in_email)
        form.addRow("Kod:", self.in_code)
        form.addRow("Nowe hasło:", self.in_new_password)
        lay.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_send_code = QPushButton("Wyślij kod")
        self.btn_send_code.setProperty("role", "secondary")
        self.btn_reset = QPushButton("Ustaw nowe hasło")
        self.btn_reset.setProperty("role", "primary")
        self.btn_close = QPushButton("Zamknij")
        btn_row.addWidget(self.btn_send_code)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        lay.addLayout(btn_row)

        root.addWidget(card)

        self.btn_send_code.clicked.connect(self.on_send_code)
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_close.clicked.connect(self.reject)

    def on_send_code(self) -> None:
        try:
            self.svc.send_admin_reset_code(self.in_email.text().strip())
            QMessageBox.information(self, "Odzyskiwanie", "Kod został wysłany na podany e-mail.")
        except Exception as e:
            QMessageBox.warning(self, "Odzyskiwanie", str(e))

    def on_reset(self) -> None:
        try:
            self.svc.reset_admin_password_with_code(
                self.in_email.text().strip(),
                self.in_code.text().strip(),
                self.in_new_password.text(),
            )
            QMessageBox.information(self, "Odzyskiwanie", "Hasło administratora zostało zresetowane.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Odzyskiwanie", str(e))




class FirstPasswordSetupDialog(QDialog):
    def __init__(self, login: str, svc: MagazynService, parent=None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._login = login
        self.setWindowTitle("Ustaw hasło administratora")
        self.resize(420, 220)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.in_password = QLineEdit()
        self.in_password.setEchoMode(QLineEdit.Password)
        self.in_password2 = QLineEdit()
        self.in_password2.setEchoMode(QLineEdit.Password)
        form.addRow("Nowe hasło:", self.in_password)
        form.addRow("Powtórz hasło:", self.in_password2)
        root.addWidget(QLabel(f"Konto '{login}' wymaga konfiguracji hasła przed pierwszym logowaniem."))
        root.addLayout(form)

        row = QHBoxLayout()
        row.addStretch(1)
        b_cancel = QPushButton("Anuluj")
        b_ok = QPushButton("Zapisz hasło")
        b_ok.setProperty("role", "primary")
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        root.addLayout(row)

        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self._save)

    def _save(self) -> None:
        p1 = self.in_password.text()
        p2 = self.in_password2.text()
        if p1 != p2:
            QMessageBox.warning(self, "Hasło", "Hasła nie są takie same.")
            return
        try:
            self._svc.setup_password_for_login(self._login, p1)
        except Exception as e:
            QMessageBox.warning(self, "Hasło", str(e))
            return
        QMessageBox.information(self, "Hasło", "Hasło zostało ustawione. Możesz się zalogować.")
        self.accept()

class LoginDialog(QDialog):
    def __init__(self, svc: MagazynService, parent=None) -> None:
        super().__init__(parent)
        self.svc = svc
        self.setWindowTitle("Logowanie")
        self.setModal(True)
        self.resize(640, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setProperty("card", True)
        root.addWidget(card)

        content = QVBoxLayout(card)
        content.setContentsMargins(28, 24, 28, 24)
        content.setSpacing(10)

        logo = QLabel()
        pm = get_logo_pixmap(height=96)
        if not pm.isNull():
            logo.setPixmap(pm)
        content.addWidget(logo)

        title = QLabel("Magazyn z dostawami")
        title.setProperty("title", True)
        content.addWidget(title)

        subtitle = QLabel("Zaloguj się do systemu")
        subtitle.setProperty("subtitle", True)
        content.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        self.in_login = QLineEdit()
        self.in_login.setPlaceholderText("Login")
        self.in_password = QLineEdit()
        self.in_password.setEchoMode(QLineEdit.Password)
        self.in_password.setPlaceholderText("Hasło")
        self.chk_remember = QCheckBox("Zapamiętaj mnie")
        self.chk_remember.setEnabled(False)
        self.chk_remember.setToolTip("Opcja tymczasowo wyłączona ze względów bezpieczeństwa.")

        for w in (self.in_login, self.in_password):
            w.setMinimumHeight(36)

        form.addRow("Login:", self.in_login)
        form.addRow("Hasło:", self.in_password)
        content.addLayout(form)
        content.addWidget(self.chk_remember)

        self.btn_forgot = QPushButton("Nie pamiętam hasła")
        self.btn_forgot.setProperty("role", "secondary")
        content.addWidget(self.btn_forgot, alignment=Qt.AlignLeft)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_cancel = QPushButton("Anuluj")
        self.btn_login = QPushButton("Zaloguj")
        self.btn_login.setProperty("role", "primary")
        self.btn_login.setDefault(True)
        self.btn_login.setAutoDefault(True)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_login)
        content.addLayout(row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_login.clicked.connect(self.accept)
        self.btn_forgot.clicked.connect(self.on_forgot_password)
        self.in_password.returnPressed.connect(self.btn_login.click)
        self.in_login.returnPressed.connect(self.in_password.setFocus)

    def on_forgot_password(self) -> None:
        dlg = PasswordRecoveryDialog(self.svc, self)
        dlg.exec()

    def credentials(self):
        return self.in_login.text().strip(), self.in_password.text(), bool(self.chk_remember.isChecked())
