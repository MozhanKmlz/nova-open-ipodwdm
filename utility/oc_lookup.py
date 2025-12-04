from pathlib import Path
import re
import subprocess
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Path to your cloned OpenConfig repo (with tags), e.g. ~/nova-open-ipodwdm/openconfig-public
OPENCONFIG_REPO = Path(__file__).parent.parent / "openconfig-public"
# File we care about inside that repo
OC_PLATFORM_YANG = "release/models/platform/openconfig-platform.yang"

REV_RE = re.compile(r'revision\s+"(\d{4}-\d{2}-\d{2})"\s*{', re.DOTALL)
OC_EXT_VER_RE = re.compile(r'oc-ext:openconfig-version\s+"([^"]+)"')
REF_VER_RE = re.compile(r'reference\s+"([^"]+)"')

class OpenConfigLookup:
    def __init__(self):
        # Build both maps at init:
        self._rev_map = {"openconfig-platform": {}}
        self._version_tags = {}

        built_from_tags = self._build_from_tags()
        if not built_from_tags:
            self._build_from_head_fallback()

        logger.debug("[Lookup] rev→version map: %s", self._rev_map["openconfig-platform"])
        logger.debug("[Lookup] version→tag map: %s", self._version_tags)

    def get_version_by_revision(self, module: str, revision_date: str):
        """Returns OpenConfig version for a module + revision date"""
        return self._rev_map.get(module, {}).get(revision_date)

    def get_latest_version(self, module: str):
        """Returns the latest known version for this module by max revision date"""
        rev_map = self._rev_map.get(module, {})
        if not rev_map:
            return None
        latest_rev = max(rev_map.keys())  # lexical works for YYYY-MM-DD
        return rev_map[latest_rev]

    def get_tag_for_version(self, version: str):
        """Returns Git tag corresponding to an OpenConfig version (if known)"""
        return self._version_tags.get(version)

    # ---- Builders -----------------------------------------------------------

    def _build_from_tags(self) -> bool:
        """
        Build:
          - revision→version for openconfig-platform
          - version→tag
        by iterating over OpenConfig repo tags and parsing the file at each tag
        """
        if not OPENCONFIG_REPO.exists():
            logger.warning("[Lookup] OpenConfig repo not found at %s", OPENCONFIG_REPO)
            return False

        try:
            subprocess.run(["git", "fetch", "--tags"], check=False, cwd=OPENCONFIG_REPO)
            res = subprocess.run(
                ["git", "tag", "-l", "v*.*.*", "--sort=v:refname"],
                cwd=OPENCONFIG_REPO, capture_output=True, text=True, check=True
            )
            tags = [t for t in res.stdout.strip().splitlines() if t]
            if not tags:
                logger.warning("[Lookup] No tags found in %s", OPENCONFIG_REPO)
                return False

            for tag in tags:
                text = self._git_show(OPENCONFIG_REPO, f"{tag}:{OC_PLATFORM_YANG}")
                if not text:
                    # Some older tags or different layouts might not have this file
                    continue

                # Extracts version (oc-ext is authoritative at this tag)
                ver = self._extract_oc_version(text)
                if not ver:
                    # Fallback to 'reference "X.Y.Z"' if present
                    ver = self._extract_ref_version(text)

                # Extracts the *top* (most recent) revision date in that file at this tag
                rev = self._extract_top_revision(text)

                if ver and rev:
                    # Map revision→version
                    self._rev_map["openconfig-platform"][rev] = ver
                    # Map version→tag (first match wins)
                    self._version_tags.setdefault(ver, tag)

            return bool(self._rev_map["openconfig-platform"])
        except Exception as e:
            logger.warning("[Lookup] Failed building from tags: %s", e)
            return False

    def _build_from_head_fallback(self):
        """
        Fallback: parses the file at HEAD (current checkout) just to get
        some revision→version mapping if tags are unavailable
        """
        path = OPENCONFIG_REPO / OC_PLATFORM_YANG
        if not path.exists():
            logger.warning("[Lookup] Fallback file not found: %s", path)
            return

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning("[Lookup] Could not read fallback file %s: %s", path, e)
            return

        # Gets a single version value (oc-ext preferred)
        ver = self._extract_oc_version(text) or self._extract_ref_version(text)
        if not ver:
            logger.warning("[Lookup] No version found in fallback HEAD file")
            return

        # Maps *all* revisions present in the file to that version (best-effort)
        for rev in REV_RE.findall(text):
            self._rev_map["openconfig-platform"][rev] = ver

    # ---- Helpers ------------------------------------------------------------

    def _git_show(self, repo: Path, obj_path: str) -> Optional[str]:
        try:
            r = subprocess.run(
                ["git", "show", obj_path],
                cwd=repo, capture_output=True, text=True, check=True
            )
            return r.stdout
        except subprocess.CalledProcessError:
            return None

    def _extract_oc_version(self, text: str) -> Optional[str]:
        m = OC_EXT_VER_RE.search(text)
        return m.group(1) if m else None

    def _extract_ref_version(self, text: str) -> Optional[str]:
        """
        If the reference contains extra words, keep only the X.Y.Z-like token.
        """
        m = REF_VER_RE.search(text)
        if not m:
            return None
        ref = m.group(1)
        sv = re.search(r"\b\d+\.\d+\.\d+\b", ref)
        return sv.group(0) if sv else ref

    def _extract_top_revision(self, text: str) -> Optional[str]:
        """
        Returns the first (topmost) revision date in the file text, which
        corresponds to the most recent revision as of that tag
        """
        m = REV_RE.search(text)
        return m.group(1) if m else None
