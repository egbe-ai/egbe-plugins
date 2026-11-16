#!/usr/bin/env bash
# Ad Creative Capture Script
# Captures HTML ad creatives as PNG images at exact dimensions
#
# Usage: capture-ad.sh <html-file> <png-file> <width> <height> [--keep-html]
#
# By default, removes the HTML file after successful PNG capture.
# Use --keep-html to preserve intermediate HTML files for debugging.
#
# Renders HTML directly via headless Chrome — no agent intervention needed.

set -e

HTML_FILE="$1"
PNG_FILE="$2"
WIDTH="$3"
HEIGHT="$4"
KEEP_HTML=false

# Parse optional flags
shift 4 2>/dev/null || true
while [ $# -gt 0 ]; do
    case "$1" in
        --keep-html) KEEP_HTML=true ;;
        *) echo "Warning: Unknown flag '$1' ignored" ;;
    esac
    shift
done

# Validate arguments
if [ -z "$HTML_FILE" ] || [ -z "$PNG_FILE" ] || [ -z "$WIDTH" ] || [ -z "$HEIGHT" ]; then
    echo "Usage: $0 <html-file> <png-file> <width> <height> [--keep-html]"
    echo ""
    echo "Examples:"
    echo "  $0 ad-variant-a.html ad-variant-a.png 1200 627          # LinkedIn Feed"
    echo "  $0 slide-01.html slide-01.png 1080 1080                  # Instagram/LinkedIn Square"
    echo "  $0 story-ad.html story-ad.png 1080 1920                  # Stories (9:16)"
    echo "  $0 ad.html ad.png 1200 627 --keep-html                   # Keep HTML for debugging"
    exit 1
fi

# Check if HTML file exists
if [ ! -f "$HTML_FILE" ]; then
    echo "Error: HTML file not found: $HTML_FILE"
    exit 1
fi

# Find a Chrome/Chromium binary that can do headless screenshots.
# CHROME_PATH, when set, names the executable and is the only candidate.
CHROME_BIN=""
CHROME_SEARCHED=()

try_chrome() {
    CHROME_SEARCHED+=("$1")
    if [ -f "$1" ] && [ -x "$1" ]; then
        CHROME_BIN="$1"
        return 0
    fi
    return 1
}

find_chrome() {
    local candidate dir app name
    if [ -n "${CHROME_PATH:-}" ]; then
        try_chrome "$CHROME_PATH" && return 0
        echo "Error: CHROME_PATH is not an executable file: $CHROME_PATH" >&2
        echo "Set it to the browser executable, e.g. on macOS" >&2
        echo "  /Applications/Google Chrome.app/Contents/MacOS/Google Chrome" >&2
        return 1
    fi

    # Linux: prefer the agent-browser bundled Chrome (real binary, not the shim)
    for candidate in \
        /opt/agent-browser/browsers/chrome-*/chrome \
        /usr/bin/google-chrome \
        /usr/bin/chromium \
        /usr/bin/chromium-browser
    do
        try_chrome "$candidate" && return 0
    done

    # macOS: Chromium-based app bundles, system-wide then per-user
    for dir in /Applications ${HOME:+"$HOME/Applications"}; do
        for app in \
            "Google Chrome" \
            "Chromium" \
            "Google Chrome Canary" \
            "Microsoft Edge" \
            "Brave Browser"
        do
            try_chrome "$dir/$app.app/Contents/MacOS/$app" && return 0
        done
    done

    # Anything else on PATH (e.g. snap or Homebrew installs)
    for name in google-chrome-stable google-chrome chromium chromium-browser; do
        candidate=$(command -v "$name" 2>/dev/null) || candidate=""
        try_chrome "${candidate:-PATH: $name}" && return 0
    done

    echo "Error: no usable Chrome/Chromium binary found. Searched:" >&2
    printf '  %s\n' "${CHROME_SEARCHED[@]}" >&2
    echo "Set CHROME_PATH to an installed Chrome/Chromium executable, or ask the user to install one." >&2
    return 1
}

find_chrome || exit 1

# Resolve absolute paths
HTML_ABS=$(cd "$(dirname "$HTML_FILE")" && pwd)/$(basename "$HTML_FILE")
PNG_DIR=$(cd "$(dirname "$PNG_FILE")" 2>/dev/null && pwd) || PNG_DIR="$(pwd)"
PNG_ABS="$PNG_DIR/$(basename "$PNG_FILE")"

echo "=== Capture: ${WIDTH}x${HEIGHT} ==="
echo "HTML:   $HTML_ABS"
echo "PNG:    $PNG_ABS"
echo "Chrome: $CHROME_BIN"

# Throwaway profile: never touch (or wait on) the user's running browser profile
CHROME_PROFILE=$(mktemp -d "${TMPDIR:-/tmp}/capture-ad-chrome.XXXXXX")
trap 'rm -rf "$CHROME_PROFILE"' EXIT

# --no-sandbox: required when running as non-root in a Linux container; keep
# the sandbox on macOS desktops, where it works
SANDBOX_FLAGS=()
if [ "$(uname -s)" != Darwin ]; then
    SANDBOX_FLAGS=(--no-sandbox)
fi

# Render HTML → PNG via headless Chrome
# --hide-scrollbars: don't include scrollbar in screenshot
# --disable-gpu: required in headless mode without display
# --use-mock-keychain: no macOS Keychain prompt (ignored elsewhere)
# --window-size: sets viewport to exact dimensions
"$CHROME_BIN" \
    --headless \
    "${SANDBOX_FLAGS[@]}" \
    --disable-gpu \
    --hide-scrollbars \
    --disable-dev-shm-usage \
    --user-data-dir="$CHROME_PROFILE" \
    --use-mock-keychain \
    --window-size="${WIDTH},${HEIGHT}" \
    --screenshot="$PNG_ABS" \
    "file://${HTML_ABS}" \
    2>&1 | grep -v -E '^\[.*ERROR:dbus|^\[.*WARN:|Failed to connect to the bus|CVDisplayLinkCreateWithCGDisplay|Trying to load the allocator multiple times' || true
# Filter above hides harmless noise: dbus/bus errors from containers without
# systemd, and macOS display-link/allocator messages from headless Chrome. If you ever need
# to debug a real Chrome failure, remove the filter temporarily to see the full
# stderr.

# Validate output
if [ -f "$PNG_ABS" ]; then
    DIMS=$(file "$PNG_ABS" | grep -o '[0-9]* x [0-9]*' | head -1)
    SIZE=$(stat -c%s "$PNG_ABS" 2>/dev/null || stat -f%z "$PNG_ABS" 2>/dev/null)
    echo "Output: $PNG_ABS"
    echo "Dimensions: $DIMS"
    echo "Size: ${SIZE} bytes"
    EXPECTED="${WIDTH} x ${HEIGHT}"
    if [ "$DIMS" = "$EXPECTED" ]; then
        echo "✓ Dimensions match target (${EXPECTED})"
    else
        echo "✗ WARNING: Expected ${EXPECTED}, got ${DIMS}"
        exit 1
    fi

    # Cleanup HTML unless --keep-html
    if [ "$KEEP_HTML" = false ]; then
        rm -f "$HTML_ABS"
        echo "Cleaned up: $(basename "$HTML_ABS")"
    else
        echo "HTML preserved: $HTML_ABS"
    fi
else
    echo "Error: PNG file not produced at $PNG_ABS"
    echo "HTML preserved for debugging: $HTML_ABS"
    exit 1
fi
