#!/usr/bin/env bash
# Wait for rate-limited / flaky APIs to come back, then run their collectors.
# Usage: scripts/retry_when_up.sh [max_hours] [sources...]
#        scripts/retry_when_up.sh            # 4 hours, gdelt and reddit
#        scripts/retry_when_up.sh 12 gdelt   # 12 hours, gdelt only
#
# GDELT throttles by IP (HTTP 429) and Arctic Shift occasionally goes down
# (HTTP 530). This polls each every 20 minutes and collects once it answers.
# The GDELT collector caches every response, so each attempt resumes where the
# last one stopped; it is done once data/raw/gdelt/articles_* exists.
set -u
cd "$(dirname "$0")/.."
max_hours=${1:-4}
shift || true
sources=${*:-gdelt reddit}
deadline=$(( $(date +%s) + max_hours * 3600 ))
gdelt_done=1; reddit_done=1
[[ " $sources " == *" gdelt "* ]] && gdelt_done=0
[[ " $sources " == *" reddit "* ]] && reddit_done=0

probe() { curl -s -m 30 -o /dev/null -w "%{http_code}" "$1"; }

while (( $(date +%s) < deadline )) && (( gdelt_done == 0 || reddit_done == 0 )); do
  if (( gdelt_done == 0 )) && [[ $(probe "https://api.gdeltproject.org/api/v2/doc/doc?query=bismillah&mode=timelinevolraw&format=json&timespan=1day") == 200 ]]; then
    echo "$(date '+%H:%M') GDELT is up; collecting"
    sleep 6 && uv run tenebres collect gdelt && ls data/raw/gdelt/articles_* >/dev/null 2>&1 && gdelt_done=1
  fi
  if (( reddit_done == 0 )) && [[ $(probe "https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=france&query=test&limit=1") == 200 ]]; then
    echo "$(date '+%H:%M') Arctic Shift is up; collecting"
    uv run tenebres collect reddit && ls data/raw/reddit/posts_* >/dev/null 2>&1 && reddit_done=1
  fi
  (( gdelt_done == 0 || reddit_done == 0 )) && sleep 1200
done
echo "gdelt_done=$gdelt_done reddit_done=$reddit_done"
(( gdelt_done && reddit_done ))
