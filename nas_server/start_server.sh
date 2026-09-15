#!/bin/sh
cd "$(dirname "$0")"
exec python3 -m uvicorn main:APP --host 0.0.0.0 --port 8767
