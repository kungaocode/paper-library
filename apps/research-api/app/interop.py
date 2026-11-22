from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from types import ModuleType


class InteropError(RuntimeError):
    pass


_LOADED: dict[str, ModuleType] = {}

# Deep analysis extracts several PDFs in worker threads at once. CPython puts a
# module into sys.modules *before* running its body, so an unsynchronized cache
# check can hand out a half-initialized module and every concurrent caller
# fails with AttributeError. One lock serializes the whole load.
_LOCK = threading.Lock()

# The reading platform's package is also called `app`, so a normal import would
# resolve to *this* package. Mounting its directory under a private package name
# keeps the two namespaces apart, and still lets their own relative imports work.
# Their `config` module is deliberately excluded: importing it would run
# load_dotenv() against apps/api/.env and leak the reading platform's model
# credentials into this process' environment.
_ALIAS_PACKAGE = "paper_atlas"

# Modules that are safe to reuse: pure data/parsing, no FastAPI app, no DB writes,
# and no import of their `config` (which would load apps/api/.env).
SAFE_MODULES = frozenset({"categories", "pdf_utils"})


def _ensure_package(api_root: Path) -> None:
    existing = sys.modules.get(_ALIAS_PACKAGE)
    if existing is not None:
        return
    source_dir = api_root / "app"
    if not source_dir.is_dir():
        raise InteropError(f"未找到阅读平台代码目录：{source_dir}")
    package = ModuleType(_ALIAS_PACKAGE)
    package.__path__ = [str(source_dir)]  # type: ignore[attr-defined]
    sys.modules[_ALIAS_PACKAGE] = package


def load_reading_platform_module(api_root: Path, name: str) -> ModuleType:
    if name not in SAFE_MODULES:
        raise InteropError(f"拒绝加载阅读平台模块：{name}（不在允许清单内）。")

    qualified = f"{_ALIAS_PACKAGE}.{name}"
    with _LOCK:
        cached = _LOADED.get(qualified) or sys.modules.get(qualified)
        if cached is not None:
            _LOADED[qualified] = cached
            return cached

        _ensure_package(api_root)
        try:
            module = importlib.import_module(qualified)
        except Exception as error:  # noqa: BLE001 - surfaced as a readable failure
            raise InteropError(f"加载 {name} 失败：{error}") from error

        _LOADED[qualified] = module
        return module


def clear_cache() -> None:
    with _LOCK:
        for qualified in list(_LOADED):
            sys.modules.pop(qualified, None)
        sys.modules.pop(_ALIAS_PACKAGE, None)
        _LOADED.clear()
