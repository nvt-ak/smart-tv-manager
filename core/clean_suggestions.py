"""Smart Clean: classify packages for disable suggestions (local heuristics)."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

import paths

TIER_SORT_ORDER = {"recommend": 0, "review": 1, "skip": 2, "blocked": 3}


def sort_suggestions_by_tier(items: List[dict]) -> List[dict]:
    return sorted(items, key=lambda x: (TIER_SORT_ORDER.get(x.get("tier"), 9), x.get("package") or ""))


class CleanSuggestionEngine:
    def __init__(self) -> None:
        self._rules = self._load_rules()

    def _load_rules(self) -> dict:
        path = os.path.join(paths.app_root(), "data", "clean_heuristics.json")
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _mfr_rules(self, manufacturer: str) -> dict:
        by = self._rules.get("by_manufacturer") or {}
        key = (manufacturer or "").strip().upper()
        for name, rules in by.items():
            if name.upper() == key:
                return rules if isinstance(rules, dict) else {}
        return by.get("default") or {}

    def _match_substrings(self, package: str, entries: list) -> str | None:
        pkg = package.lower()
        for entry in entries or []:
            if isinstance(entry, str):
                if entry.lower() in pkg:
                    return "Khớp pattern OEM / bloat."
            elif isinstance(entry, dict):
                m = (entry.get("match") or "").lower()
                if m and m in pkg:
                    return entry.get("reason") or "Khớp danh sách gợi ý."
        return None

    def _classify_pkg(self, package: str, manufacturer: str) -> Tuple[str, str]:
        pkg = package.lower()
        mfr = self._mfr_rules(manufacturer)

        for keep in self._rules.get("keep_substrings") or []:
            if keep.lower() in pkg:
                return "skip", "Giữ theo danh sách an toàn (launcher / hệ thống / dịch vụ chính)."

        for exact in mfr.get("recommend_exact") or []:
            if pkg == exact.lower():
                return "recommend", "Gợi ý theo hãng TV (danh sách nội bộ)."

        for exact in self._rules.get("recommend_exact") or []:
            if pkg == exact.lower():
                return "recommend", "App bloat / không cần thiết trên nhiều TV."

        reason = self._match_substrings(package, self._rules.get("recommend_substrings"))
        if reason:
            return "recommend", reason

        for exact in mfr.get("review_exact") or []:
            if pkg == exact.lower():
                return "review", "Cần xem xét theo model TV."

        reason = self._match_substrings(package, self._rules.get("review_substrings"))
        if reason:
            return "review", reason

        return "skip", "Không nằm trong gợi ý dọn dẹp — giữ nguyên."

    def _is_kept(self, package: str) -> bool:
        pkg = package.lower()
        return any(k.lower() in pkg for k in self._rules.get("keep_substrings") or [])

    def analyze(
        self,
        apps: List[dict],
        manufacturer: str = "",
        profile_notes: Dict[str, str] | None = None,
        profile_label: str = "",
        profile_quality: str = "",
    ) -> List[dict]:
        """Classify packages.

        profile_notes: package -> note from a matched Gathin per-model profile. Those packages
        become suggestions only: never pre-selected, never one-click, and the safe-list and
        can_disable checks still win.
        """
        out: List[dict] = []
        for app in apps:
            pkg = app.get("package") or ""
            if not pkg:
                continue
            enabled = app.get("enabled", True) and app.get("type") != "disabled"
            base = {
                "package": pkg,
                "type": app.get("type"),
                "enabled": enabled,
                "is_home": app.get("is_home"),
                "can_disable": app.get("can_disable"),
                "source": "local",
            }
            if not enabled:
                out.append(
                    {
                        **base,
                        "tier": "skip",
                        "reason": "Đã vô hiệu hóa.",
                        "selected": False,
                    }
                )
                continue
            if not app.get("can_disable"):
                out.append(
                    {
                        **base,
                        "tier": "blocked",
                        "reason": app.get("disable_reason") or "Không được phép vô hiệu hóa.",
                        "selected": False,
                    }
                )
                continue
            tier, reason = self._classify_pkg(pkg, manufacturer)
            row = {**base, "tier": tier, "reason": reason, "selected": tier == "recommend"}
            if profile_notes and pkg in profile_notes and not self._is_kept(pkg):
                note = profile_notes[pkg]
                tag = f"profile Gathin «{profile_label}»"
                if tier == "recommend":
                    row["reason"] = f"{reason} Có trong {tag}."
                else:
                    row["tier"] = "recommend" if profile_quality == "exact" else "review"
                    row["reason"] = f"Gợi ý theo {tag}" + (f": {note}" if note else ".")
                    row["selected"] = False
                    row["source"] = "profile"
                    row["profile_match"] = profile_quality
            out.append(row)
        return sort_suggestions_by_tier(out)

    def merge_ai(self, local: List[dict], ai_rows: List[dict]) -> List[dict]:
        by_pkg: Dict[str, dict] = {s["package"]: dict(s) for s in local}
        allowed = {"recommend", "review", "skip"}
        for row in ai_rows or []:
            pkg = (row.get("package") or "").strip()
            tier = (row.get("tier") or "").strip().lower()
            if not pkg or tier not in allowed:
                continue
            cur = by_pkg.get(pkg)
            if not cur or cur.get("tier") == "blocked" or not cur.get("can_disable"):
                continue
            if not cur.get("enabled"):
                continue
            if cur.get("source") == "profile":
                continue  # per-model suggestion stays as the profile gave it (never pre-selected)
            cur["tier"] = tier
            cur["reason"] = (row.get("reason") or cur.get("reason") or "Gợi ý AI.").strip()
            if row.get("category"):
                cur["ai_category"] = row.get("category")
            if row.get("confidence"):
                cur["ai_confidence"] = row.get("confidence")
            cur["source"] = "ai"
            cur["selected"] = tier == "recommend"
        return sort_suggestions_by_tier(list(by_pkg.values()))
