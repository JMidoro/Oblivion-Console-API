from __future__ import annotations

import uvicorn

from .settings import Settings


def main() -> None:
    settings = Settings.from_environment()
    uvicorn.run(
        "oblivion_bridge.app:app",
        host="127.0.0.1",
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
