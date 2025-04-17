from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import os
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel
from db.command_db import command_db

from topologies import StarTopo, RingTopo, CustomTopo, FatTree, PartialMeshTopo, FullMeshTopo, TreeTopo
import time
from datetime import datetime

app = FastAPI()
network = None  # Store the active Mininet network instance
connected_clients = []
last_broadcast_time = {}
last_data_received = datetime.now()  # Initialize with current time
BROADCAST_COOLDOWN = 3.0  # seconds

# -------------------- WebSocket Server --------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global network
    await websocket.accept()
    connected_clients.append(websocket)
    await websocket.send_text("Connection successful...")

    try:
        while True:
            command = await websocket.receive_text()
            print(f"Received: {command}")

            if command.startswith("start:"):
                _, hosts_num, topology, meshType = command.split(":")
                hosts = int(hosts_num)
                response = await start_mininet(hosts, topology, meshType)
                await websocket.send_json(response)

            elif command == "stop":
                if network:
                    network = None
                    await websocket.send_json({"message": "Mininet stopped.", "type": "message"})
                else:
                    await websocket.send_json({"message": "No active Mininet session.", "type": "message"})

            elif command.startswith("exec:"):
                cmd = command.split(":")[1].strip()
                print(f"Executing {cmd}...")
                result = await execute_mininet_command(cmd)
                await websocket.send_json(result)

    except WebSocketDisconnect:
        # Handle normal disconnection gracefully
        connected_clients.remove(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {str(e)}")
        try:
            await websocket.send_json({"message": f"Error: {str(e)}", "type": "message"})
        except RuntimeError:
            # If we can't send because the connection is already closed, just log it
            print("Could not send error message - connection already closed")

        if websocket in connected_clients:
            connected_clients.remove(websocket)

@app.head("/path-data")
async def head_path_data():
    # This simply allows HEAD requests to check if the endpoint is available
    return {}

@app.post("/path-data")
async def receive_path_data(data: dict):
    global last_data_received
    print(f"Received path data: {data}")
    
    # Update last data received timestamp
    last_data_received = datetime.now()
    
    # Add a message type for the Flutter app to recognize
    data["type"] = "path_data"
    
    # Log the data being broadcasted
    print(f"Broadcasting path data: {data}")
    
    # Use rate-limited broadcast
    broadcast_sent = await rate_limited_broadcast(data)
    
    if broadcast_sent:
        print(f"Successfully broadcasted path data to clients")
    else:
        print(f"Path data broadcast was rate-limited")
    
    return {"status": "success", "broadcast_sent": broadcast_sent}

async def start_mininet(hosts_num, topology, meshType):
    global network
    setLogLevel("info")

    try:
        os.system("sudo mn -c")  # Clean previous Mininet sessions

        print(f"Starting Mininet with {hosts_num} hosts, topology: {topology}")
        
        if topology == "star":
            topo = StarTopo(hosts_num)
        elif topology == "fattree":
            topo = FatTree(hosts_num)
        elif topology == "ring":
            topo = RingTopo(hosts_num)
        elif topology == "mesh":
            if meshType == "partial":
                topo = PartialMeshTopo(hosts_num)
            else:
                topo = FullMeshTopo(hosts_num)
        elif topology == "tree":
            topo = TreeTopo(hosts_num)
        elif topology == "custom":
            topo = CustomTopo(hosts_num, switches)
        else:
            return {"message": "Invalid topology", "status": "failed"}

        net = Mininet(topo=topo, controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6633))
        net.start()

        topology_data = {
            "hosts": [h.name for h in net.hosts],
            "switches": [s.name for s in net.switches],
            "links": [(link.intf1.node.name, link.intf2.node.name) for link in net.links],
        }

        network = net

        return {"message": "Mininet started successfully!", "topology": topology_data, "status": "success"}

    except Exception as e: # Type: "mininet"
        return {"message": f"Error starting Mininet: {str(e)}", "status": "error", "type": "mininet"}


async def execute_mininet_command(cmd):
    global network
    if network:
        try:
            print(f"Executing command: {cmd}")
            # Determine command type
            command_type = None
            if cmd == "pingall":
                command_type = "pingall"
            elif cmd.startswith("ping"):
                command_type = "ping"
            elif cmd == "dump" or cmd == "net":
                command_type = "topology"
            elif "ifconfig" in cmd:
                command_type = "ifconfig"
            elif "logs" in cmd:
                command_type = "logs"
            else:
                command_type = "command"

            # Add command to database with type
            try:
                command_data = {
                    "command": cmd,
                    "source": "mininet",
                    "type": command_type,
                    "status": "pending",
                    "timestamp": datetime.now().isoformat()
                }
                # Add command and get its ID
                command_id = command_db.add_command(command_data)
                if not command_id:
                    raise Exception("Failed to add command to database")
                command_data["id"] = command_id
                print(f"Added command to database with ID: {command_id} and type: {command_type}")
            except Exception as e:
                print(f"Error adding command to database: {e}")
                return {"message": f"Error adding command to database: {e}", "status": "error"}
            
            if cmd == "pingall":
                print("Executing pingall command...")
                result = network.pingAll()
                # Update command status
                try:
                    command_db.update_command_status(
                        command_id,
                        "completed",
                        {"result": result}
                    )
                    print(f"Updated pingall command status to completed")
                except Exception as e:
                    print(f"Error updating pingall command status: {e}")
                return {"message": f"PingAll output: {result}", "result": result, "status": "success", "type": "pingall"}
            elif cmd.startswith("ping"):
                # Split the command and handle different formats
                parts = cmd.split()
                if len(parts) < 3:
                    return {"message": "Invalid ping command format. Use: ping <host1> <host2>", "status": "error"}
                
                host1_name = parts[1]
                host2_name = parts[2]
                
                print(f"Attempting to ping from {host1_name} to {host2_name}")
                
                try:
                    host1 = network.get(host1_name)
                    host2 = network.get(host2_name)
                    
                    if not host1 or not host2:
                        error_msg = f"Host not found: {host1_name if not host1 else host2_name}"
                        print(error_msg)
                        try:
                            command_db.update_command_status(
                                command_id,
                                "error",
                                {"error": error_msg}
                            )
                        except Exception as e:
                            print(f"Error updating command status: {e}")
                        return {"message": error_msg, "status": "error"}
                    
                    print(f"Host1 IP: {host1.IP()}, Host2 IP: {host2.IP()}")
                    result = host1.cmd(f"ping -c 1 {host2.IP()}")
                    print(f"Ping result: {result}")
                    
                    isSuccessful = "0% packet loss" in result
                    
                    # Update command status
                    try:
                        command_db.update_command_status(
                            command_id,
                            "completed",
                            {
                                "result": result,
                                "success": isSuccessful,
                                "source": host1_name,
                                "destination": host2_name
                            }
                        )
                        print(f"Updated ping command status to completed")
                    except Exception as e:
                        print(f"Error updating ping command status: {e}")
                    
                    if isSuccessful:
                        return {
                            "message": f"ping from {host1_name} to {host2_name} success",
                            "source": host1_name,
                            "destination": host2_name,
                            "result": result,
                            "status": "success",
                            "type": "ping"
                        }
                    else:
                        return {
                            "message": f"ping from {host1_name} to {host2_name} failed",
                            "source": host1_name,
                            "destination": host2_name,
                            "result": result,
                            "status": "failed",
                            "type": "ping"
                        }
                except Exception as e:
                    error_msg = f"Error executing ping: {str(e)}"
                    print(error_msg)
                    try:
                        command_db.update_command_status(
                            command_id,
                            "error",
                            {"error": error_msg}
                        )
                    except Exception as e:
                        print(f"Error updating command status: {e}")
                    return {"message": error_msg, "status": "error"}
            elif cmd == 'dump':
                # Get network topology information
                hosts = [h.name for h in network.hosts]
                switches = [s.name for s in network.switches]
                links = [(link.intf1.node.name, link.intf2.node.name) for link in network.links]
                
                # Format the dump output
                dump_output = "Network Topology Information:\n\n"
                dump_output += "Hosts:\n"
                for host in hosts:
                    dump_output += f"- {host}\n"
                
                dump_output += "\nSwitches:\n"
                for switch in switches:
                    dump_output += f"- {switch}\n"
                
                dump_output += "\nLinks:\n"
                for link in links:
                    dump_output += f"- {link[0]} <-> {link[1]}\n"
                
                print(dump_output)
                return {
                    "message": "Network topology information retrieved",
                    "result": dump_output,
                    "status": "success",
                    "type": "topology"
                }
            elif cmd == 'net':
                # Get network topology information
                links = [(link.intf1.node.name, link.intf2.node.name) for link in network.links]
                
                # Format the net output
                net_output = "Network Links:\n"
                for link in links:
                    net_output += f"- {link[0]} <-> {link[1]}\n"
                
                print(net_output)
                return {
                    "message": "Network topology information retrieved",
                    "result": net_output,
                    "status": "success",
                    "type": "topology"
                }
            elif cmd.split(' ')[1] == 'ifconfig':
                h = cmd.split(' ')[0]
                host = network.get(h)
                result = host.cmd('ifconfig')
                print(result)
                return {
                    "message": f"ifconfig output: {result}",
                    "host": h, 
                    "result": result, 
                    "status": "success", 
                    "type": "ifconfig"
                }
            elif cmd.split(' ')[1] == 'logs':
                h = cmd.split(' ')[0]
                host = network.get(h)
                # Get system logs with timestamp and process information
                result = host.cmd('dmesg | tail -n 20')
                print(result)
                return {
                    "message": f"System logs retrieved for {h}",
                    "host": h,
                    "result": result,
                    "status": "success",
                    "type": "logs"
                }
            else:
                result = network.run(cmd)
                # Update command status
                command_db.update_command_status(
                    command_id,
                    "completed",
                    {"result": result}
                )
                return {"message": f"Command output: {result}", "status": "success", "type": "command"}
        except Exception as e:
            # Update command status with error
            command_db.update_command_status(
                command_id,
                "error",
                {"error": str(e)}
            )
            return {"message": f"Error executing command: {str(e)}", "status": "error", "type": "command"}
    return {"message": "No active Mininet session.", "type": "message"}

# python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

async def broadcast_to_clients(message: dict):
    """Send message to all connected WebSocket clients."""
    # Create a copy of the list to avoid issues if it changes during iteration
    clients = connected_clients.copy()
    
    for client in clients:
        try:
            print(f"Sending message to client: {message}")
            await client.send_json(message)
        except Exception as e:
            print(f"Error broadcasting to client: {e}")
            # Client might be disconnected but not properly removed
            if client in connected_clients:
                connected_clients.remove(client)

async def rate_limited_broadcast(data: dict):
    """Broadcast with rate limiting based on source/destination pair"""
    path_key = f"{data['src']}-{data['dst']}"
    current_time = time.time()
    
    # Only broadcast if enough time has passed since last broadcast for this path
    if path_key not in last_broadcast_time or (current_time - last_broadcast_time[path_key]) >= BROADCAST_COOLDOWN:
        last_broadcast_time[path_key] = current_time
        print(f"Broadcasting to {len(connected_clients)} connected clients")
        await broadcast_to_clients(data)
        return True
    else:
        print(f"Rate limiting path data for {path_key}")
        return False