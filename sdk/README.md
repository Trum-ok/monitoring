# monitor-sdk

Python SDK for sending exceptions to monitor-service.

## Install

From GitHub repository:

```bash
pip install "git+https://github.com/<ORG>/<REPO>.git#subdirectory=sdk"
```

Pin to release tag:

```bash
pip install "git+https://github.com/<ORG>/<REPO>.git@sdk-v0.1.1#subdirectory=sdk"
```

From local source:

```bash
pip install .
```

## Usage

```python
import monitor_sdk

monitor_sdk.init(
    dsn="http://localhost:8000",
    service_name="my-service",
)
```

After initialization, SDK hooks `sys.excepthook` and current `asyncio` loop exception handler,  
and sends exceptions to `POST /api/errors`.