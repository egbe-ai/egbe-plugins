#!/bin/sh
# Egbe session logging for Claude Code and Cowork, run at Stop and SessionEnd.
#
# On by default in every project folder set up for Egbe: installing the plugin
# is the founder's agreement, which its README and Egbe's setup disclose. It
# needs the project's Git-ignored, private .env.local with the project's Egbe
# key, and stays off when that file says EGBE_SESSION_LOGGING=off, when the
# project's saved choice declines logging, or when the project already sends
# sessions through the Langfuse plugin. Sessions in a Git worktree of the project
# use the main folder's settings; sessions in another copy of the project on this
# machine, such as one a scheduled job runs in, use the settings of the project
# folder the hook last logged in, while it still has them. It uploads the new part of this
# session's transcript files to Egbe's telemetry gateway, authenticated with the
# project's own key, and asks the gateway to record the new turns. It never
# blocks or fails the session: work runs in the background, with short
# timeouts, and any error leaves the rest for the next turn. In a project set up
# for Egbe, each run adds its result, never a secret, to last-run in the
# plugin's data folder.

umask 077
project=${CLAUDE_PROJECT_DIR:-$PWD}
data="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/egbe}"
home=$project

note() {
  [ -f "$home/egbe-docs/telemetry/setup.json" ] || [ -f "$home/.env.local" ] || return 0
  mkdir -p "$data" 2>/dev/null || return 0
  printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$project" "$1" >>"$data/last-run" 2>/dev/null
  tail -n 50 "$data/last-run" >"$data/last-run.tmp" 2>/dev/null && mv "$data/last-run.tmp" "$data/last-run"
}

project_of() {
  id=$(sed -n 's/.*"project_id"[[:space:]]*:[[:space:]]*\([1-9][0-9]*\).*/\1/p' "$1/egbe-docs/telemetry/setup.json" 2>/dev/null |
    head -n 1)
  case $id in ???????????????????*) ;; *) printf '%s' "$id" ;; esac
}

# Where this project's settings are: its own folder; the main folder of a Git
# worktree (a desktop scheduled task or claude --worktree); or, for another copy
# of the project on this machine, the project folder the hook last logged in,
# while that folder still has its settings and names the same project. Only that
# folder's path is remembered, never a key, so its settings and choices apply
# to the copies as they are now.
env_file="$home/.env.local"
source=folder
if [ ! -f "$env_file" ]; then
  common=$(cd "$project" 2>/dev/null && git rev-parse --git-common-dir 2>/dev/null) &&
    main=$(cd "$project" && cd "$common/.." && pwd -P) && [ -f "$main/.env.local" ] &&
    { home=$main; env_file="$main/.env.local"; source=worktree; }
fi
project_id=$(project_of "$home")
link=
[ -n "$project_id" ] && link="$data/folders/$project_id"
if [ ! -f "$env_file" ]; then
  folder=$(sed -n 1p "$link" 2>/dev/null)
  if [ -n "$folder" ] && [ "$folder" != "$home" ] && [ -f "$folder/.env.local" ] &&
    [ "$(project_of "$folder")" = "$project_id" ]; then
    home=$folder
    env_file="$folder/.env.local"
    source=copy
  else
    # The project's folder moved, lost its settings or names another project.
    [ -n "$link" ] && rm -f "$link"
    note "skipped: no .env.local here, in a main folder or in the project's folder"
    exit 0
  fi
fi
saved="$home/egbe-docs/telemetry/setup.json"
# Only the project's private settings count: setup writes .env.local with mode
# 600, while a copy that came with a cloned repository is readable by others.
case $(ls -ln "$env_file" | cut -c5-10) in ------) ;; *) note "skipped: settings readable by others"; exit 0 ;; esac

off() {
  note "skipped: $1"
  exit 0
}

setting() {
  sed -n "s/^[[:space:]]*\(export[[:space:]][[:space:]]*\)\{0,1\}$1=//p" "$env_file" | tail -n 1 |
    sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

choice=$(setting EGBE_SESSION_LOGGING)
case $choice in
  on) ;;
  '')
    # A choice saved before logging became the default still holds.
    grep -Eqs '"consent"[[:space:]]*:[[:space:]]*"(declined|skipped)"' "$saved" && off "logging declined"
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
      }' "$saved" && off "claude-code collector stopped"
    # The Langfuse plugin already records this project's sessions; don't send them twice.
    grep -Eqs 'LANGFUSE_BASE_URL"[^,}]*/ingest/claude-code' "$home/.claude/settings.local.json" "$home/.claude/settings.json" &&
      off "sessions go through the Langfuse plugin"
    ;;
  *) off "EGBE_SESSION_LOGGING=$choice" ;;
esac
command -v curl >/dev/null 2>&1 || { note "skipped: curl not found"; exit 0; }
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
  *) note "skipped: no Egbe telemetry gateway in the settings"; exit 0 ;;
esac
case $base$os_url in *[!A-Za-z0-9:/._-]*) note "skipped: unexpected characters in a URL"; exit 0 ;; esac
case $secret in '' | *[!A-Za-z0-9_-]*) note "skipped: no usable Egbe key"; exit 0 ;; esac
# Without a saved public key, the project's own is found once with its Egbe key.
if [ -z "$public" ]; then
  [ -n "$os_url" ] && [ "$secret" = "$os_key" ] || { note "skipped: no public key and no Egbe key to find it"; exit 0; }
else
  case $public in
    pk-lf-*[!A-Za-z0-9-]* | pk-lf-) note "skipped: unusable public key"; exit 0 ;;
    pk-lf-*) ;;
    *) note "skipped: unusable public key"; exit 0 ;;
  esac
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

state="$data/sessions/$session"
known="$data/projects/$(printf '%s' "$home" | cksum | cut -d ' ' -f 1)"
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

# Remembers this folder for other copies of the project on this machine, only
# while its key belongs to the project its setup.json names.
remember() {
  [ "$source" = folder ] && [ -n "$link" ] && [ "$public" = "pk-lf-egbe-$project_id" ] || return 0
  case $home in *'
'*) return 0 ;; esac
  mkdir -p "${link%/*}" && printf '%s\n' "$home" >"$link.tmp" && mv "$link.tmp" "$link"
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
  discover || { rmdir "$lock"; note "$session: the project's key lookup failed"; return; }
  # Another folder's key serves only the project this copy names.
  if [ "$source" = copy ] && [ "$public" != "pk-lf-egbe-$project_id" ]; then
    rmdir "$lock"; note "$session: skipped: the project folder's key belongs to another project"; return
  fi
  changed=0
  before=$(cat "$state"/*.offset 2>/dev/null | cksum)
  status=
  upload "$transcript" transcript.jsonl
  case $status in
    # A rejected discovered key is found again next turn, for example after the
    # folder was set up for another business.
    401) rm -f "$known"; note "$session: upload refused (HTTP 401)" ;;
    '' | 200 | 409) remember ;;
    *) note "$session: upload failed (HTTP $status)" ;;
  esac
  dir=${transcript%.jsonl}
  if [ -d "$dir/subagents" ]; then
    find "$dir/subagents" -type f \( -name 'agent-*.jsonl' -o -name 'agent-*.meta.json' -o -name journal.jsonl \) |
      while IFS= read -r path; do upload "$path" "${path#"$dir"/}"; done
  fi
  [ "$(cat "$state"/*.offset 2>/dev/null | cksum)" = "$before" ] || changed=1
  rm -f "$state/chunk"
  rmdir "$lock"
  [ "$changed" = 1 ] && note "$session: sent ($source settings)"
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
