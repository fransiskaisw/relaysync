"""Menghasilkan saran TEAM_ID unik dengan sufiks acak 4 karakter."""
from __future__ import annotations

from relaysync.settings.identity import suggest_team_id


def main() -> None:
    suggested = suggest_team_id()
    print(f"Saran identitas kelompok unik: {suggested}")
    print(f"Salin baris berikut ke berkas .env Anda:\nTEAM_ID={suggested}")


if __name__ == "__main__":
    main()
