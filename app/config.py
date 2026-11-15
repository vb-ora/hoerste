"""Einstellungen aus Umgebungsvariablen (HOERSTE_*)."""

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("HOERSTE_DATA_DIR", "./data")).resolve()
