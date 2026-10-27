#!/usr/bin/env bash
# One-click demo (macOS/Linux). Run from the repository root.
set -e

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install -q -r requirements-demo.txt

find_free_port() {
    local port="$1"
    local limit=$((port + 100))
    while [ "$port" -lt "$limit" ] && [ "$port" -le 65535 ]; do
        if .venv/bin/python -c 'import socket,sys; s=socket.socket(); s.bind(("127.0.0.1", int(sys.argv[1]))); s.close()' "$port" >/dev/null 2>&1; then
            printf '%s\n' "$port"
            return 0
        fi
        port=$((port + 1))
    done
    echo "No free local port found starting at $1." >&2
    return 1
}

API_PORT=$(find_free_port "${CARECONNECT_API_PORT:-8001}")
STREAMLIT_PORT=$(find_free_port "${CARECONNECT_STREAMLIT_PORT:-8501}")
export FASTAPI_ENDPOINT="http://127.0.0.1:$API_PORT"

.venv/bin/python -m uvicorn main:app --app-dir fastapi --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
cleanup() {
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

API_READY=0
ATTEMPT=0
while [ "$ATTEMPT" -lt 30 ]; do
    if .venv/bin/python -c 'import sys,urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1)' "$FASTAPI_ENDPOINT/openapi.json" >/dev/null 2>&1; then
        API_READY=1
        break
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "FastAPI stopped during startup." >&2
        exit 1
    fi
    sleep 1
    ATTEMPT=$((ATTEMPT + 1))
done
if [ "$API_READY" -ne 1 ]; then
    echo "FastAPI did not become ready at $FASTAPI_ENDPOINT." >&2
    exit 1
fi

echo "CareConnect API is ready at $FASTAPI_ENDPOINT"
echo "Open the app at http://127.0.0.1:$STREAMLIT_PORT"
cd Streamlit
../.venv/bin/python -m streamlit run Home.py --server.address 127.0.0.1 --server.port "$STREAMLIT_PORT" --server.headless true --browser.gatherUsageStats false
