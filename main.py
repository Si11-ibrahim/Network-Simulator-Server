from fastapi import FastAPI, WebSocket
import os
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel
import json

from topologies import StarTopo, RingTopo, CustomTopo, FatTree, PartialMeshTopo, FullMeshTopo, TreeTopo

app = FastAPI()
network = None  # Store the active Mininet network instance

# -------------------- WebSocket Server --------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global network
    await websocket.accept()
    await websocket.send_text('Connection successful...')

    try:
        while True:
            command = await websocket.receive_text()
            print(f"Received: {command}")

            if command.startswith("start:"):
                _, hosts, switches, topology, meshType = command.split(":")
                hosts, switches = int(hosts), int(switches)
                response = await start_mininet(hosts, switches, topology, meshType)
                await websocket.send_json(response)

            elif command == "stop":
                if network:
                    network.stop()
                    network = None
                    await websocket.send_text("Mininet stopped.")
                else:
                    await websocket.send_text("No active Mininet session.")

            elif command.startswith("exec:"):
                cmd = command.split(":")[1].strip()
                print(f'Executing {cmd}...')
                result = await execute_mininet_command(cmd)
                await websocket.send_text(result)

    except Exception as e:
        print(f"Error: {str(e)}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        await websocket.close()


async def start_mininet(hosts_num, switches, topology, meshType):
    global network
    setLogLevel("info")

    try:
        os.system("sudo mn -c")  # Clean previous Mininet sessions

        print(f"Starting Mininet with {hosts_num} hosts, {switches} switches, topology: {topology}")
        
        if topology == "star":
            topo = StarTopo(hosts_num, switches)
        elif topology == "fattree":
            topo = FatTree(hosts_num)
        elif topology == "ring":
            topo = RingTopo(switches)
        elif topology == "mesh":
            if meshType == 'partial':
                topo = PartialMeshTopo(hosts_num)
            else:
                topo = FullMeshTopo(hosts_num)
        elif topology == 'tree':
            topo = TreeTopo(hosts_num)
        elif topology == "custom":
            topo = CustomTopo(hosts_num, switches)
        else:
            return {'message': "Invalid topology", 'status': 'failure'}

        net = Mininet(topo=topo, controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6633))
        net.start()

        topology_data = {
            "hosts": [h.name for h in net.hosts],
            "switches": [s.name for s in net.switches],
            "links": [(link.intf1.node.name, link.intf2.node.name) for link in net.links],
        }

        network = net 

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
            elif cmd.split(' ')[0] == 'ping':
                data = cmd.split(' ') # Eg: ['ping', 'h1', 'h2']
                host1 = network.get(data[1])
                host2 = network.get(data[2])
                result = host1.cmd('ping -c 1 %s' % host2.IP()) # Sending to the ip of the second host
                print(result)
                isSuccessful = '0% packet loss' in result
                if isSuccessful:
                    print(f'ping from {data[1]} to {data[2]} success')
                    return f'ping from {data[1]} to {data[2]} success'
                else:
                    print(f'ping from {data[1]} to {data[2]} failure')
                    return 'ping failure'
                
            else:
                result = network.run(cmd)
                return f"Command output: {result}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    return "No active Mininet session."

# python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload