import asyncio
import websockets
import json
import logging
from typing import Dict, Set, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebSocketServer")

class WebSocketServer:
    def __init__(self):
        self.clients: Dict[str, Set[websockets.WebSocketServerProtocol]] = {
            "flutter": set(),
            "server": set()
        }

    def print_connections(self):
        """Print current connection status."""
        logger.info("Current WebSocket Connections:")
        for client_type, clients in self.clients.items():
            logger.info(f"{client_type} clients: {len(clients)}")
            for client in clients:
                logger.info(f"  - {client.remote_address}")

    async def register_client(self, websocket, client_type: str):
        """Register a new client connection."""
        self.clients[client_type].add(websocket)
        logger.info(f"New {client_type} client connected. Total {client_type} clients: {len(self.clients[client_type])}")
        self.print_connections()

    async def unregister_client(self, websocket, client_type: str):
        """Unregister a client connection."""
        self.clients[client_type].discard(websocket)
        logger.info(f"{client_type} client disconnected. Remaining {client_type} clients: {len(self.clients[client_type])}")
        self.print_connections()

    async def _send_message(self, websocket, message: Dict[str, Any]):
        """Send a message to a specific client."""
        try:
            await websocket.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed while sending message")

    async def broadcast_to_type(self, message: Dict[str, Any], client_type: str):
        """Broadcast a message to all clients of a specific type."""
        if client_type not in self.clients:
            logger.error(f"Unknown client type: {client_type}")
            return

        disconnected = set()
        for client in self.clients[client_type]:
            try:
                await self._send_message(client, message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)

        # Remove disconnected clients
        for client in disconnected:
            self.clients[client_type].discard(client)

    async def handle_client(self, websocket, path: str):
        """Handle a new client connection."""
        try:
            # Extract client type from path (e.g., /ws/flutter or /ws/server)
            client_type = path.split('/')[-1]
            if client_type not in self.clients:
                logger.error(f"Invalid client type: {client_type}")
                return

            await self.register_client(websocket, client_type)

            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        # Route message to the other client type
                        target_type = "server" if client_type == "flutter" else "flutter"
                        await self.broadcast_to_type(data, target_type)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received from {client_type} client")
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"{client_type} client connection closed normally")
            finally:
                await self.unregister_client(websocket, client_type)
        except Exception as e:
            logger.error(f"Error handling client: {e}")

async def main():
    server = WebSocketServer()
    
    # Create a handler function that matches the expected signature
    async def handler(websocket):
        # Get the path from the websocket's request path
        path = websocket.request.path
        await server.handle_client(websocket, path)
    
    async with websockets.serve(handler, "localhost", 8765):
        logger.info("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main()) 