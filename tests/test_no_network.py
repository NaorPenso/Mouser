"""Fork policy guards: the application must never talk to the network.

This fork of Mouser removed the release check and auto-updater and must
stay that way. These tests fail the build if network-capable code, the
update machinery, or a release pipeline is reintroduced (for example by an
upstream merge), and they keep dependency pinning honest.
"""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Only the single-instance guard may use QtNetwork, and only for a local
# (same user, same machine) socket. Nothing else from that module is allowed.
ALLOWED_QTNETWORK = {"QLocalServer", "QLocalSocket", "QAbstractSocket"}

# Modules that open sockets or launch a browser. ``urllib.parse`` is pure
# string handling and is allowed; every other ``urllib`` submodule is not.
FORBIDDEN_MODULES = {
    "urllib.request", "urllib.error", "urllib.robotparser",
    "requests", "httpx", "aiohttp", "http.client", "http.server",
    "socket", "ssl", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib",
    "websocket", "websockets", "xmlrpc", "webbrowser",
}
FORBIDDEN_QT_NAMES = {
    "QNetworkAccessManager", "QNetworkRequest", "QTcpSocket", "QTcpServer",
    "QUdpSocket", "QSslSocket", "QDesktopServices",
}

APP_SOURCES = (
    [ROOT / "main_qml.py", ROOT / "build_support.py"]
    + sorted((ROOT / "core").glob("*.py"))
    + sorted((ROOT / "ui").glob("*.py"))
)


def _imports(tree):
    """Yield (module, name) pairs for every import in the tree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                yield module, alias.name


class NoNetworkCodeTests(unittest.TestCase):
    def test_application_sources_import_no_network_modules(self):
        for path in APP_SOURCES:
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            for module, name in _imports(tree):
                full = module if name == module else f"{module}.{name}"
                with self.subTest(file=path.name, imported=full):
                    self.assertFalse(
                        module in FORBIDDEN_MODULES
                        or full in FORBIDDEN_MODULES
                        or (module == "urllib" and name != "parse"),
                        f"{path.name} imports network module {full}",
                    )
                    if module.startswith("PySide6"):
                        self.assertNotIn(name, FORBIDDEN_QT_NAMES,
                                         f"{path.name} imports {name}")
                    if module == "PySide6.QtNetwork":
                        self.assertIn(name, ALLOWED_QTNETWORK,
                                      f"{path.name} imports QtNetwork.{name}")

    def test_only_the_single_instance_guard_uses_qtnetwork(self):
        # build_support.py names QtNetwork in the PyInstaller keep-list so the
        # local-socket guard ships; it does not use the module.
        users = [
            p.name for p in APP_SOURCES
            if p.name != "build_support.py"
            and "QtNetwork" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(users, ["main_qml.py"])

    def test_no_attribute_access_to_network_apis(self):
        # Catches ``PySide6.QtGui.QDesktopServices.openUrl`` style access
        # that the import scan above would miss.
        pattern = re.compile(r"\b(QDesktopServices|webbrowser|urlopen|QNetworkAccessManager)\b")
        for path in APP_SOURCES:
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                with self.subTest(file=path.name, line=lineno):
                    self.assertIsNone(pattern.search(line), f"{path.name}:{lineno}: {line.strip()}")


class NoAutoUpdateTests(unittest.TestCase):
    def test_update_modules_are_gone(self):
        for rel in ("core/updater.py", "core/update_installer.py",
                    "tools/generate_update_manifest.py",
                    "tools/verify_update_manifest.py",
                    ".github/workflows/release.yml"):
            with self.subTest(path=rel):
                self.assertFalse((ROOT / rel).exists(), f"{rel} must not exist")

    def test_no_update_references_in_sources(self):
        pattern = re.compile(
            r"check_for_updates|update_check_state|MOUSER_ENABLE_UPDATE_INSTALL|"
            r"mouser-apply-update|releases/latest|api\.github\.com"
        )
        scan = APP_SOURCES + sorted((ROOT / "ui" / "qml").glob("*.qml"))
        for path in scan:
            text = path.read_text(encoding="utf-8")
            if path.name == "config.py":
                # The config migration pops the two removed settings keys
                # out of pre-fork user configs; that scrub must name them.
                text = "\n".join(
                    line for line in text.splitlines() if ".pop(" not in line
                )
            with self.subTest(file=path.name):
                self.assertIsNone(pattern.search(text))

    def test_default_config_has_no_update_settings(self):
        from core.config import DEFAULT_CONFIG
        settings = DEFAULT_CONFIG["settings"]
        self.assertNotIn("check_for_updates", settings)
        self.assertNotIn("update_check_state", settings)


class DependencyPinningTests(unittest.TestCase):
    def test_lock_file_pins_every_requirement_with_hashes(self):
        lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
        pinned = set(re.findall(r"^([a-z0-9_.-]+)==", lock, re.MULTILINE | re.IGNORECASE))
        self.assertIn("--hash=sha256:", lock)
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name = re.split(r"[<>=!;\s]", line, 1)[0].lower().replace("_", "-")
            with self.subTest(requirement=name):
                self.assertIn(name, pinned, f"{name} is not pinned in requirements.lock")

    def test_lock_file_is_universal(self):
        lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
        for platform in ("darwin", "linux", "win32"):
            with self.subTest(platform=platform):
                self.assertIn(f"sys_platform == '{platform}'", lock)


if __name__ == "__main__":
    unittest.main()
