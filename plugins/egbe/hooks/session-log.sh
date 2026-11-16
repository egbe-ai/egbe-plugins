#!/bin/sh
# Egbe session logging for Claude Code and Cowork, run at Stop and SessionEnd.
#
# On by default in every project folder set up for Egbe: installing the plugin
# is the founder's agreement, which its README and Egbe's setup disclose. It
# needs the project's Git-ignored, private .env.local with the project's Egbe
# key, and stays off when that file says EGBE_SESSION_LOGGING=off, when the
# project's saved choice declines logging, or when the project already sends
# sessions through the Langfuse plugin. It uploads the new part of this
# session's transcript files to Egbe's telemetry gateway, authenticated with the
# project's own key, and asks the gateway to record the new turns. It never
# blocks or fails the session: work runs in the background, with short
# timeouts, and any error leaves the rest for the next turn.

umask 077
project=${CLAUDE_PROJECT_DIR:-$PWD}
env_file="$project/.env.local"
[ -f "$env_file" ] || exit 0
# Only the project's private settings count: setup writes .env.local with mode
# 600, while a copy that came with a cloned repository is readable by others.
case $(ls -ln "$env_file" | cut -c5-10) in ------) ;; *) exit 0 ;; esac

setting() {
  sed -n "s/^[[:space:]]*\(export[[:space:]][[:space:]]*\)\{0,1\}$1=//p" "$env_file" | tail -n 1 |
    sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

choice=$(setting EGBE_SESSION_LOGGING)
case $choice in
  on) ;;
  '')
    # A choice saved before logging became the default still holds.
    saved="$project/egbe-docs/telemetry/setup.json"
    grep -Eqs '"consent"[[:space:]]*:[[:space:]]*"(declined|skipped)"' "$saved" && exit 0
    # So does a stop of only this harness's collector: its own "enabled": false
    # or "stop", whatever nested objects it also holds.
    [ -f "$saved" ] && awk '
      { text = text $0 " " }
      END {
        while ((at = index(text, "\"claude-code\"")) > 0) {
          text = substr(text, at + 13)
          if (!match(text, /^[ \t\r]*:[ \t\r]*[{]/)) continue
          body = substr(text, RLENGTH + 1); depth = 1; quoted = 0; escaped = 0; own = ""
          for (i = 1; i <= length(body) && depth > 0; i++) {
            c = substr(body, i, 1); before = depth
            if (quoted) { if (escaped) escaped = 0; else if (c == "\\") escaped = 1; else if (c == "\"") quoted = 0 }
            else if (c == "\"") quoted = 1
            else if (c == "{" || c == "[") depth++
            else if (c == "}" || c == "]") depth--
            if (before == 1 && depth == 1) own = own c
          }
          exit !(own ~ /"enabled"[ \t\r]*:[ \t\r]*false/ || own ~ /"stop"[ \t\r]*:/)
        }
        exit 1
      }' "$saved" && exit 0
    # The Langfuse plugin already records this project's sessions; don't send them twice.
    grep -Eqs 'LANGFUSE_BASE_URL"[^,}]*/ingest/claude-code' "$project/.claude/settings.local.json" "$project/.claude/settings.json" && exit 0
    ;;
  *) exit 0 ;;
esac
command -v curl >/dev/null 2>&1 || exit 0
os_url=$(setting OS_URL)
os_url=${os_url%/}
os_key=$(setting OS_API_KEY)
base=$(setting EGBE_TELEMETRY_URL)
public=$(setting EGBE_TELEMETRY_PUBLIC_KEY)
secret=$(setting EGBE_TELEMETRY_SECRET_KEY)
[ -n "$secret" ] || secret=$os_key
# Egbe's own OS and telemetry gateway, or loopback services in tests.
case $os_url in
  https://os.hz.egbe.dev) [ -n "$base" ] || base=https://observe.hz.egbe.dev/telemetry ;;
  http://127.0.0.1:[0-9]* | http://localhost:[0-9]*) ;;
  *) os_url= ;;
esac
# Sessions go only to Egbe's telemetry gateway, or a loopback gateway in tests.
case $base in
  https://observe.hz.egbe.dev/* | http://127.0.0.1:[0-9]* | http://localhost:[0-9]*) base=${base%/} ;;
  *) exit 0 ;;
esac
case $base$os_url in *[!A-Za-z0-9:/._-]*) exit 0 ;; esac
case $secret in '' | *[!A-Za-z0-9_-]*) exit 0 ;; esac
# Without a saved public key, the project's own is found once with its Egbe key.
if [ -z "$public" ]; then
  [ -n "$os_url" ] && [ "$secret" = "$os_key" ] || exit 0
else
  case $public in pk-lf-*[!A-Za-z0-9-]* | pk-lf-) exit 0 ;; pk-lf-*) ;; *) exit 0 ;; esac
fi

payload=$(cat)
field() {
  printf '%s' "$payload" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
}
event=$(field hook_event_name)
session=$(field session_id)
transcript=$(field transcript_path)
case $event in Stop | SessionEnd) ;; *) exit 0 ;; esac
printf '%s\n' "$session" | grep -Eq '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' || exit 0
[ -f "$transcript" ] || exit 0

data="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/egbe}"
state="$data/sessions/$session"
known="$data/projects/$(printf '%s' "$project" | cksum | cut -d ' ' -f 1)"
url="$base/ingest/claude-code/sessions/$session"
chunk_bytes=4194304

request() {
  # The credential goes to curl on stdin, never on its command line.
  printf 'user = "%s:%s"\n' "$public" "$secret" |
    curl -sS -K - -o /dev/null -D - -H 'Expect:' --connect-timeout 5 --max-time 30 "$@" 2>/dev/null | tr -d '\r'
}

# The project's telemetry public key, pk-lf-egbe-<project id>, from its Egbe key.
discover() {
  [ -z "$public" ] || return 0
  public=$(sed -n '1s/^\(pk-lf-egbe-[1-9][0-9]*\)$/\1/p' "$known" 2>/dev/null)
  [ -z "$public" ] || return 0
  id=$(printf 'header = "Authorization: Bearer %s"\n' "$os_key" |
    curl -sS -K - --connect-timeout 5 --max-time 15 "$os_url/me/limits" 2>/dev/null |
    sed -n 's/.*"instance_id"[[:space:]]*:[[:space:]]*\([1-9][0-9]*\).*/\1/p' | head -n 1)
  case $id in '' | ???????????????????*) return 1 ;; esac
  public="pk-lf-egbe-$id"
  mkdir -p "${known%/*}" && printf '%s\n' "$public" >"$known"
}

upload() {
  file=$1
  name=$2
  mark="$state/$(printf '%s' "$name" | tr '/' '_').offset"
  sent=$(cat "$mark" 2>/dev/null)
  case $sent in '' | *[!0-9]*) sent=0 ;; esac
  size=$(wc -c <"$file" | tr -d ' ')
  rounds=0
  while [ "$sent" -lt "$size" ] && [ "$rounds" -lt 32 ] && [ "$(date +%s)" -lt "$deadline" ]; do
    rounds=$((rounds + 1))
    tail -c +"$((sent + 1))" "$file" | head -c "$chunk_bytes" >"$state/chunk"
    reply=$(request -X PUT -H "X-Egbe-Offset: $sent" -H 'Content-Type: application/octet-stream' \
      --data-binary @"$state/chunk" "$url/files/$name")
    status=$(printf '%s\n' "$reply" | sed -n '1s/^HTTP\/[0-9.]* \([0-9][0-9]*\).*/\1/p')
    offset=$(printf '%s\n' "$reply" | sed -n 's/^[Xx]-[Ee]gbe-[Oo]ffset: *\([0-9][0-9]*\)$/\1/p' | tail -n 1)
    case $status in
      200 | 409) [ -n "$offset" ] || return 1 ;;
      *) return 1 ;;
    esac
    # A 409 reports what the gateway already holds; continue from there.
    sent=$offset
    printf '%s\n' "$sent" >"$mark"
  done
  [ "$sent" -ge "$size" ]
}

run() {
  mkdir -p "$state" || return
  lock="$state/lock"
  waited=0
  until mkdir "$lock" 2>/dev/null; do
    # Another upload for this session is running; wait for it, then send ours.
    [ "$waited" -ge 30 ] && { [ -n "$(find "$lock" -prune -mmin +5 2>/dev/null)" ] && rmdir "$lock"; return; }
    sleep 1
    waited=$((waited + 1))
  done
  deadline=$(($(date +%s) + 90))
  discover || { rmdir "$lock"; return; }
  changed=0
  before=$(cat "$state"/*.offset 2>/dev/null | cksum)
  upload "$transcript" transcript.jsonl
  # A rejected discovered key is found again next turn, for example after the
  # folder was set up for another business.
  [ "$status" = 401 ] && rm -f "$known"
  dir=${transcript%.jsonl}
  if [ -d "$dir/subagents" ]; then
    find "$dir/subagents" -type f \( -name 'agent-*.jsonl' -o -name 'agent-*.meta.json' -o -name journal.jsonl \) |
      while IFS= read -r path; do upload "$path" "${path#"$dir"/}"; done
  fi
  [ "$(cat "$state"/*.offset 2>/dev/null | cksum)" = "$before" ] || changed=1
  rm -f "$state/chunk"
  rmdir "$lock"
  [ "$changed" = 1 ] || [ "$event" = SessionEnd ] || return
  # A busy gateway answers 429 or 503: ask again for a few minutes, so the
  # session's last turns are recorded even when no later turn follows.
  tries=0
  while :; do
    status=$(request -X POST -H 'Content-Type: application/json' --data "{\"event\":\"$event\"}" "$url/process" |
      sed -n '1s/^HTTP\/[0-9.]* \([0-9][0-9]*\).*/\1/p')
    case $status in 429 | 503) ;; *) return ;; esac
    tries=$((tries + 1))
    [ "$tries" -lt 10 ] || return
    sleep 30
  done
}

(trap '' HUP; run) </dev/null >/dev/null 2>&1 &
exit 0
