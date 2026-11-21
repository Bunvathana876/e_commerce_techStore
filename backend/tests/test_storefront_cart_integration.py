"""Exercise the actual TypeScript client/store against the isolated FastAPI app."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

import pytest
import uvicorn

from app.db.database import engine
from app.main import app


def test_storefront_cart_against_isolated_api(headers):
    node = shutil.which("node")
    storefront = Path(__file__).resolve().parents[2] / "storefront"
    if not node or not (storefront / "node_modules/zustand").is_dir():
        pytest.skip("Cross-stack test requires Node and installed storefront dependencies.")

    # conftest configures the database before app imports; never serve normal settings here.
    assert engine.url.get_backend_name() == "sqlite"
    assert Path(engine.url.database).parent.name.startswith("blue-panda-tests-")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started, "Isolated API did not start"
        env = {
            **os.environ,
            "NEXT_PUBLIC_API_URL": f"http://127.0.0.1:{port}/api",
            "BLUE_PANDA_TEST_TOKEN": headers(2)["Authorization"].removeprefix("Bearer "),
            "BLUE_PANDA_OTHER_TEST_TOKEN": headers(3)["Authorization"].removeprefix("Bearer "),
        }
        result = subprocess.run(
            [node, "--import", "./src/lib/__tests__/ts-resolver.mjs",
             "--test", "tests/cart-api.integration.mjs"],
            cwd=storefront, env=env, capture_output=True, text=True, timeout=45,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
    assert not thread.is_alive(), "Isolated API did not stop"
