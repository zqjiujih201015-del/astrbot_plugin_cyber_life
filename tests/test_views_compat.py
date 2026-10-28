"""Guards the AstrBot 4.24 - 4.29 plugin view compatibility contract.

AstrBot 4.24.2 introduced plugin views but scanned only ``pages/`` and injected
only ``window.AstrBotPluginPage``. AstrBot 4.29 renamed the feature to Views:
it scans ``views/`` first and keeps ``pages/`` as an alias, and it injects
``window.AstrBotPluginView`` while keeping the old global as an alias.

A plugin that ships only one directory name, or that hard-codes one bridge
name, therefore breaks on the other half of the supported range. These tests
are pure filesystem assertions so they run without AstrBot installed.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VIEW_DIR_NAMES = ("views", "pages")
VIEW_NAME = "settings"
ENTRY_FILE = "index.html"
BRIDGE_NAMES = ("AstrBotPluginPage", "AstrBotPluginView")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ViewDirectoryLayoutTest(unittest.TestCase):
    def test_both_view_directory_names_exist(self) -> None:
        for dir_name in VIEW_DIR_NAMES:
            with self.subTest(dir_name=dir_name):
                entry = ROOT / dir_name / VIEW_NAME / ENTRY_FILE
                self.assertTrue(entry.is_file(), f"missing view entry: {entry}")

    def test_view_assets_are_present(self) -> None:
        for dir_name in VIEW_DIR_NAMES:
            page_root = ROOT / dir_name / VIEW_NAME
            for asset in ("index.html", "app.js", "style.css"):
                with self.subTest(dir_name=dir_name, asset=asset):
                    self.assertTrue((page_root / asset).is_file())

    def test_no_extra_explorable_entries(self) -> None:
        """AstrBot treats every sub-directory with index.html as a view."""
        for dir_name in VIEW_DIR_NAMES:
            root = ROOT / dir_name
            stray = [
                child.name
                for child in root.iterdir()
                if child.is_dir() and child.name != VIEW_NAME and (child / ENTRY_FILE).is_file()
            ]
            with self.subTest(dir_name=dir_name):
                self.assertEqual(stray, [], f"unexpected extra views: {stray}")


class ViewCopiesStayInSyncTest(unittest.TestCase):
    """views/ and pages/ must stay byte-identical, or the two hosts disagree."""

    def test_view_copies_are_identical(self) -> None:
        for asset in ("index.html", "app.js", "style.css"):
            with self.subTest(asset=asset):
                first = (ROOT / VIEW_DIR_NAMES[0] / VIEW_NAME / asset).read_bytes()
                second = (ROOT / VIEW_DIR_NAMES[1] / VIEW_NAME / asset).read_bytes()
                self.assertEqual(
                    first,
                    second,
                    f"{asset} differs between views/ and pages/; re-sync the two copies",
                )


class BridgeBootstrapTest(unittest.TestCase):
    def test_bootstrap_accepts_both_bridge_globals(self) -> None:
        source = _read(ROOT / "views" / VIEW_NAME / "app.js")
        for name in BRIDGE_NAMES:
            with self.subTest(bridge=name):
                self.assertIn(
                    f"window.{name}",
                    source,
                    f"app.js never reads window.{name}",
                )

    def test_bootstrap_has_same_origin_fallback(self) -> None:
        source = _read(ROOT / "views" / VIEW_NAME / "app.js")
        self.assertIn("/api/plug/", source)
        self.assertRegex(source, r"ready:|ready\s*[:=]")

    def test_relative_asset_urls_only(self) -> None:
        """4.29 serves assets through path tokens; hard-coded URLs break it."""
        html = _read(ROOT / "views" / VIEW_NAME / "index.html")
        refs = re.findall(r'(?:src|href)="([^"]+)"', html)
        self.assertTrue(refs, "index.html references no assets")
        for ref in refs:
            with self.subTest(ref=ref):
                self.assertFalse(ref.startswith(("http://", "https://")), ref)
                self.assertFalse(ref.startswith("/"), ref)
                self.assertNotIn("asset_token", ref)

    def test_no_hard_coded_asset_token(self) -> None:
        for dir_name in VIEW_DIR_NAMES:
            page_root = ROOT / dir_name / VIEW_NAME
            for asset in ("index.html", "app.js"):
                with self.subTest(dir_name=dir_name, asset=asset):
                    self.assertNotIn("asset_token", _read(page_root / asset))


class ViewI18nTest(unittest.TestCase):
    NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

    def test_locale_files_declare_view_metadata(self) -> None:
        i18n_dir = ROOT / ".astrbot-plugin" / "i18n"
        locales = sorted(i18n_dir.glob("*.json"))
        self.assertTrue(locales, "no locale files found")
        for locale in locales:
            with self.subTest(locale=locale.name):
                data = json.loads(_read(locale))
                view_name = data.get("views", {}).get(VIEW_NAME)
                self.assertIsInstance(
                    view_name,
                    dict,
                    f"{locale.name} is missing views.{VIEW_NAME}; "
                    "AstrBot 4.29 reads views.<name>.title first",
                )
                alias = data.get("pages", {}).get(VIEW_NAME)
                self.assertIsInstance(
                    alias,
                    dict,
                    f"{locale.name} is missing pages.{VIEW_NAME}; "
                    "AstrBot 4.24 - 4.28 read pages.<name>.title",
                )

    def test_view_titles_agree_between_keys(self) -> None:
        i18n_dir = ROOT / ".astrbot-plugin" / "i18n"
        for locale in sorted(i18n_dir.glob("*.json")):
            with self.subTest(locale=locale.name):
                data = json.loads(_read(locale))
                self.assertEqual(
                    data["views"][VIEW_NAME].get("title"),
                    data["pages"][VIEW_NAME].get("title"),
                )


class MetadataTest(unittest.TestCase):
    """The declared floor is the maintainer's call; these tests only record it.

    ``astrbot_version`` is intentionally left as ``>=4.16`` in this change.
    Plugin views do not exist before 4.24.2, so the real floor is higher than
    what the metadata claims; that mismatch is reported in the pull request
    description instead of being changed here.
    """

    def test_metadata_declares_a_parseable_version_floor(self) -> None:
        text = _read(ROOT / "metadata.yaml")
        match = re.search(r'^astrbot_version:\s*"?([^"\n]+)"?', text, re.MULTILINE)
        self.assertIsNotNone(match, "metadata.yaml has no astrbot_version")
        spec = match.group(1).strip()
        self.assertRegex(spec, r">=\s*\d+\.\d+", f"unparseable spec: {spec!r}")

    def test_actual_view_floor_is_above_declared_floor(self) -> None:
        """Documents the known mismatch so it cannot be forgotten silently."""
        text = _read(ROOT / "metadata.yaml")
        spec = re.search(r'^astrbot_version:\s*"?([^"\n]+)"?', text, re.MULTILINE)
        self.assertIsNotNone(spec)
        floor = re.search(r">=\s*(\d+)\.(\d+)(?:\.(\d+))?", spec.group(1))
        self.assertIsNotNone(floor)
        declared = tuple(int(part or 0) for part in floor.groups())
        self.assertLess(
            declared,
            (4, 24, 2),
            "if the metadata floor was raised to >=4.24.2, drop this test and "
            "the matching note in the README",
        )


if __name__ == "__main__":
    unittest.main()
