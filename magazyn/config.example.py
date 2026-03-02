"""Przykładowa konfiguracja środowiska (bez sekretów).

Skopiuj wartości do zmiennych środowiskowych MAGAZYN_*.
"""

# Backup
MAGAZYN_AUTO_BACKUP_INTERVAL = "1800"
MAGAZYN_BACKUP_ZIP_PASSWORD = ""

# Konto administratora (login startowy bez hasła; hasło ustawiane w UI przy pierwszym logowaniu)
MAGAZYN_MAIN_ADMIN_LOGIN = "admin"
MAGAZYN_MAIN_ADMIN_PASSWORD = ""

# SMTP (odzyskiwanie hasła)
MAGAZYN_SMTP_HOST = ""
MAGAZYN_SMTP_PORT = "587"
MAGAZYN_SMTP_USERNAME = ""
MAGAZYN_SMTP_PASSWORD = ""
MAGAZYN_SMTP_USE_TLS = "1"
MAGAZYN_SMTP_FROM = ""
MAGAZYN_RESET_CODE_TTL_MINUTES = "15"
