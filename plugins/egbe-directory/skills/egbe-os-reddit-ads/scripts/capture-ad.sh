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

# Find a Chrome/Chromium binary that can do headless screenshots
find_chrome() {
    # Prefer the agent-browser bundled Chrome (real binary, not the shim)
    local candidate
    for candidate in \
        /opt/agent-browser/browsers/chrome-*/chrome \
        /usr/bin/google-chrome \
        /usr/bin/chromium \
        /usr/bin/chromium-browser
    do
        if [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

CHROME_BIN=$(find_chrome) || {
    echo "Error: no usable Chrome/Chromium binary found"
    exit 1
}

# Resolve absolute paths
HTML_ABS=$(cd "$(dirname "$HTML_FILE")" && pwd)/$(basename "$HTML_FILE")
PNG_DIR=$(cd "$(dirname "$PNG_FILE")" 2>/dev/null && pwd) || PNG_DIR="$(pwd)"
PNG_ABS="$PNG_DIR/$(basename "$PNG_FILE")"

echo "=== Capture: ${WIDTH}x${HEIGHT} ==="
echo "HTML:   $HTML_ABS"
echo "PNG:    $PNG_ABS"
echo "Chrome: $CHROME_BIN"

# Render HTML → PNG via headless Chrome
# --hide-scrollbars: don't include scrollbar in screenshot
# --no-sandbox: required when running as non-root in container
# --disable-gpu: required in headless mode without display
# --window-size: sets viewport to exact dimensions
"$CHROME_BIN" \
    --headless \
    --no-sandbox \
    --disable-gpu \
    --hide-scrollbars \
    --disable-dev-shm-usage \
    --window-size="${WIDTH},${HEIGHT}" \
    --screenshot="$PNG_ABS" \
    "file://${HTML_ABS}" \
    2>&1 | grep -v -E '^\[.*ERROR:dbus|^\[.*WARN:|Failed to connect to the bus' || true
# Filter above hides dbus/bus noise from containers without systemd — headless
# Chrome tries to reach the desktop session bus and logs harmless errors. If you
# ever need to debug a real Chrome failure, remove the filter temporarily to see
# the full stderr.

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
