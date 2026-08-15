#!/usr/bin/env python3
"""根拠台帳を、ピン留めした解析対象の実ファイルと突き合わせて検証する。

台帳は 2 本ある。
  analysis/factors.yaml — 投稿者が操作可能なランキング要因
  analysis/code.yaml    — コードそのもの（設計・実装技法）の観察

この repo の主張はすべて「該当ファイルの該当行にこの文字列が実在する」まで固定されている。
evidence の照合ロジックは 1 箇所だけに置き、両台帳に同じ厳しさで適用する。
1 件でも不一致・欠落があれば exit 1（fail-closed）。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "source.lock"
VENDOR = ROOT / "vendor" / "x-algorithm"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

CONFIDENCE = {"high", "medium", "low"}
STAGES = {"source", "hydrator", "filter", "scorer", "selector", "visibility", "infra"}
# YAML 1.1 が yes/no を真偽値に解釈するため、その 2 語は意図的に避けている
CONTROLLABLE = {"direct", "indirect", "none"}
DIRECTIONS = {"boost", "suppress", "gate", "neutral"}
KINDS = {"source", "hydrator", "filter", "scorer", "selector"}
# 誰の都合でその処理が効くか。author=投稿の作り方 / viewer=閲覧者の設定・履歴 / system=運用・実験・整合
CONTROLLED_BY = {"author", "viewer", "system"}
TOPICS = {
    "architecture",
    "abstraction",
    "algorithm",
    "concurrency",
    "error-handling",
    "testing",
    "performance",
    "language",
    "api-design",
    "code-quality",
}


@dataclass(frozen=True)
class LedgerSpec:
    """1 本の台帳の形。evidence の扱いは全台帳で共通なのでここには持たせない。"""

    filename: str
    entries_key: str
    id_prefix: str
    label: str
    required: tuple[str, ...]
    enums: dict[str, set[str]]
    stat_keys: tuple[str, ...]

    @property
    def path(self) -> Path:
        return ROOT / "analysis" / self.filename

    @property
    def id_re(self) -> re.Pattern[str]:
        return re.compile(rf"^{self.id_prefix}\d{{3}}$")


LEDGERS = (
    LedgerSpec(
        filename="factors.yaml",
        entries_key="factors",
        id_prefix="F",
        label="要因",
        required=(
            "id",
            "name",
            "stage",
            "author_controllable",
            "direction",
            "summary",
            "evidence",
            "confidence",
        ),
        enums={
            "stage": STAGES,
            "author_controllable": CONTROLLABLE,
            "direction": DIRECTIONS,
            "confidence": CONFIDENCE,
        },
        stat_keys=("stage", "author_controllable", "direction", "confidence"),
    ),
    LedgerSpec(
        filename="code.yaml",
        entries_key="observations",
        id_prefix="C",
        label="観察",
        required=(
            "id",
            "topic",
            "title",
            "summary",
            "takeaway",
            "evidence",
            "confidence",
        ),
        enums={"topic": TOPICS, "confidence": CONFIDENCE},
        stat_keys=("topic", "confidence"),
    ),
    LedgerSpec(
        filename="components.yaml",
        entries_key="components",
        id_prefix="P",
        label="構成要素",
        required=(
            "id",
            "kind",
            "name",
            "order",
            "role",
            "controlled_by",
            "evidence",
            "confidence",
        ),
        enums={
            "kind": KINDS,
            "controlled_by": CONTROLLED_BY,
            "confidence": CONFIDENCE,
        },
        stat_keys=("kind", "controlled_by", "confidence"),
    ),
)


class Failures(list):
    def add(self, where: str, msg: str) -> None:
        self.append(f"{where}: {msg}")


@dataclass
class LedgerResult:
    spec: LedgerSpec
    entries: list = field(default_factory=list)

    @property
    def evidence_count(self) -> int:
        return sum(len(e.get("evidence", [])) for e in self.entries if isinstance(e, dict))


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


def read_lines(path: Path, cache: dict[Path, list[str]]) -> list[str]:
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return cache[path]


def check_evidence(where: str, ev, cache, fail: Failures) -> None:
    """evidence 1 件の照合。全台帳でこの関数だけを使う（片方だけ緩い検証にしない）。"""
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


def check_entry(spec: LedgerSpec, entry, seen_ids: set[str], cache, fail: Failures) -> None:
    if not isinstance(entry, dict):
        fail.add(spec.filename, "要素がマッピングではない")
        return

    eid = entry.get("id", "<no id>")
    where = f"{spec.filename} {eid}"

    missing = [k for k in spec.required if k not in entry]
    if missing:
        fail.add(where, f"必須キーが無い: {', '.join(missing)}")
        return

    if not spec.id_re.match(str(eid)):
        fail.add(where, f"id は {spec.id_prefix}001 形式にする")
    if eid in seen_ids:
        fail.add(where, "id が重複している")
    seen_ids.add(eid)

    for key, allowed in spec.enums.items():
        if entry[key] not in allowed:
            fail.add(where, f"{key} が不正: {entry[key]!r} (許容: {sorted(allowed)})")

    evidence = entry["evidence"]
    if not isinstance(evidence, list) or not evidence:
        fail.add(where, "evidence が空。根拠を持たないものは台帳に載せない")
        return

    for i, ev in enumerate(evidence):
        check_evidence(f"{where} evidence[{i}]", ev, cache, fail)


def load_ledger(spec: LedgerSpec, commit: str | None, fail: Failures) -> LedgerResult:
    result = LedgerResult(spec=spec)
    if not spec.path.is_file():
        fail.add(spec.filename, "が無い")
        return result
    try:
        data = yaml.safe_load(spec.path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        fail.add(spec.filename, f"パースできない: {exc}")
        return result
    if not isinstance(data, dict):
        fail.add(spec.filename, "トップレベルがマッピングではない")
        return result

    ref = data.get("source_ref")
    if commit and ref != commit:
        fail.add(spec.filename, f"source_ref が source.lock と違う: {ref} != {commit}")

    raw = data.get(spec.entries_key)
    if not isinstance(raw, list) or not raw:
        fail.add(spec.filename, f"{spec.entries_key} が空のリスト")
        return result

    result.entries = raw
    return result


def print_stats(results: list[LedgerResult]) -> None:
    for res in results:
        entries = [e for e in res.entries if isinstance(e, dict)]
        print(f"{res.spec.filename}: {len(entries)} 件 / evidence {res.evidence_count} 件")
        for key in res.spec.stat_keys:
            counts = Counter(e.get(key, "<none>") for e in entries)
            breakdown = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            print(f"  {key:20} {breakdown}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", action="store_true", help="検証に加えて集計を出す")
    args = parser.parse_args()

    fail = Failures()

    commit = read_pinned_commit(fail)
    vendor_ok = check_vendor(commit, fail) if commit else False

    results = [load_ledger(spec, commit, fail) for spec in LEDGERS]

    if vendor_ok:
        cache: dict[Path, list[str]] = {}
        for res in results:
            seen: set[str] = set()
            for entry in res.entries:
                check_entry(res.spec, entry, seen, cache, fail)
    elif any(res.entries for res in results):
        fail.add("verify", "vendor が使えないため evidence を照合できなかった")

    if fail:
        print(f"NG: {len(fail)} 件", file=sys.stderr)
        for msg in fail:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    summary = " / ".join(
        f"{res.spec.label} {len(res.entries)} 件・evidence {res.evidence_count} 件" for res in results
    )
    print(f"OK: {summary} すべて {commit[:12]} の実ファイルと一致")
    if args.stats:
        print()
        print_stats(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
