#!/bin/zsh
# 解析対象を source.lock のピン留め commit で vendor/ へ取得する。
# 既に同一 commit が取得済みなら何もしない。取得できなければ必ず非ゼロで落ちる。
set -eu

ROOT="${0:A:h:h}"
LOCK="$ROOT/source.lock"
DEST="$ROOT/vendor/x-algorithm"

[ -r "$LOCK" ] || { print -u2 "source.lock を読めない: $LOCK"; exit 1; }

REPO_URL=""
COMMIT=""
while IFS='=' read -r key value; do
  case "$key" in
    REPO_URL) REPO_URL="$value" ;;
    COMMIT)   COMMIT="$value" ;;
  esac
done < "$LOCK"

[ -n "$REPO_URL" ] || { print -u2 "source.lock に REPO_URL が無い"; exit 1; }
[[ "$COMMIT" =~ '^[0-9a-f]{40}$' ]] || { print -u2 "source.lock の COMMIT が 40 桁の SHA ではない: '$COMMIT'"; exit 1; }

if [ -d "$DEST/.git" ]; then
  CURRENT=$(git -C "$DEST" rev-parse HEAD) || {
    print -u2 "vendor の HEAD を読めない。'make clean' してからやり直す。"; exit 1
  }
  if [ "$CURRENT" = "$COMMIT" ]; then
    print "already at $COMMIT"
    exit 0
  fi
  print "vendor の commit がピン留めと違う ($CURRENT) → 取り直す"
  rm -rf "$DEST"
fi

mkdir -p "$DEST"
git -C "$DEST" init -q
git -C "$DEST" remote add origin "$REPO_URL"
git -C "$DEST" fetch -q --depth 1 origin "$COMMIT"
git -C "$DEST" checkout -q FETCH_HEAD

FETCHED=$(git -C "$DEST" rev-parse HEAD) || { print -u2 "取得後の HEAD を読めない"; exit 1; }
[ "$FETCHED" = "$COMMIT" ] || {
  print -u2 "取得した commit がピン留めと一致しない: $FETCHED != $COMMIT"; exit 1
}

print "fetched $COMMIT -> ${DEST#$ROOT/}"
