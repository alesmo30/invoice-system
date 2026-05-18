"""Espacio para fixtures compartidos de pytest."""

from pathlib import Path

from dotenv import load_dotenv

# Igual que al correr scripts con dotenv desde la raíz del repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")
