#!/usr/bin/env bash
# ./hackmode.sh on   keep the Mac awake (display + system), show battery/disk/network status
# ./hackmode.sh off  back to normal
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
PIDF=.hackmode.pid

case "${1:-on}" in
  on)
    if [[ -f $PIDF ]] && kill -0 "$(cat $PIDF)" 2>/dev/null; then echo "already on (pid $(cat $PIDF))"
    else caffeinate -dimsu & echo $! > $PIDF; echo "caffeinate on (pid $!): no sleep until ./hackmode.sh off"; fi
    echo; pmset -g batt | tail -1
    df -h / | awk 'NR==2{print "disk free: "$4}'
    echo; echo "network:"
    for h in https://api.anthropic.com https://aitta-api.csc.fi https://pypi.org https://github.com; do
      code=$(curl -s -o /dev/null -m 6 -w '%{http_code}' "$h" || echo 000)
      [[ "$code" == "000" ]] && echo "  DOWN  $h" || echo "  ok    $h ($code)"
    done
    cat <<'EOF'

checklist:
  - Focus / Do Not Disturb on (Control Centre)
  - charger plugged in; phone hotspot ready as Wi-Fi backup
  - quit apps you don't need (Chrome tabs eat RAM on Intel Macs)
  - stage demo: make demo  (DEMO_MODE replays demo/cache, no network)
EOF
    ;;
  off)
    [[ -f $PIDF ]] && kill "$(cat $PIDF)" 2>/dev/null; rm -f $PIDF; echo "caffeinate off" ;;
  *) echo "usage: $0 on|off"; exit 2 ;;
esac
