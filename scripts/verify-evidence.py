#!/usr/bin/env python3
"""根拠台帳 (analysis/factors.yaml) を、ピン留めした解析対象の実ファイルと突き合わせて検証する。

この repo の主張はすべて「該当ファイルの該当行にこの文字列が実在する」まで固定されている。
1 件でも不一致・欠落があれば exit 1（fail-closed）。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "source.lock"
LEDGER = ROOT / "analysis" / "factors.yaml"
VENDOR = ROOT / "vendor" / "x-algorithm"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^F\d{3}$")

STAGES = {"source", "hydrator", "filter", "scorer", "selector", "visibility", "infra"}
# YAML 1.1 が yes/no を真偽値に解釈するため、その 2 語は意図的に避けている
CONTROLLABLE = {"direct", "indirect", "none"}
DIRECTIONS = {"boost", "suppress", "gate", "neutral"}
CONFIDENCE = {"high", "medium", "low"}

REQUIRED = (
    "id",
    "name",
    "stage",
    "author_controllable",
    "direction",
    "summary",
    "evidence",
    "confidence",
)


class Failures(list):
    def add(self, where: str, msg: str) -> None:
        self.append(f"{where}: {msg}")


def read_pinned_commit(fail: Failures) -> str | None:
    if not LOCK.is_file():
        fail.add("source.lock", "が無い")
        return None
    commit = None
    for raw in LOCK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "COMMIT":
            commit = value.strip()
    if commit is None or not SHA_RE.match(commit):
        fail.add("source.lock", f"COMMIT が 40 桁の SHA ではない: {commit!r}")
        return None
    return commit


def check_vendor(commit: str, fail: Failures) -> bool:
    if not (VENDOR / ".git").is_dir():
        fail.add("vendor", f"{VENDOR.relative_to(ROOT)} が無い。`make fetch` を先に実行する")
        return False
    try:
        head = subprocess.run(
            ["git", "-C", str(VENDOR), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        fail.add("vendor", f"HEAD を読めない: {exc}")
        return False
    if head != commit:
        fail.add("vendor", f"HEAD がピン留めと違う: {head} != {commit}。`make fetch` で取り直す")
        return False
    return True


def load_ledger(fail: Failures) -> dict | None:
    if not LEDGER.is_file():
        fail.add("factors.yaml", "が無い")
        return None
    try:
        data = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        fail.add("factors.yaml", f"パースできない: {exc}")
        return None
    if not isinstance(data, dict):
        fail.add("factors.yaml", "トップレベルがマッピングではない")
        return None
    return data


def read_lines(path: Path, cache: dict[Path, list[str]]) -> list[str]:
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return cache[path]


def check_evidence(where: str, ev, cache, fail: Failures) -> None:
    if not isinstance(ev, dict):
        fail.add(where, "evidence の要素がマッピングではない")
        return
    for key in ("path", "line", "snippet"):
        if key not in ev:
            fail.add(where, f"evidence に {key} が無い")
            return

    rel = str(ev["path"])
    if rel.startswith("/") or ".." in Path(rel).parts:
        fail.add(where, f"path は解析対象ルートからの相対パスにする: {rel}")
        return

    target = VENDOR / rel
    if not target.is_file():
        fail.add(where, f"ファイルが存在しない: {rel}")
        return

    start = ev["line"]
    end = ev.get("line_end", start)
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        fail.add(where, f"line/line_end が不正: {start}/{end}")
        return

    lines = read_lines(target, cache)
    if end > len(lines):
        fail.add(where, f"{rel} は {len(lines)} 行しかない (指定: {start}-{end})")
        return

    snippet = str(ev["snippet"]).strip()
    if not snippet:
        fail.add(where, "snippet が空")
        return

    window = "\n".join(lines[start - 1 : end])
    if snippet not in window:
        actual = lines[start - 1].strip()
        fail.add(
            where,
            f"{rel}:{start}-{end} に snippet が無い\n"
            f"      期待: {snippet!r}\n"
            f"      実際({start} 行目): {actual!r}",
        )


def check_factor(factor, seen_ids: set[str], cache, fail: Failures) -> None:
    if not isinstance(factor, dict):
        fail.add("factors", "要素がマッピングではない")
        return

    fid = factor.get("id", "<no id>")
    where = f"factor {fid}"

    missing = [k for k in REQUIRED if k not in factor]
    if missing:
        fail.add(where, f"必須キーが無い: {', '.join(missing)}")
        return

    if not ID_RE.match(str(fid)):
        fail.add(where, "id は F001 形式にする")
    if fid in seen_ids:
        fail.add(where, "id が重複している")
    seen_ids.add(fid)

    for key, allowed in (
        ("stage", STAGES),
        ("author_controllable", CONTROLLABLE),
        ("direction", DIRECTIONS),
        ("confidence", CONFIDENCE),
    ):
        if factor[key] not in allowed:
            fail.add(where, f"{key} が不正: {factor[key]!r} (許容: {sorted(allowed)})")

    evidence = factor["evidence"]
    if not isinstance(evidence, list) or not evidence:
        fail.add(where, "evidence が空。根拠を持たない要因は台帳に載せない")
        return

    for i, ev in enumerate(evidence):
        check_evidence(f"{where} evidence[{i}]", ev, cache, fail)


def print_stats(factors: list) -> None:
    print(f"要因: {len(factors)} 件")
    for key in ("stage", "author_controllable", "direction", "confidence"):
        counts = Counter(f.get(key, "<none>") for f in factors if isinstance(f, dict))
        breakdown = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"  {key:20} {breakdown}")
    total_ev = sum(len(f.get("evidence", [])) for f in factors if isinstance(f, dict))
    print(f"  {'evidence':20} {total_ev} 件")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", action="store_true", help="検証に加えて集計を出す")
    args = parser.parse_args()

    fail = Failures()

    commit = read_pinned_commit(fail)
    vendor_ok = check_vendor(commit, fail) if commit else False
    ledger = load_ledger(fail)

    factors: list = []
    if ledger is not None:
        ref = ledger.get("source_ref")
        if commit and ref != commit:
            fail.add("factors.yaml", f"source_ref が source.lock と違う: {ref} != {commit}")
        raw = ledger.get("factors")
        if not isinstance(raw, list) or not raw:
            fail.add("factors.yaml", "factors が空のリスト")
        else:
            factors = raw
            if vendor_ok:
                cache: dict[Path, list[str]] = {}
                seen: set[str] = set()
                for factor in factors:
                    check_factor(factor, seen, cache, fail)
            else:
                fail.add("verify", "vendor が使えないため evidence を照合できなかった")

    if fail:
        print(f"NG: {len(fail)} 件", file=sys.stderr)
        for msg in fail:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    total_ev = sum(len(f.get("evidence", [])) for f in factors)
    print(f"OK: 要因 {len(factors)} 件 / evidence {total_ev} 件 すべて {commit[:12]} の実ファイルと一致")
    if args.stats:
        print()
        print_stats(factors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
