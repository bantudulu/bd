"""Start uvicorn with SO_REUSEADDR socket for Windows TIME_WAIT bypass."""
import socket
import uvicorn

# Pre-bind socket with SO_REUSEADDR
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', 8083))
sock.listen(2048)

# Use uvicorn's Config with fd - override AF_UNIX check by passing socket directly
from uvicorn.config import Config
from uvicorn.server import Server

config = Config(
    app="app.main:app",
    host="0.0.0.0",
    port=8083,
    log_level="info",
)
# Bypass uvicorn's own socket creation by pre-binding
server = Server(config)
server.servers = []  # Clear auto-created servers
# Inject our socket directly
import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
server.servers.append(sock)
server.run()
