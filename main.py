from fastapi import FastAPI, WebSocket
import os
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel
import json

from topologies import StarTopo, RingTopo, CustomTopo, FatTree, PartialMeshTopo

app = FastAPI()
network = None  # Store the active Mininet network instance

# -------------------- WebSocket Server --------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global network
    await websocket.accept()

    try:
        while True:
            command = await websocket.receive_text()
            print(f"Received command: {command}")

            if command.startswith("start:"):
                _, hosts, switches, topology = command.split(":")
                hosts, switches = int(hosts), int(switches)
                response = await start_mininet(hosts, switches, topology)
                await websocket.send_json(response)

            elif command == "stop":
                if network:
                    network.stop()
                    network = None
                    await websocket.send_text("Mininet stopped.")
                else:
                    await websocket.send_text("No active Mininet session.")

            elif command.startswith("exec:"):
                cmd = command.split("exec:")[1].strip()
                result = await execute_mininet_command(cmd)
                await websocket.send_text(result)

    except Exception as e:
        print(f"Error: {str(e)}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        await websocket.close()


async def start_mininet(hosts, switches, topology):
    global network
    setLogLevel("info")

    try:
        os.system("sudo mn -c")  # Clean previous Mininet sessions

        print(f"Starting Mininet with {hosts} hosts, {switches} switches, topology: {topology}")
        
        if topology == "star":
            topo = StarTopo(hosts, switches)
        elif topology == "fattree":
            topo = FatTree(hosts)
        elif topology == "ring":
            topo = RingTopo(switches)
        elif topology == "mesh":
            topo = PartialMeshTopo(hosts)
        elif topology == "custom":
            topo = CustomTopo(hosts, switches)
        else:
            return {'message': "Invalid topology", 'status': 'failure'}

        net = Mininet(topo=topo, controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6633))
        net.start()

        topology_data = {
            "hosts": [h.name for h in net.hosts],
            "switches": [s.name for s in net.switches],
            "links": [(link.intf1.node.name, link.intf2.node.name) for link in net.links],
        }

        network = net  # Store the Mininet instance

        return {"message": "Mininet started successfully!", "topology": topology_data, "status": "success"}

    except Exception as e:
        return {'message': f"Error starting Mininet: {str(e)}", 'status': 'error'}


async def execute_mininet_command(cmd):
    global network
    if network:
        try:
            if cmd == 'pingall':
                result = network.pingAll()
                return f"PingAll output: {result}"
            else:
                result = network.run(cmd)
                return f"Command output: {result}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    return "No active Mininet session."

# python3 -m uvicorn main:app --reload