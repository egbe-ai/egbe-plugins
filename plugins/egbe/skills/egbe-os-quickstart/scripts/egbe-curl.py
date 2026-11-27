#!/usr/bin/env python3
"""Add opt-in workspace identity to curl requests to the configured Egbe URL.

Requests made only to that URL with supported options send the installed catalog
release. Those with a single destination are also traced: they exit 22 on an HTTP
status of 400 or above (the body is still printed, as with `curl --fail-with-body`)
and end with one stderr line
`egbe-curl: status=<code> request_id=<id> route=<METHOD> <path> catalog=<release>`.
When curl stopped without a complete response (a certificate, TLS,
name-resolution, connection, proxy or timeout failure), one line naming the host
and the environment guide precedes it; curl's exit code is kept.
`--egbe-run <command>` instead starts a bundled client with the saved settings
from `.env.local` in its environment. `--egbe-git <remote> <git arguments>` runs
native Git against an Egbe Git remote with the saved key and the same identity
headers.
"""
import os
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlsplit
from uuid import UUID

CATALOG_DIGEST = re.compile(r"[a-f0-9]{64}")
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
DATA_OPTIONS = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "-F", "--form", "--form-string"}
SUPPORTED_VALUE_OPTIONS = DATA_OPTIONS | {"-H", "--header", "-X", "--request", "-o", "--output", "-w", "--write-out",
                                          "--max-time", "--connect-timeout", "--retry", "--retry-delay",
                                          "--retry-max-time", "-A", "--user-agent", "--url"}


def project_environment(settings_file=None, *, saved_credentials=False):
    values = {}
    path = Path(settings_file) if settings_file else Path.cwd() / ".env.local"
    if path.is_symlink():
        raise ValueError("Load connection settings from a regular project-local .env.local file")
    if path.is_file():
        for line in path.read_text().splitlines():
            match = re.match(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)", line.strip())
            if match and (match[1] in {"OS_URL", "OS_API_KEY", "OS_WORKSPACE_NAME"} or match[1].startswith("OS_CONNECTION_ID_")
                          or (settings_file and match[1] == "OS_AGENT_NAME")):
                parts = shlex.split(match[2], comments=True)
                if len(parts) <= 1:
                    values[match[1]] = parts[0] if parts else ""
    # Saved scheduler snapshots own their agent name. Interactive credential
    # files keep the actual agent shell-local; only that name may fall back.
    # UUIDs, nicknames and destination always belong to the selected file.
    if settings_file:
        values.setdefault("OS_AGENT_NAME", os.environ.get("OS_AGENT_NAME", ""))
        return values
    # Identity belongs to this workspace, never an ambient previous project.
    values.update({key: value for key, value in os.environ.items()
                   if not (key.startswith("OS_CONNECTION_ID_") or key == "OS_WORKSPACE_NAME"
                           or (saved_credentials and key in {"OS_URL", "OS_API_KEY"}))})
    return values


def catalog_release(script=__file__):
    """The skills catalog release of this installation, or None.

    `.egbe-catalog/manifest.json` beside the installed skills records the
    published skills archive digest the last refresh reconciled. While a refresh
    kept some skills at an earlier release (local edits or conflicts) it records
    only its target, reported with `+partial`. A helper outside an installed
    catalog, or an unreadable manifest, sends no release.
    """
    parents = Path(os.path.abspath(script)).parents
    if len(parents) < 3:
        return None  # e.g. a pre-install copy saved directly in /tmp
    path = parents[2] / ".egbe-catalog" / "manifest.json"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
            return None
        manifest = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    reconciled, target = manifest.get("reconciled"), manifest.get("target")
    if isinstance(reconciled, str) and CATALOG_DIGEST.fullmatch(reconciled):
        return reconciled
    if isinstance(target, str) and CATALOG_DIGEST.fullmatch(target):
        return target + "+partial"
    return None


def curl_destinations(arguments):
    # Consume curl option values before classifying URLs. Extra known options
    # remain pass-through for other hosts, but are not enabled for identity calls.
    value_options = set("""
        --abstract-unix-socket --alt-svc --aws-sigv4 --cacert --capath --cert --cert-type --ciphers
        --config --connect-timeout --connect-to --continue-at --cookie --cookie-jar
        --create-file-mode --crlfile --curves --data --data-ascii --data-binary --data-raw
        --data-urlencode --delegation --dns-interface --dns-ipv4-addr --dns-ipv6-addr --dns-servers
        --doh-url --dump-header --egd-file --engine --etag-compare --etag-save --expect100-timeout
        --form --form-string --ftp-account --ftp-alternative-to-user --ftp-method --ftp-port
        --ftp-ssl-ccc-mode --happy-eyeballs-timeout-ms --haproxy-clientip --header --help
        --hostpubmd5 --hostpubsha256 --hsts --interface --ipfs-gateway --json --keepalive-time --key
        --key-type --krb --libcurl --limit-rate --local-port --login-options --mail-auth --mail-from
        --mail-rcpt --max-filesize --max-redirs --max-time --netrc-file --noproxy --oauth2-bearer
        --output --output-dir --parallel-max --pass --pinnedpubkey --preproxy --proto
        --proto-default --proto-redir --proxy --proxy-cacert --proxy-capath --proxy-cert
        --proxy-cert-type --proxy-ciphers --proxy-crlfile --proxy-header --proxy-key
        --proxy-key-type --proxy-pass --proxy-pinnedpubkey --proxy-service-name
        --proxy-tls13-ciphers --proxy-tlsauthtype --proxy-tlspassword --proxy-tlsuser --proxy-user
        --pubkey --quote --random-file --range --rate --referer --request --request-target --resolve
        --retry --retry-delay --retry-max-time --sasl-authzid --service-name --socks4 --socks4a
        --socks5 --socks5-gssapi-service --socks5-hostname --speed-limit --speed-time --stderr
        --telnet-option --tftp-blksize --time-cond --tls-max --tls13-ciphers --tlsauthtype
        --tlspassword --tlsuser --trace --trace-ascii --trace-config --unix-socket --upload-file
        --url --url-query --user --user-agent --variable --write-out
    """.split()) | {"-" + char for char in "ACDEFHKPQTUXYbcdehmortuwxyz"}
    flags = {"--disable", "--silent", "--show-error", "--fail", "--fail-with-body", "--include",
             "--head", "--get", "--verbose", "--no-buffer", "--globoff", "--compressed",
             "--http1.1", "--http2", "--no-progress-meter"}
    destinations, unsupported = [], False
    index = 0
    while index < len(arguments):
        arg = arguments[index]
        option, equals, value = arg.partition("=")
        if arg == "--":
            destinations.extend(arguments[index + 1:])
            break
        if option in value_options:
            unsupported |= option not in SUPPORTED_VALUE_OPTIONS
            if not equals:
                index += 1
                if index == len(arguments):
                    unsupported = True
                    break
                value = arguments[index]
            if option == "--url":
                destinations.append(value)
        elif arg in flags or (arg.startswith("-") and not arg.startswith("--")
                              and set(arg[1:]) <= set("sSfIivNgG")):
            pass
        elif arg.startswith("-"):
            unsupported = True
            if not arg.startswith("--"):
                # A value-taking short option consumes the rest of its cluster,
                # or the next argument: e.g. -sdURL and -sd URL.
                for position, char in enumerate(arg[1:], start=1):
                    if "-" + char in value_options:
                        if position == len(arg) - 1:
                            index += 1
                        break
        else:
            destinations.append(arg)
        index += 1
    return destinations, unsupported


def egbe_base(environment):
    return urlsplit(environment.get("OS_URL", "https://os.hz.egbe.dev").rstrip("/"))


def is_egbe_url(url, base):
    def origin(value):
        port = value.port if value.port is not None else {"http": 80, "https": 443}.get(value.scheme)
        return value.scheme, value.hostname, port
    try:
        target = urlsplit(url)
        return target.hostname == base.hostname and origin(target) == origin(base) and (
            not base.path or target.path == base.path or target.path.startswith(base.path + "/"))
    except ValueError:
        return False


def egbe_destinations(arguments, environment):
    """The URLs of a request made only to the Egbe URL with supported options, else []."""
    destinations, unsupported = curl_destinations(arguments)
    base = egbe_base(environment)
    if unsupported or not destinations or not all(is_egbe_url(url, base) for url in destinations):
        return []
    return destinations


def connection_variable(agent):
    """The `.env.local` key holding this agent's saved connection ID."""
    return "OS_CONNECTION_ID_" + re.sub(r"[^A-Z0-9]+", "_", agent.upper()).strip("_")


def command(arguments, environment):
    result = ["curl"]
    base = egbe_base(environment)
    destinations, unsupported = curl_destinations(arguments)
    matches = [is_egbe_url(url, base) for url in destinations]
    agent = environment.get("OS_AGENT_NAME", "")
    ambiguous_destination = any("://" not in url and is_egbe_url(
        base.scheme + "://" + url, base) for url in destinations)
    if (any(matches) or ambiguous_destination) and agent:
        if unsupported:
            raise ValueError("Use supported explicit curl options for identified Egbe requests")
        if not destinations or not all(is_egbe_url(url, base) for url in destinations):
            raise ValueError("Use separate curl commands for Egbe and other destinations")
        # Ignore ambient curl config only for identified requests: it may add
        # extra destinations or redirects. Other curl commands stay unchanged.
        result.append("--disable")
        connection = environment.get(connection_variable(agent))
        if not connection:
            raise ValueError("Run Egbe quickstart to save this agent's workspace connection ID first")
        connection = str(UUID(connection))
        labels = [("X-Egbe-Agent-Name", agent)]
        workspace = environment.get("OS_WORKSPACE_NAME")
        if workspace:
            labels.append(("X-Egbe-Workspace-Name", workspace))
        for _, label in labels:
            if not re.fullmatch(r"[A-Za-z0-9_ .()+-]{1,80}", label) or not label.strip():
                raise ValueError("Connection labels must be plain ASCII nicknames of 1–80 characters")
        result += ["-H", "X-Egbe-Connection-Id: " + connection]
        for name, label in labels:
            result += ["-H", name + ": " + label]
    release = catalog_release() if egbe_destinations(arguments, environment) else None
    if release:
        if result == ["curl"] and arguments[:1] == ["--disable"]:
            # --disable only works as curl's first option.
            result, arguments = ["curl", "--disable"], arguments[1:]
        result += ["-H", "X-Egbe-Catalog-Release: " + release]
    return result + arguments


# curl exits that end a request without a complete Egbe response.
CERTIFICATE_EXITS = {35: "TLS handshake failed", 51: "server certificate rejected",
                     58: "client certificate problem", 60: "certificate not trusted"}
UNREACHED_EXITS = {5: "proxy name not resolved", 6: "host name not resolved", 7: "could not connect"}
# These can also stop after Egbe received the request.
INTERRUPTED_EXITS = {28: "timed out", 56: "connection or proxy tunnel failed"}
NETWORK_EXITS = UNREACHED_EXITS | INTERRUPTED_EXITS
ENVIRONMENT_GUIDE = "See the Egbe quickstart's references/environment.md."


def transport_failure(code, host):
    """Why curl's exit code ended a request to host without a complete Egbe response, or None."""
    if code in CERTIFICATE_EXITS:
        return (f"certificate or TLS failure reaching {host} (curl exit {code}: {CERTIFICATE_EXITS[code]}), "
                "so no Egbe response arrived. Usually a sandbox or intercepting proxy, not an Egbe outage "
                f"or a key problem: ask for {host} to be allowed or trusted through this environment's "
                f"network setting; do not disable certificate verification. {ENVIRONMENT_GUIDE}")
    if code in UNREACHED_EXITS:
        return (f"{host} was not reached (curl exit {code}: {UNREACHED_EXITS[code]}), so no Egbe response "
                "arrived. Often this environment's network or proxy setting (a sandbox denial), otherwise "
                f"an Egbe outage; not a key problem: ask once for {host} to be allowed. {ENVIRONMENT_GUIDE}")
    if code in INTERRUPTED_EXITS:
        return (f"the request to {host} ended without a complete Egbe response (curl exit {code}: "
                f"{INTERRUPTED_EXITS[code]}); Egbe may still have processed it, so check its result before "
                "repeating a write. If this recurs before any response, this environment's network or proxy "
                f"setting may need to allow {host}. {ENVIRONMENT_GUIDE}")
    return None


def request_method(arguments):
    """The HTTP method curl uses for these (supported) options."""
    method, head, get, data = None, False, False, False
    index = 0
    while index < len(arguments) and arguments[index] != "--":
        arg = arguments[index]
        option, equals, value = arg.partition("=")
        if option in SUPPORTED_VALUE_OPTIONS:
            if not equals:
                index += 1
                value = arguments[index] if index < len(arguments) else ""
            if option in {"-X", "--request"}:
                method = value.upper()
            data |= option in DATA_OPTIONS
        elif arg == "--head" or (arg.startswith("-") and not arg.startswith("--") and "I" in arg):
            head = True
        elif arg == "--get" or (arg.startswith("-") and not arg.startswith("--") and "G" in arg):
            get = True
        index += 1
    return method or ("HEAD" if head else "GET" if get or not data else "POST")


def responses(headers):
    """(status, request ID) of each final response in a curl header dump."""
    found = []
    for line in headers.splitlines():
        status = re.match(r"HTTP/\S+\s+(\d{3})\b", line)
        if status:
            found.append([status[1], "-"])
            continue
        request_id = re.match(r"(?i)x-egbe-request-id:\s*([A-Za-z0-9-]{1,64})\s*$", line)
        if request_id and found:
            found[-1][1] = request_id[1]
    return [(status, request_id) for status, request_id in found if not status.startswith("1")]


def trailer_release(release):
    """The short form of a catalog release in the trailer: 12 hex digits, `+partial` kept."""
    if not release:
        return "-"
    digest, partial, _ = release.partition("+")
    return digest[:12] + ("+partial" if partial else "")


def trailer(status, request_id, method, url, release=None):
    path = urlsplit(url).path or "/"
    # Quotes and backslashes are encoded too, so the line reads the same inside a JSON string.
    path = re.sub(r'[^\x21-\x7e]|["\\]', lambda match: quote(match[0]), path)[:200]
    return f"egbe-curl: status={status} request_id={request_id} route={method} {path} catalog={trailer_release(release)}"


def run_traced(args, arguments, url):
    """Run curl for one destination, then report its response and fail on an HTTP error status."""
    descriptor, dump = tempfile.mkstemp(prefix="egbe-curl-", suffix=".headers")
    os.close(descriptor)
    try:
        start = 2 if args[1:2] == ["--disable"] else 1
        code = subprocess.run(args[:start] + ["-D", dump] + args[start:]).returncode
        with open(dump, errors="replace") as stream:
            final = responses(stream.read())
    finally:
        os.unlink(dump)
    # Retries or a proxy CONNECT add earlier responses; the last one is the answer.
    status, request_id = final[-1] if final else ("000", "-")
    if code == 0 and int(status) >= 400:
        code = 22  # curl's own --fail exit code; the body was still printed.
    try:
        # Keep the trailer on its own line when the body shares the stream.
        separate = not os.path.samestat(os.fstat(1), os.fstat(2))
    except OSError:
        separate = True
    sys.stdout.flush()
    line = trailer(status, request_id, request_method(arguments), url, catalog_release())
    hint = transport_failure(code, urlsplit(url).hostname)
    if hint:
        line = "egbe-curl: " + hint + "\n" + line
    print(("" if separate else "\n") + line, file=sys.stderr)
    return code


def identity_headers(url, environment):
    """The connection identity and catalog headers an Egbe request to url carries."""
    args = command([url], environment)
    return dict(args[index + 1].split(": ", 1) for index, arg in enumerate(args) if arg == "-H")


def connection_headers(url, settings_file=None):
    try:
        return identity_headers(url, project_environment(settings_file))
    except (ValueError, OSError):
        return {}


def run_git(arguments):
    """Run native Git against an Egbe Git remote with the saved key and this agent's identity.

    Each header reaches Git through `--config-env` scoped to the remote, so the key
    stays out of argv and Git config. Without OS_AGENT_NAME or its saved connection
    ID, Git still runs as an unidentified connection; invalid saved identity is refused."""
    if len(arguments) < 2:
        raise ValueError("--egbe-git requires an Egbe Git remote URL and Git arguments")
    remote, git_arguments = arguments[0], arguments[1:]
    environment = project_environment(saved_credentials=True)
    key = environment.get("OS_API_KEY")
    if not environment.get("OS_URL") or not key:
        raise ValueError("Save OS_URL and OS_API_KEY in the project-local .env.local first")
    base, target = egbe_base(environment), urlsplit(remote)
    if (not is_egbe_url(remote, base) or target.username is not None or target.password is not None
            or target.query or target.fragment or not target.path.startswith(base.path + "/git/http/")):
        raise ValueError("--egbe-git requires a remote under the saved OS_URL's /git/http/")
    agent = environment.get("OS_AGENT_NAME", "")
    if not agent or not environment.get(connection_variable(agent)):
        print("egbe-git: no connection identity (set OS_AGENT_NAME and save its connection ID), so Git runs "
              "as an unidentified connection. See the Egbe quickstart's references/connection.md.", file=sys.stderr)
        environment = {**environment, "OS_AGENT_NAME": ""}
    # A saved but invalid ID or label is refused, as for --egbe-request.
    headers = {"Authorization": "Bearer " + key, **identity_headers(remote, environment)}
    git_environment, options = dict(os.environ), []
    git_environment.setdefault("GIT_TERMINAL_PROMPT", "0")
    for index, (name, value) in enumerate(headers.items()):
        variable = f"EGBE_GIT_HEADER_{index}"
        git_environment[variable] = name + ": " + value
        options.append(f"--config-env=http.{remote}.extraHeader={variable}")
    return subprocess.run(["git", *options, *git_arguments], env=git_environment).returncode


def run_with_settings(arguments):
    """Run a bundled client with the project's saved connection settings in its environment.

    `.env.local` is read without executing it, as with --egbe-request: its URL, key
    and identity replace ambient ones, and the command's other environment is kept."""
    if not arguments:
        raise ValueError("--egbe-run requires a command")
    environment = project_environment(saved_credentials=True)
    if not environment.get("OS_URL") or not environment.get("OS_API_KEY"):
        raise ValueError("Save OS_URL and OS_API_KEY in the project-local .env.local first")
    return subprocess.run(arguments, env=environment).returncode


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--egbe-run":
        try:
            return run_with_settings(sys.argv[2:])
        except (ValueError, OSError):
            print("Could not load valid project connection settings or start the command. Check .env.local and the command.",
                  file=sys.stderr)
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "--egbe-git":
        try:
            return run_git(sys.argv[2:])
        except (ValueError, OSError):
            print("Could not load valid project connection settings or start Git. Check .env.local, the remote "
                  "URL (under the saved OS_URL's /git/http/) and that Git 2.31 or later is installed.", file=sys.stderr)
            return 2
    if len(sys.argv) == 5 and sys.argv[1] == "--identity-headers" and sys.argv[3] == "--env-file":
        print(json.dumps(connection_headers(sys.argv[2], sys.argv[4])))
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "--identity-headers":
        print(json.dumps(connection_headers(sys.argv[2])))
        return 0
    try:
        arguments = sys.argv[1:]
        saved_request = bool(arguments and arguments[0] == "--egbe-request")
        environment = project_environment(saved_credentials=saved_request)
        if saved_request:
            if len(arguments) < 2 or not arguments[1].startswith('/') or arguments[1].startswith('//'):
                raise ValueError("--egbe-request requires an API path beginning with a single slash")
            endpoint, options = arguments[1], arguments[2:]
            destinations, unsupported = curl_destinations(options)
            if destinations or unsupported:
                raise ValueError("Use supported curl options without destinations or redirects with --egbe-request")
            base, key = environment.get("OS_URL"), environment.get("OS_API_KEY")
            if not base or not key:
                raise ValueError("Save OS_URL and OS_API_KEY in the project-local .env.local first")
            arguments = ["--disable", base.rstrip('/') + endpoint, "-H", "Authorization: Bearer " + key, *options]
        args = command(arguments, environment)
        destinations = egbe_destinations(arguments, environment)
    except (ValueError, OSError):
        print("Could not load valid project connection settings or safely attach identity headers. Check .env.local and the Egbe quickstart.", file=sys.stderr)
        return 2
    if len(destinations) == 1:
        # A dump of several transfers cannot be attributed to their URLs once
        # retries or a proxy add responses, so only single requests are traced.
        return run_traced(args, arguments, destinations[0])
    return subprocess.run(args).returncode


if __name__ == "__main__":
    raise SystemExit(main())
