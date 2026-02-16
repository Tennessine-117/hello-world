#!/usr/bin/env bash
set -euo pipefail

# 最新main上に、化学検索アプリの変更を載せ直す補助スクリプト。
# 使い方:
#   bash tools/rebuild_on_main.sh [remote] [base_branch] [new_branch]
# 例:
#   bash tools/rebuild_on_main.sh origin main chem-search-rebuild

REMOTE="${1:-origin}"
BASE_BRANCH="${2:-main}"
NEW_BRANCH="${3:-chem-search-rebuild}"

# このリポジトリで化学アプリを入れたコミット範囲
# 190ec1a: アプリ/データ/UI/READMEの実装
# 1d9cb8a: READMEの競合回避メモ追記
PICK_RANGE="190ec1a^..1d9cb8a"

echo "[1/5] fetch: ${REMOTE}/${BASE_BRANCH}"
git fetch "${REMOTE}" "${BASE_BRANCH}"

echo "[2/5] create branch: ${NEW_BRANCH} from ${REMOTE}/${BASE_BRANCH}"
git switch -C "${NEW_BRANCH}" "${REMOTE}/${BASE_BRANCH}"

echo "[3/5] cherry-pick range: ${PICK_RANGE}"
if git cherry-pick ${PICK_RANGE}; then
  echo "[4/5] cherry-pick success"
else
  echo "[4/5] conflict detected"
  echo "- 競合を解消したら: git add <files> && git cherry-pick --continue"
  echo "- 中止するなら:   git cherry-pick --abort"
  exit 1
fi

echo "[5/5] done"
echo "次: 動作確認後に push して新PRを作成してください。"
