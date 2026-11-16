#!/bin/bash
# Upload a delivery folder to a remote store as ONE immutable version, check it there, then point `current` at it.
#
#   upload_version.sh [-n] [-r README] <ssh-host> <remote-root> <version-name> <local-folder>
#
#   -n          dry run: print what would happen, change nothing
#   -r README   also copy this file to <remote-root>/README.md (the top-level "which file to use" note)
#
# What it does:
#   1. writes md5sums.txt (GNU md5sum format, paths relative to the folder) of every file in <local-folder>
#   2. refuses if <remote-root>/<version-name> already exists (versions are never overwritten)
#   3. rsyncs the folder there, runs `md5sum -c` on the remote, and only if every file checks out
#   4. moves the `current` symlink to the new version (older versions stay untouched)
# Name versions after the map they hold, e.g. <builder>_<YYYY-MM-DD>_<HHMM>, and keep a version table in the README.
# The remote needs bash, rsync and GNU md5sum; ssh must work without a password prompt (keys / agent).
set -euo pipefail
DRY=0; README=""
while getopts "nr:" o; do
  case $o in n) DRY=1 ;; r) README=$OPTARG ;; *) exit 2 ;; esac
done
shift $((OPTIND - 1))
[ $# -eq 4 ] || { sed -n '2,8p' "$0"; exit 2; }
HOST=$1; ROOT=$2; VER=$3; SRC=${4%/}
[ -d "$SRC" ] || { echo "no folder $SRC"; exit 1; }
SSH="ssh -o BatchMode=yes -o ConnectTimeout=25"
run() { if [ $DRY = 1 ]; then echo "[dry run] $*"; else eval "$@"; fi; }

python3 - "$SRC" <<'EOF'
import hashlib, pathlib, sys
base = pathlib.Path(sys.argv[1])
files = sorted(p for p in base.rglob("*") if p.is_file() and not p.name.startswith(".") and p.name != "md5sums.txt")
with open(base / "md5sums.txt", "w") as f:
    for p in files:
        f.write(f"{hashlib.md5(p.read_bytes()).hexdigest()}  {p.relative_to(base).as_posix()}\n")
print(len(files), "files in", base / "md5sums.txt")
EOF

run "$SSH $HOST \"test ! -e '$ROOT/$VER' || { echo '$ROOT/$VER exists: not overwriting'; exit 1; }; mkdir -p '$ROOT/$VER'\""
run "rsync -a --exclude '.*' -e \"$SSH\" '$SRC/' '$HOST:$ROOT/$VER/'"
[ -n "$README" ] && run "rsync -a -e \"$SSH\" '$README' '$HOST:$ROOT/README.md'"
run "$SSH $HOST \"cd '$ROOT/$VER' && md5sum -c --quiet md5sums.txt && echo md5 OK: \\\$(wc -l < md5sums.txt) files && cd '$ROOT' && ln -sfn '$VER' current && ls -l '$ROOT'\""
