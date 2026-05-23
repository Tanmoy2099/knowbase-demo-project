#!/usr/bin/env bash
# wait-for-it.sh — poll a TCP host:port until it accepts connections or timeout.
#
# Usage:
#   wait-for-it.sh HOST:PORT [OPTIONS] [-- COMMAND [ARGS...]]
#   wait-for-it.sh -h | --help
#
# Options:
#   -t, --timeout=SECONDS   Seconds to wait before giving up (default: 60; 0 = no limit)
#   -q, --quiet             Suppress status messages on stderr
#   -s, --strict            Only execute COMMAND if the host is reachable
#   -- COMMAND [ARGS...]    Execute COMMAND with ARGS after the wait
#
# Exit codes:
#   0  Host became reachable within the timeout
#   1  Timeout elapsed before the host became reachable

WAITFORIT_cmdname=$(basename "$0")

WAITFORIT_host=""
WAITFORIT_port=""
WAITFORIT_timeout=60
WAITFORIT_quiet=0
WAITFORIT_strict=0
WAITFORIT_child_pid=0
WAITFORIT_result=0

# ─── helpers ─────────────────────────────────────────────────────────────────

echoerr() {
    if [[ $WAITFORIT_quiet -ne 1 ]]; then
        printf "%s\n" "$*" 1>&2
    fi
}

usage() {
    cat >&2 <<EOF
Usage:
  $WAITFORIT_cmdname HOST:PORT [OPTIONS] [-- COMMAND [ARGS...]]

Wait until a TCP host:port is reachable, then optionally execute a command.

Options:
  -t SECS, --timeout=SECS   Max seconds to wait (default: 60; 0 = unlimited)
  -q,      --quiet          Suppress progress messages
  -s,      --strict         Exit non-zero if host not reached (skips COMMAND)
  -h,      --help           Show this help message

Examples:
  $WAITFORIT_cmdname postgres:5432 --timeout=30
  $WAITFORIT_cmdname postgres:5432 -- alembic upgrade head
EOF
    exit 1
}

# ─── argument parsing ────────────────────────────────────────────────────────

parse_args() {
    # First positional argument must be HOST:PORT (if not a flag)
    if [[ $# -eq 0 ]]; then
        usage
    fi

    local hostport="$1"
    shift

    # Accept HOST:PORT or --host HOST --port PORT style
    if [[ "$hostport" == -* ]]; then
        echoerr "Error: first argument must be HOST:PORT, got: $hostport"
        usage
    fi

    # Split host:port
    if [[ "$hostport" != *:* ]]; then
        echoerr "Error: expected HOST:PORT, got: $hostport"
        usage
    fi

    WAITFORIT_host="${hostport%%:*}"
    WAITFORIT_port="${hostport##*:}"

    if [[ -z "$WAITFORIT_host" || -z "$WAITFORIT_port" ]]; then
        echoerr "Error: HOST and PORT must be non-empty in '$hostport'"
        usage
    fi

    # Parse remaining options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -q | --quiet)
                WAITFORIT_quiet=1
                shift
                ;;
            -s | --strict)
                WAITFORIT_strict=1
                shift
                ;;
            -t)
                WAITFORIT_timeout="$2"
                if [[ -z "$WAITFORIT_timeout" ]]; then
                    echoerr "Error: -t requires an argument"
                    usage
                fi
                shift 2
                ;;
            --timeout=*)
                WAITFORIT_timeout="${1#*=}"
                shift
                ;;
            -h | --help)
                usage
                ;;
            --)
                shift
                WAITFORIT_CLI=("$@")
                break
                ;;
            *)
                echoerr "Unknown option: $1"
                usage
                ;;
        esac
    done

    # Validate timeout is a non-negative integer
    if ! [[ "$WAITFORIT_timeout" =~ ^[0-9]+$ ]]; then
        echoerr "Error: timeout must be a non-negative integer, got: $WAITFORIT_timeout"
        exit 1
    fi
}

# ─── TCP probe via /dev/tcp ───────────────────────────────────────────────────

wait_for() {
    local start_time
    start_time=$(date +%s)
    local elapsed=0

    echoerr "$WAITFORIT_cmdname: waiting for $WAITFORIT_host:$WAITFORIT_port (timeout ${WAITFORIT_timeout}s)"

    while true; do
        # Attempt a TCP connection using bash built-in /dev/tcp
        if (echo > /dev/tcp/"$WAITFORIT_host"/"$WAITFORIT_port") 2>/dev/null; then
            elapsed=$(( $(date +%s) - start_time ))
            echoerr "$WAITFORIT_cmdname: $WAITFORIT_host:$WAITFORIT_port is available after ${elapsed}s"
            return 0
        fi

        elapsed=$(( $(date +%s) - start_time ))

        if [[ $WAITFORIT_timeout -gt 0 && $elapsed -ge $WAITFORIT_timeout ]]; then
            echoerr "$WAITFORIT_cmdname: timeout after ${elapsed}s waiting for $WAITFORIT_host:$WAITFORIT_port"
            return 1
        fi

        echoerr "$WAITFORIT_cmdname: $WAITFORIT_host:$WAITFORIT_port not yet available — retrying in 1s (${elapsed}s elapsed)"
        sleep 1
    done
}

# ─── signal handling ─────────────────────────────────────────────────────────

cleanup() {
    if [[ $WAITFORIT_child_pid -ne 0 ]]; then
        kill "$WAITFORIT_child_pid" 2>/dev/null
        wait "$WAITFORIT_child_pid" 2>/dev/null
    fi
}

trap cleanup INT TERM EXIT

# ─── main ────────────────────────────────────────────────────────────────────

main() {
    parse_args "$@"

    wait_for
    WAITFORIT_result=$?

    if [[ ${#WAITFORIT_CLI[@]} -gt 0 ]]; then
        if [[ $WAITFORIT_result -ne 0 && $WAITFORIT_strict -eq 1 ]]; then
            echoerr "$WAITFORIT_cmdname: strict mode — not executing COMMAND because host was not reachable"
            exit $WAITFORIT_result
        fi
        echoerr "$WAITFORIT_cmdname: executing command: ${WAITFORIT_CLI[*]}"
        exec "${WAITFORIT_CLI[@]}"
    fi

    exit $WAITFORIT_result
}

main "$@"
