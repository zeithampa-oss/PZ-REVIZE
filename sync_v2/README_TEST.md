# Test SYNC 2.0

This package is a protocol test client, not yet the production PZ-REVIZE application.

On Windows with Python installed:

```text
python demo_app.py add job TEST-001
python demo_app.py sync
```

The client creates a local SQLite outbox and retries safely. The server endpoint must implement `/sync/v2/batch` according to `PROTOCOL.md`.

For the real PZ-REVIZE test build, the next integration step is to connect the production SQLite entities and the existing NAS API to this protocol, then build Windows EXE and Android APK.
