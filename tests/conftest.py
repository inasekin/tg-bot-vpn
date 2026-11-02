import os

import pytest

# Модули в src/ при импорте читают окружение и создают data/bot.db,
# поэтому перед каждым тестом чистим WG_*-переменные.


@pytest.fixture(autouse=True)
def clean_wg_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("WG_SERVER"):
            monkeypatch.delenv(name, raising=False)
