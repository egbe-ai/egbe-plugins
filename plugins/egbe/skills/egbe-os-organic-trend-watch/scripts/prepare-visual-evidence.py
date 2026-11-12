#!/usr/bin/env python3
"""Download provider media and extract canonical opening/middle/end frames."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

from _contract import (
    ContractError,
    atomic_write_json,
    read_json,
    sha256_bytes,
    sha256_file,
    VISUAL_EVIDENCE_METHOD,
    canonical_frame_seconds,
)


DEFAULT_MAX_TOTAL_BYTES = 1024 * 1024 * 1024


def _resolve_public_target(
    value: object,
) -> tuple[str, urllib.parse.ParseResult, int, tuple]:
    if not isinstance(value, str) or not value:
        raise ContractError("observation has no provider media URL")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ContractError("provider media URL must be HTTP(S)")
    if parsed.username is not None or parsed.password is not None:
        raise ContractError("provider media URL cannot contain credentials")
    host = parsed.hostname.casefold()
    if host in {"localhost", "localhost.localdomain"}:
        raise ContractError("provider media URL cannot target localhost")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ContractError(f"cannot resolve provider media host: {host}") from exc
    if not addresses:
        raise ContractError(f"cannot resolve provider media host: {host}")
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise ContractError("provider media URL resolved to a non-public address")
    family, _, _, _, sockaddr = addresses[0]
    return value, parsed, family, sockaddr


def _open_pinned(
    parsed: urllib.parse.ParseResult,
    family: int,
    sockaddr: tuple,
    *,
    timeout: float,
) -> tuple[http.client.HTTPResponse, socket.socket]:
    raw_socket = socket.socket(family, socket.SOCK_STREAM)
    raw_socket.settimeout(timeout)
    try:
        raw_socket.connect(sockaddr)
        connection: socket.socket
        if parsed.scheme == "https":
            connection = ssl.create_default_context().wrap_socket(
                raw_socket,
                server_hostname=parsed.hostname,
            )
        else:
            connection = raw_socket
        default_port = 443 if parsed.scheme == "https" else 80
        port = parsed.port or default_port
        host = parsed.hostname or ""
        host_header = f"[{host}]" if ":" in host else host
        if port != default_port:
            host_header += f":{port}"
        target = urllib.parse.urlunparse(("", "", parsed.path or "/", "", parsed.query, ""))
        request = (
            f"GET {target} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "User-Agent: EgbeOrganicTrendWatch/1\r\n"
            "Accept: */*\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        connection.sendall(request)
        response = http.client.HTTPResponse(connection)
        response.begin()
        return response, connection
    except Exception:
        raw_socket.close()
        raise


def _download(
    url: str,
    destination: Path,
    max_bytes: int,
    *,
    deadline: float,
) -> None:
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        current_url = url
        for redirect_count in range(6):
            _, parsed, family, sockaddr = _resolve_public_target(current_url)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ContractError("media preparation exceeded its total deadline")
            response, connection = _open_pinned(
                parsed,
                family,
                sockaddr,
                timeout=min(60, remaining),
            )
            try:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        raise ContractError("provider media redirect has no Location")
                    if redirect_count == 5:
                        raise ContractError("provider media exceeded five redirects")
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue
                if not 200 <= response.status < 300:
                    raise ContractError(
                        f"provider media returned HTTP {response.status}"
                    )
                with temporary.open("wb") as output:
                    total = 0
                    while True:
                        if time.monotonic() >= deadline:
                            raise ContractError(
                                "media preparation exceeded its total deadline"
                            )
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise ContractError(f"provider media exceeds {max_bytes} bytes")
                        output.write(chunk)
                break
            finally:
                response.close()
                connection.close()
        if temporary.stat().st_size == 0:
            raise ContractError("provider media download is empty")
        temporary.replace(destination)
    except (ContractError, urllib.error.URLError, OSError):
        temporary.unlink(missing_ok=True)
        raise


def _safe_name(observation_id: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in observation_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--observation-id", required=True)
    parser.add_argument("--max-bytes", type=int, default=250 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--total-timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    normalized_path = root / "normalized/videos.json"
    prior_alarm_handler = signal.getsignal(signal.SIGALRM)
    try:
        if not 1 <= args.max_bytes <= 500 * 1024 * 1024:
            raise ContractError("max-bytes must be between 1 and 524288000")
        if not args.max_bytes <= args.max_total_bytes <= 5 * 1024 * 1024 * 1024:
            raise ContractError(
                "max-total-bytes must be at least max-bytes and no more than 5368709120"
            )
        if not 30 <= args.total_timeout_seconds <= 900:
            raise ContractError("total timeout must be between 30 and 900 seconds")
        deadline = time.monotonic() + args.total_timeout_seconds
        def _deadline_exceeded(_signum, _frame):
            raise ContractError("media preparation exceeded its total deadline")

        signal.signal(signal.SIGALRM, _deadline_exceeded)
        signal.setitimer(signal.ITIMER_REAL, args.total_timeout_seconds)
        payload = read_json(normalized_path)
        videos = payload.get("videos")
        if not isinstance(videos, list):
            raise ContractError("normalized videos must be a list")
        matches = [video for video in videos if video.get("observation_id") == args.observation_id]
        if len(matches) != 1:
            raise ContractError("observation ID must identify exactly one normalized video")
        video = matches[0]
        evidence = video.get("evidence")
        if not isinstance(evidence, dict):
            raise ContractError("normalized observation evidence must be an object")
        recorded_hashes = evidence.get("artifact_sha256")
        if not isinstance(recorded_hashes, dict):
            raise ContractError("normalized evidence has no artifact hash map")
        media_url = evidence.get("media_url")
        if not isinstance(media_url, str) or not media_url:
            raise ContractError("observation has no provider media URL")
        stem = _safe_name(args.observation_id)
        media_dir = root / "media"
        frames_dir = root / "frames"
        media_dir.mkdir(parents=True, exist_ok=True)
        frames_dir.mkdir(parents=True, exist_ok=True)
        media_path = media_dir / f"{stem}.mp4"
        media_relative = media_path.relative_to(root).as_posix()
        existing_other_media_bytes = sum(
            candidate.stat().st_size
            for candidate in media_dir.iterdir()
            if candidate != media_path and candidate.is_file() and not candidate.is_symlink()
        )
        remaining_media_bytes = args.max_total_bytes - existing_other_media_bytes
        if remaining_media_bytes <= 0:
            raise ContractError("aggregate media budget is exhausted")
        media_is_trusted = (
            media_path.is_file()
            and not media_path.is_symlink()
            and recorded_hashes.get(media_relative) == sha256_file(media_path)
        )
        if not media_is_trusted:
            _download(
                media_url,
                media_path,
                min(args.max_bytes, remaining_media_bytes),
                deadline=deadline,
            )
        media_replaced = not media_is_trusted
        if existing_other_media_bytes + media_path.stat().st_size > args.max_total_bytes:
            if media_replaced:
                media_path.unlink(missing_ok=True)
            raise ContractError("aggregate media budget exceeded")

        duration = video.get("metrics", {}).get("duration_seconds")
        frame_paths: list[str] = []
        frame_samples: list[dict[str, object]] = []
        for second in canonical_frame_seconds(duration):
            milliseconds = int(second * 1000)
            frame_path = frames_dir / f"{stem}-{milliseconds:04d}ms.jpg"
            frame_relative = frame_path.relative_to(root).as_posix()
            frame_is_trusted = (
                not media_replaced
                and frame_path.is_file()
                and recorded_hashes.get(frame_relative) == sha256_file(frame_path)
            )
            if not frame_is_trusted:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ContractError("media preparation exceeded its total deadline")
                command = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    str(second),
                    "-i",
                    str(media_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    "-y",
                    str(frame_path),
                ]
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=min(60, remaining),
                )
                if result.returncode != 0:
                    frame_path.unlink(missing_ok=True)
                    continue
            if frame_path.is_file() and frame_path.stat().st_size > 0:
                frame_paths.append(frame_relative)
                frame_samples.append({"path": frame_relative, "second": second})
        if not frame_paths:
            raise ContractError("ffmpeg produced no inspectable frames")
        evidence["video_path"] = media_relative
        evidence["frame_paths"] = frame_paths
        evidence["visual_preparation"] = {
            "method": VISUAL_EVIDENCE_METHOD,
            "source_media_url_sha256": sha256_bytes(media_url.encode("utf-8")),
            "video_path": media_relative,
            "frame_samples": frame_samples,
        }
        evidence["artifact_sha256"] = {
            relative: sha256_file(root / relative)
            for relative in [evidence["video_path"], *frame_paths]
        }
        atomic_write_json(normalized_path, payload)
    except (
        ContractError,
        OSError,
        UnicodeDecodeError,
        urllib.error.URLError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(f"could not prepare visual evidence: {exc}", file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior_alarm_handler)
    print(f"prepared {len(frame_paths)} frames for {args.observation_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
