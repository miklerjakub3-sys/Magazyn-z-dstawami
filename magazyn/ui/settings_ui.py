from __future__ import annotations

from datetime import datetime
import os

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import BACKUP_DIR, DB_PATH, MAIN_ADMIN_PASSWORD
from ..services import MagazynService
from ..backup import get_configured_backup_password


class AddUserDialog(QDialog):
    def __init__(self, svc: MagazynService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.svc = svc
        self.setWindowTitle("Dodaj użytkownika")

        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.in_admin_password = QLineEdit()
        self.in_admin_password.setEchoMode(QLineEdit.Password)
        self.in_login = QLineEdit()
        self.in_password = QLineEdit()
        self.in_password.setEchoMode(QLineEdit.Password)
        self.cmb_role = QComboBox()
        for role_id, role_name in self.svc.list_roles():
            self.cmb_role.addItem(role_name, int(role_id))

        form.addRow("Hasło główne:", self.in_admin_password)
        form.addRow("Login:", self.in_login)
        form.addRow("Hasło:", self.in_password)
        form.addRow("Ranga:", self.cmb_role)
        lay.addLayout(form)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Dodaj")
        btn_cancel = QPushButton("Anuluj")
        btn_cancel.setProperty("role", "secondary")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)

    def get_data(self):
        return (
            self.in_admin_password.text().strip(),
            self.in_login.text().strip(),
            self.in_password.text(),
            int(self.cmb_role.currentData()),
        )


class SettingsPage(QWidget):
    def __init__(self, svc: MagazynService) -> None:
        super().__init__()
        self.svc = svc

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        title = QLabel("Ustawienia")
        title.setProperty("title", True)
        root.addWidget(title)

        info_card = QFrame()
        info_card.setProperty("card", True)
        info_l = QVBoxLayout(info_card)
        info_l.addWidget(QLabel(f"Ścieżka bazy: {DB_PATH}"))
        info_l.addWidget(QLabel(f"Folder backupów: {BACKUP_DIR}"))
        root.addWidget(info_card)

        main_grid = QGridLayout()
        main_grid.setHorizontalSpacing(12)
        main_grid.setVerticalSpacing(12)

        backup_card = QFrame()
        backup_card.setProperty("card", True)
        backup_l = QVBoxLayout(backup_card)
        backup_l.addWidget(QLabel("Backup"))

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Autozapis co:"))
        self.cmb_interval = QComboBox()
        self.cmb_interval.addItem("15 minut", 15 * 60)
        self.cmb_interval.addItem("30 minut", 30 * 60)
        self.cmb_interval.addItem("60 minut", 60 * 60)
        self.cmb_interval.addItem("120 minut", 120 * 60)
        interval_row.addWidget(self.cmb_interval)
        self.btn_apply_interval = QPushButton("Zastosuj")
        self.btn_apply_interval.setProperty("role", "secondary")
        interval_row.addWidget(self.btn_apply_interval)
        interval_row.addStretch(1)
        backup_l.addLayout(interval_row)

        list_row = QHBoxLayout()
        self.lst_backups = QListWidget()
        list_row.addWidget(self.lst_backups, 1)

        side_btns = QVBoxLayout()
        self.btn_refresh = QPushButton("Odśwież listę")
        self.btn_create = QPushButton("Utwórz backup teraz")
        self.btn_create.setProperty("role", "primary")
        self.btn_restore = QPushButton("Przywróć zaznaczony backup")
        self.btn_restore.setProperty("role", "danger")
        side_btns.addWidget(self.btn_refresh)
        side_btns.addWidget(self.btn_create)
        side_btns.addWidget(self.btn_restore)
        side_btns.addStretch(1)
        list_row.addLayout(side_btns)

        backup_l.addLayout(list_row)

        users_card = QFrame()
        users_card.setProperty("card", True)
        users_l = QVBoxLayout(users_card)
        users_l.addWidget(QLabel("Użytkownicy i uprawnienia"))

        user_row = QHBoxLayout()
        self.lst_users = QListWidget()
        user_row.addWidget(self.lst_users, 1)

        user_buttons = QVBoxLayout()
        self.btn_users_refresh = QPushButton("Odśwież użytkowników")
        self.btn_user_add = QPushButton("Dodaj użytkownika")
        self.btn_user_save = QPushButton("Zapisz rolę i uprawnienia")
        self.btn_user_save.setProperty("role", "secondary")
        self.btn_user_add.setProperty("role", "primary")
        user_buttons.addWidget(self.btn_users_refresh)
        user_buttons.addWidget(self.btn_user_add)
        user_buttons.addWidget(self.btn_user_save)
        user_buttons.addStretch(1)
        user_row.addLayout(user_buttons)
        users_l.addLayout(user_row)

        role_row = QHBoxLayout()
        role_row.addWidget(QLabel("Ranga użytkownika:"))
        self.cmb_user_role = QComboBox()
        role_row.addWidget(self.cmb_user_role)
        role_row.addStretch(1)
        users_l.addLayout(role_row)

        users_l.addWidget(QLabel("Uprawnienia roli (ptaszki):"))
        self.perm_wrap = QWidget()
        self.perm_grid = QGridLayout(self.perm_wrap)
        self.perm_grid.setContentsMargins(0, 0, 0, 0)
        self.perm_grid.setHorizontalSpacing(10)
        self.perm_grid.setVerticalSpacing(6)
        users_l.addWidget(self.perm_wrap)

        recovery_row = QHBoxLayout()
        recovery_row.addWidget(QLabel("E-mail odzyskiwania admina:"))
        self.in_admin_recovery_email = QLineEdit()
        self.in_admin_recovery_email.setPlaceholderText("admin@twojadomena.pl")
        self.btn_save_recovery_email = QPushButton("Zapisz e-mail")
        self.btn_save_recovery_email.setProperty("role", "secondary")
        recovery_row.addWidget(self.in_admin_recovery_email, 1)
        recovery_row.addWidget(self.btn_save_recovery_email)
        users_l.addLayout(recovery_row)

        main_grid.addWidget(backup_card, 0, 0)
        main_grid.addWidget(users_card, 0, 1)
        main_grid.setColumnStretch(0, 1)
        main_grid.setColumnStretch(1, 1)

        root.addLayout(main_grid, 1)

        self.btn_refresh.clicked.connect(self.refresh_backups)
        self.btn_create.clicked.connect(self.create_backup)
        self.btn_restore.clicked.connect(self.restore_selected_backup)
        self.btn_apply_interval.clicked.connect(self.apply_interval)
        self.btn_users_refresh.clicked.connect(self.refresh_users)
        self.btn_user_add.clicked.connect(self.add_user)
        self.btn_user_save.clicked.connect(self.save_selected_user_role_and_permissions)
        self.btn_save_recovery_email.clicked.connect(self.save_admin_recovery_email)
        self.lst_users.currentRowChanged.connect(self.refresh_permission_checks)

        self._sync_interval_combo()
        self.refresh_backups()
        self.refresh_users()
        self._load_admin_recovery_email()
        self._apply_permissions()

    def _load_admin_recovery_email(self) -> None:
        try:
            self.in_admin_recovery_email.setText(self.svc.get_admin_recovery_email())
        except Exception:
            self.in_admin_recovery_email.setText("")

    def _apply_permissions(self) -> None:
        can_backup = bool(self.svc.has_permission("backup.manage"))
        for btn in (self.btn_refresh, self.btn_create, self.btn_restore, self.btn_apply_interval):
            btn.setEnabled(can_backup)
        self.cmb_interval.setEnabled(can_backup)

        can_users = bool(self.svc.has_permission("users.manage"))
        for btn in (self.btn_users_refresh, self.btn_user_add, self.btn_user_save):
            btn.setEnabled(can_users)
        self.lst_users.setEnabled(can_users)
        self.cmb_user_role.setEnabled(can_users)
        self.in_admin_recovery_email.setEnabled(can_users)
        self.btn_save_recovery_email.setEnabled(can_users)
        if not can_users:
            self.btn_user_add.setToolTip("Brak uprawnienia: users.manage")

    def _sync_interval_combo(self) -> None:
        sec = int(self.svc.get_backup_interval_seconds())
        best_idx = 1
        for i in range(self.cmb_interval.count()):
            if int(self.cmb_interval.itemData(i)) == sec:
                best_idx = i
                break
        self.cmb_interval.setCurrentIndex(best_idx)

    def apply_interval(self) -> None:
        seconds = int(self.cmb_interval.currentData())
        try:
            self.svc.set_backup_interval_seconds(seconds)
        except PermissionError:
            QMessageBox.warning(self, "Backup", "Brak uprawnienia: backup.manage")
            return
        QMessageBox.information(self, "Backup", f"Ustawiono autozapis co {seconds // 60} minut.")

    def refresh_backups(self) -> None:
        self.lst_backups.clear()
        try:
            rows = self.svc.list_backups()
        except PermissionError:
            rows = []
        for name, path, size in rows:
            mb = size / (1024 * 1024)
            dt = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            self.lst_backups.addItem(f"{name} | {mb:.2f} MB | {dt} | {path}")

    def create_backup(self) -> None:
        try:
            path = self.svc.create_backup(manual=True)
        except PermissionError:
            QMessageBox.warning(self, "Backup", "Brak uprawnienia: backup.manage")
            return
        if path:
            QMessageBox.information(self, "Backup", f"Utworzono backup:\n{path}")
            self.refresh_backups()
        else:
            QMessageBox.warning(self, "Backup", "Nie udało się utworzyć backupu.")

    def restore_selected_backup(self) -> None:
        item = self.lst_backups.currentItem()
        if not item:
            QMessageBox.information(self, "Backup", "Wybierz backup z listy.")
            return

        path = item.text().split(" | ")[-1]
        password = QLineEdit(self)
        password.setEchoMode(QLineEdit.Password)
        password.setPlaceholderText("Hasło ZIP backupu")

        q = QMessageBox(self)
        q.setWindowTitle("Potwierdź przywracanie")
        q.setText("Podaj hasło ZIP backupu (jeśli backup był szyfrowany):")
        q.layout().addWidget(password, 1, 1)
        q.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if q.exec() != QMessageBox.Ok:
            return

        entered_password = password.text().strip() or get_configured_backup_password()
        try:
            ok = self.svc.restore_backup(path, password=entered_password)
        except PermissionError:
            QMessageBox.warning(self, "Backup", "Brak uprawnienia: backup.manage")
            return
        if ok:
            QMessageBox.information(self, "Backup", "Przywrócono backup. Dla pewności uruchom aplikację ponownie.")
        else:
            QMessageBox.critical(self, "Backup", "Nie udało się przywrócić backupu (sprawdź hasło ZIP).")

    def refresh_users(self) -> None:
        self.lst_users.clear()
        self.cmb_user_role.clear()
        try:
            for role_id, role_name in self.svc.list_roles():
                self.cmb_user_role.addItem(role_name, int(role_id))
            self._users_cache = self.svc.list_users()
        except PermissionError:
            self._users_cache = []
            return
        for user_id, login, role_name, is_active in self._users_cache:
            status = "AKTYWNY" if int(is_active) == 1 else "ZABLOKOWANY"
            self.lst_users.addItem(f"{login} | {role_name} | {status} | id={user_id}")
        self.refresh_permission_checks()

    def refresh_permission_checks(self) -> None:
        while self.perm_grid.count():
            item = self.perm_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        current = self.lst_users.currentRow()
        if current < 0 or current >= len(getattr(self, "_users_cache", [])):
            return

        _, _, role_name, _ = self._users_cache[current]
        try:
            roles = {name: rid for rid, name in self.svc.list_roles()}
        except PermissionError:
            return
        role_id = roles.get(role_name)
        if not role_id:
            return
        ridx = self.cmb_user_role.findData(int(role_id))
        if ridx >= 0:
            self.cmb_user_role.setCurrentIndex(ridx)
        selected = set(self.svc.role_permission_keys(int(role_id)))

        try:
            perms = self.svc.list_permissions()
        except PermissionError:
            return
        for idx, (_, key, label) in enumerate(perms):
            chk = QCheckBox(label)
            chk.setChecked(key in selected)
            chk.setEnabled(bool(self.svc.has_permission("users.manage")))
            chk.setProperty("perm_key", key)
            self.perm_grid.addWidget(chk, idx // 2, idx % 2)

    def add_user(self) -> None:
        d = AddUserDialog(self.svc, self)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        admin_password, login, password, role_id = d.get_data()
        if not MAIN_ADMIN_PASSWORD:
            QMessageBox.warning(self, "Użytkownicy", "Brak skonfigurowanego MAGAZYN_ADMIN_MASTER_PASSWORD.")
            return
        if admin_password != MAIN_ADMIN_PASSWORD:
            QMessageBox.warning(self, "Użytkownicy", "Nieprawidłowe hasło główne.")
            return
        if not login or not password:
            QMessageBox.warning(self, "Użytkownicy", "Login i hasło są wymagane.")
            return
        try:
            self.svc.create_user(login, password, role_id)
            QMessageBox.information(self, "Użytkownicy", "Dodano użytkownika.")
            self.refresh_users()
        except Exception as e:
            QMessageBox.critical(self, "Użytkownicy", f"Nie udało się dodać użytkownika:\n{e}")

    def save_selected_user_role_and_permissions(self) -> None:
        current = self.lst_users.currentRow()
        if current < 0 or current >= len(getattr(self, "_users_cache", [])):
            QMessageBox.information(self, "Użytkownicy", "Wybierz użytkownika z listy.")
            return
        user_id = int(self._users_cache[current][0])
        role_id = int(self.cmb_user_role.currentData())
        selected_keys = []
        for i in range(self.perm_grid.count()):
            w = self.perm_grid.itemAt(i).widget()
            if isinstance(w, QCheckBox) and w.isChecked():
                selected_keys.append(str(w.property("perm_key") or ""))

        p = QLineEdit(self)
        p.setEchoMode(QLineEdit.Password)
        p.setPlaceholderText("Hasło główne")
        q = QMessageBox(self)
        q.setWindowTitle("Potwierdź zmiany")
        q.setText("Podaj hasło główne, aby zapisać rolę i uprawnienia:")
        q.layout().addWidget(p, 1, 1)
        q.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if q.exec() != QMessageBox.Ok:
            return
        if not MAIN_ADMIN_PASSWORD:
            QMessageBox.warning(self, "Użytkownicy", "Brak skonfigurowanego MAGAZYN_ADMIN_MASTER_PASSWORD.")
            return
        if p.text().strip() != MAIN_ADMIN_PASSWORD:
            QMessageBox.warning(self, "Użytkownicy", "Nieprawidłowe hasło główne.")
            return

        self.svc.set_user_role(user_id, role_id)
        self.svc.update_role_permissions(role_id, selected_keys)
        QMessageBox.information(self, "Użytkownicy", "Zapisano rolę i uprawnienia.")
        self.refresh_users()

    def save_admin_recovery_email(self) -> None:
        email = self.in_admin_recovery_email.text().strip()
        if "@" not in email or "." not in email:
            QMessageBox.warning(self, "Użytkownicy", "Podaj poprawny adres e-mail.")
            return
        try:
            self.svc.set_admin_recovery_email(email)
            QMessageBox.information(self, "Użytkownicy", "Zapisano e-mail odzyskiwania administratora.")
            self._load_admin_recovery_email()
        except PermissionError:
            QMessageBox.warning(self, "Użytkownicy", "Brak uprawnienia: users.manage")
        except Exception as e:
            QMessageBox.critical(self, "Użytkownicy", str(e))
