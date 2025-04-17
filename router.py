from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.icmp import icmp
from pox.lib.packet.arp import arp
from pox.lib.addresses import EthAddr, IPAddr
import time
import heapq
import json
from collections import defaultdict
import requests
from requests.exceptions import RequestException, ConnectionError
import sys
import os

# Add the server directory to Python path
server_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(server_dir)


from db.command_db import command_db

log = core.getLogger()

# FastAPI integration for sending data
FASTAPI_URL = "http://127.0.0.1:8000/path-data"
fastapi_available = False  # Flag to track if FastAPI server is available
FASTAPI_RETRY_INTERVAL = 5  # Seconds between FastAPI connection retries
MAX_FASTAPI_RETRIES = 3  # Maximum number of retries for FastAPI connection
STARTUP_DELAY = 10  # Seconds to wait before first connection attempt

# Data structures for topology and path tracking
adjacency_list = defaultdict(dict)  # { switch: {neighbor: cost, ...}, ... }
path_table = {}  # Caches shortest paths for faster forwarding
host_to_switch = {}  # Stores {host_ip: switch_dpid}
mac_to_port = {}  # Stores {mac: (switch_dpid, port)}
dpid_to_name = {}  # Maps switch DPIDs to human-readable names
ip_to_name = {}  # Map IP addresses to human-readable host names (h1, h2, etc.)
host_movement_count = {}  # Track host movement detections
host_movement_time = {}  # Track last movement time for each host
MOVEMENT_COOLDOWN = 5  # Cooldown period in seconds
MIN_MOVEMENT_DETECTIONS = 5  # Number of detections required to confirm movement

# Add these at the top with other global variables
SWITCH_RECONNECT_TIMEOUT = 10  # Seconds to wait before considering a switch disconnected
switch_last_seen = {}  # Track last seen time for each switch

# Add ip_to_mac mapping dictionary near the top with other global variables
ip_to_mac = {} # Stores {ip_address: mac_address}

# Near the top of the file, add these variables
LOG_RATE_LIMIT = {}  # Track last log time for rate-limited logs
LOG_RATE_INTERVAL = 5  # Seconds between rate-limited logs

def rate_limited_log(logger, level, message, rate_key, interval=LOG_RATE_INTERVAL):
    """Log a message, but rate-limit to avoid spam."""
    current_time = time.time()
    if rate_key not in LOG_RATE_LIMIT or current_time - LOG_RATE_LIMIT[rate_key] > interval:
        if level == "info":
            logger.info(message)
        elif level == "debug":
            logger.debug(message)
        elif level == "warning":
            logger.warning(message)
        LOG_RATE_LIMIT[rate_key] = current_time

def check_fastapi_connection():
    """Verify if the FastAPI server is available with improved retry logic."""
    global fastapi_available
    try:
        # Add a small delay before checking connection
        time.sleep(1)
        response = requests.head(FASTAPI_URL, timeout=2)
        if response.status_code < 400:
            fastapi_available = True
            log.info(f"Connected to FastAPI server at {FASTAPI_URL}")
            return True
        else:
            fastapi_available = False
            log.warning(f"FastAPI server returned status code {response.status_code}")
            return False
    except (RequestException, ConnectionError) as e:
        fastapi_available = False
        log.warning(f"Failed to connect to FastAPI server: {e}")
        # Schedule a retry
        from pox.lib.recoco import Timer
        Timer(FASTAPI_RETRY_INTERVAL, check_fastapi_connection)
        return False

def dijkstra(src, dst):
    """Find the shortest path between switches using Dijkstra's algorithm."""
    if src not in adjacency_list or dst not in adjacency_list:
        log.warning(f"Dijkstra: Source {src} or destination {dst} not in adjacency list")
        return []

    pq = [(0, src, [])]  # (cost, current switch, path)
    visited = set()
    distances = {src: 0}

    while pq:
        cost, node, path = heapq.heappop(pq)
        if node in visited:
            continue
        path = path + [node]
        if node == dst:
            log.info(f"Dijkstra: Found path from {src} to {dst}: {path}")
            return path
        visited.add(node)

        for neighbor, port in adjacency_list[node].items():
            if neighbor not in visited:
                neighbor_cost = cost + 1  # Use default cost of 1 per hop
                if neighbor not in distances or neighbor_cost < distances[neighbor]:
                    distances[neighbor] = neighbor_cost
                    heapq.heappush(pq, (neighbor_cost, neighbor, path))

    log.warning(f"Dijkstra: No path found from {src} to {dst}")
    return []

def send_path_data(packet_type, src_host, dst_host, path, ttl=None, time_ms=None):
    """Send path data to the FastAPI endpoint."""
    global fastapi_available
    
    log.info(f"Starting send_path_data: type={packet_type}, src={src_host}, dst={dst_host}")
    log.info(f"Path: {path}, ttl={ttl}, time_ms={time_ms}")
    
    # Convert DPIDs to names
    named_path = []
    named_path.append(src_host)  # Add source host
    
    # Add switch DPIDs (convert to names if available)
    for dpid in path:
        switch_name = dpid_to_name.get(dpid, f"s{dpid}")
        named_path.append(switch_name)
    
    named_path.append(dst_host)  # Add destination host
    
    data = {
        "type": packet_type,
        "src": src_host,
        "dst": dst_host,
        "time": time_ms if time_ms is not None else 0,
        "ttl": ttl if ttl is not None else 64,
        "path": named_path,
        "direction": "src_to_dst"
    }
    
    log.info(f"Preparing to send path data: {json.dumps(data)}")
    
    def _send_to_fastapi():
        global fastapi_available
        max_retries = MAX_FASTAPI_RETRIES
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                if not fastapi_available:
                    log.info("FastAPI server not available, attempting to reconnect...")
                    if check_fastapi_connection():
                        log.info("Reconnected to FastAPI server")
                    else:
                        log.warning(f"Failed to reconnect to FastAPI server (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                
                log.info(f"Sending path data to FastAPI server (attempt {attempt + 1}/{max_retries})")
                response = requests.post(FASTAPI_URL, json=data, timeout=2)
                if response.status_code == 200:
                    log.info(f"Successfully sent path data to {FASTAPI_URL}")
                    return True
                else:
                    log.warning(f"Failed to send path data: HTTP {response.status_code}")
                    fastapi_available = False
                    time.sleep(retry_delay)
            except requests.exceptions.Timeout:
                log.warning(f"Timeout sending path data (attempt {attempt + 1}/{max_retries})")
                fastapi_available = False
                time.sleep(retry_delay)
            except requests.exceptions.RequestException as e:
                log.warning(f"Error sending path data: {e}")
                fastapi_available = False
                time.sleep(retry_delay)
        
        log.warning("Failed to send path data after all retries")
        return False
    
    # Use a timer to send the data asynchronously
    from pox.lib.recoco import Timer
    Timer(0.1, _send_to_fastapi)
    return True

def install_path_flows(connection, packet, path):
    """Install flow rules for the given path."""
    # Get the current switch
    current_switch = connection.dpid
    
    # Find the next hop in the path
    current_index = path.index(current_switch)
    if current_index < len(path) - 1:
        next_switch = path[current_index + 1]
        out_port = adjacency_list[current_switch][next_switch]
                
        # Install the forwarding rule
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.actions.append(of.ofp_action_output(port=out_port))
        msg.idle_timeout = 10  # Flow expires after 10 seconds of inactivity
        msg.hard_timeout = 30  # Flow expires after 30 seconds regardless
        connection.send(msg)
        
        log.info(f"Installed flow rule on switch {current_switch}: {packet.src} -> {packet.dst} via port {out_port}")

def _handle_ConnectionUp(event):
    """Handle switch connection events."""
    switch_last_seen[event.dpid] = time.time()
    log.info(f"Switch {event.dpid} connected")
    
    # Install ICMP flow rule immediately
    log.info(f"Installing ICMP flow rule on switch {event.dpid}")
    icmp_msg = of.ofp_flow_mod()
    icmp_msg.match = of.ofp_match()
    icmp_msg.match.dl_type = 0x800  # IP
    icmp_msg.match.nw_proto = 1     # ICMP
    icmp_msg.priority = 65535       # Highest priority
    icmp_msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
    event.connection.send(icmp_msg)
    log.info(f"Installed ICMP flow rule on switch {event.dpid}")
    
    # Clear any stale paths involving this switch
    for path in list(path_table.keys()):
        if event.dpid in path:
            del path_table[path]

def _handle_ConnectionDown(event):
    """Handle switch disconnection events."""
    if event.dpid in switch_last_seen:
        del switch_last_seen[event.dpid]
    
    # Clear paths and links involving this switch
    for neighbor in list(adjacency_list[event.dpid].keys()):
        if neighbor in adjacency_list:
            del adjacency_list[neighbor][event.dpid]
    adjacency_list[event.dpid].clear()
    
    # Clear host mappings for this switch
    for mac, switch in list(host_to_switch.items()):
        if switch == event.dpid:
            del host_to_switch[mac]
    
    log.info(f"Switch {event.dpid} disconnected, cleared related paths and mappings")

def _handle_PacketIn(event):
    """Handle incoming packets and route them appropriately."""
    packet = event.parsed
    dpid = event.dpid  # Switch DPID

    if not packet.parsed:
        log.warning("Ignoring incomplete packet")
        return

    eth = packet.find('ethernet')
    if not eth:
        return

    # Track MAC address to switch/port mapping
    src_mac = str(eth.src)
    
    # Skip multicast and broadcast MAC addresses
    if eth.src.is_multicast or eth.src.is_broadcast:
        log.warning(f"Ignoring packet with broadcast/multicast source MAC: {src_mac}")
        return
    
    # Check if this MAC is already mapped to a switch/port
    if src_mac in mac_to_port:
        current_switch, current_port = mac_to_port[src_mac]
        
        # Only update if the switch has changed (host moved)
        if current_switch != dpid:
            mac_to_port[src_mac] = (dpid, event.port)
            rate_limited_log(log, "debug", f"Host {src_mac} moved from switch {current_switch} to switch {dpid}, port {event.port}", f"host_move_{src_mac}")
    else:
        # New MAC address
        mac_to_port[src_mac] = (dpid, event.port)
        log.debug(f"Learned new MAC {src_mac} on switch {dpid}, port {event.port}")

    # Handle ARP packets specially
    if eth.type == ethernet.ARP_TYPE:
        log.debug(f"Processing ARP packet from {eth.src} to {eth.dst}")
        arp_packet = packet.find('arp')
        
        if arp_packet:
            log.debug(f"ARP packet details: opcode={arp_packet.opcode}, src_ip={arp_packet.protosrc}, dst_ip={arp_packet.protodst}")
            
            # Update IP to MAC mapping
            if str(arp_packet.protosrc) not in ip_to_mac:
                ip_to_mac[str(arp_packet.protosrc)] = src_mac
                log.debug(f"Mapped IP {arp_packet.protosrc} to MAC {src_mac}")
        
        # If we know the destination MAC location, send directly there
        if str(eth.dst) in mac_to_port and not eth.dst.is_multicast and not eth.dst.is_broadcast:
            dst_dpid, dst_port = mac_to_port[str(eth.dst)]
            if dst_dpid == dpid:  # If on same switch
                msg = of.ofp_packet_out()
                msg.data = event.ofp
                msg.actions.append(of.ofp_action_output(port=dst_port))
                msg.in_port = event.port
                event.connection.send(msg)
                log.info(f"Forwarding ARP directly to known host on port {dst_port}")
                return
        
        # Otherwise, flood ARP request/reply
        flood_packet(event)
        return

    # Handle IP packets for routing
    ip_packet = packet.find('ipv4')
    if not ip_packet:
        # Handle flooding for non-IP packets
        if eth.dst.is_multicast or eth.dst.is_broadcast:
            log.debug(f"Flooding multicast/broadcast packet from switch {dpid}")
            flood_packet(event)
        elif str(eth.dst) not in mac_to_port:
            log.debug(f"Flooding packet with unknown destination MAC {eth.dst}")
            flood_packet(event)
        return

    src_ip = str(ip_packet.srcip)
    dst_ip = str(ip_packet.dstip)
    
    log.info(f"Processing IP packet: {src_ip} -> {dst_ip} on switch {dpid}")

    # Update IP to MAC mapping
    if src_ip not in ip_to_mac:
        ip_to_mac[src_ip] = src_mac
        log.info(f"Mapped IP {src_ip} to MAC {src_mac}")

    # Update host-to-switch mapping
    if src_ip not in host_to_switch:
        host_to_switch[src_ip] = dpid
        log.info(f"Detected host {src_ip} connected to switch {dpid}")
        
        # Create host name mapping based on IP
        host_num = src_ip.split('.')[-1]
        if src_ip not in ip_to_name:
            ip_to_name[src_ip] = f"h{host_num}"
            log.info(f"Mapping {src_ip} to {ip_to_name[src_ip]}")

    # If destination is broadcast/multicast, flood
    if ip_packet.dstip.is_multicast or ip_packet.dstip.is_broadcast:
        log.debug(f"Flooding multicast/broadcast IP packet to {dst_ip}")
        flood_packet(event)
        return

    # If destination MAC is broadcast but we know the IP, try to use IP
    if (eth.dst.is_broadcast or eth.dst.is_multicast) and dst_ip in host_to_switch:
        log.info(f"Broadcast MAC with known IP destination {dst_ip}, attempting to route based on IP")
    elif str(eth.dst) not in mac_to_port and dst_ip not in host_to_switch:
        log.warning(f"Unknown destination {dst_ip}, flooding packet")
        flood_packet(event)
        return

    # Get source and destination switches
    src_switch = host_to_switch[src_ip]
    
    # If destination IP not in host_to_switch mapping, flood
    if dst_ip not in host_to_switch:
        log.warning(f"Unknown destination IP {dst_ip}, flooding packet")
        flood_packet(event)
        return
        
    dst_switch = host_to_switch[dst_ip]
    log.info(f"Host-to-switch mapping: {src_ip} -> {src_switch}, {dst_ip} -> {dst_switch}")

    # Compute shortest path if not already cached
    path_key = (src_ip, dst_ip)
    if path_key not in path_table:
        if src_switch == dst_switch:
            path = [src_switch]  # Same switch, no need for Dijkstra
            log.info(f"Source and destination on same switch: {src_switch}")
        else:
            path = dijkstra(src_switch, dst_switch)
            
        if path:
            path_table[path_key] = path
            log.info(f"Computed path for {src_ip}->{dst_ip}: {path}")
        else:
            log.warning(f"No path found from {src_ip} to {dst_ip}")
            flood_packet(event)  # Flood as fallback
            return
    else:
        path = path_table[path_key]
        log.info(f"Using cached path for {src_ip}->{dst_ip}: {path}")

    # Get human-readable names for tracking
    src_host = ip_to_name.get(src_ip, f"h{src_ip.split('.')[-1]}")
    dst_host = ip_to_name.get(dst_ip, f"h{dst_ip.split('.')[-1]}")

    # Check if this is an ICMP packet
    icmp_packet = packet.find('icmp')
    if icmp_packet:
        log.info(f"Detected ICMP packet: type={icmp_packet.type}, code={icmp_packet.code}")
        
        # For ICMP Echo Request (ping), we want to track the path
        if icmp_packet.type == 8:  # Echo Request
            log.info(f"Processing ICMP Echo Request from {src_ip} to {dst_ip}")
            
            # Only send path data if the last command was a ping (not pingall)
            if command_db.is_last_command_ping():
                log.info("Last command was ping, sending path data")
                # Send path data for visualization
                send_path_data(
                    "ping",
                    src_host,
                    dst_host,
                    path,
                    ip_packet.ttl,
                    time.time() * 1000
                )
            else:
                log.info("Last command was not ping, skipping path data")
                
        # For ICMP Echo Reply, we also want to track the path
        elif icmp_packet.type == 0:  # Echo Reply
            log.info(f"Processing ICMP Echo Reply from {src_ip} to {dst_ip}")
            # Only send return path data if the last command was a ping
            if command_db.is_last_command_ping():
                log.info("Last command was ping, sending return path data")
                send_path_data(
                    "pong",
                    src_host,
                    dst_host,
                    path,
                    ip_packet.ttl,
                    time.time() * 1000
                )
            else:
                log.info("Last command was not ping, skipping return path data")

    # Check if the current switch is in the path
    if dpid not in path:
        log.warning(f"Current switch {dpid} not in path {path}, flooding packet")
        flood_packet(event)
        return
        
    # Find the position of the current switch in the path
    current_pos = path.index(dpid)
    
    # Install flows and forward the packet
    install_path_flows(event.connection, packet, path)
    forward_packet(event, path, packet)

# Helper functions for packet handling
def flood_packet(event):
    """Flood a packet out all ports except the input port."""
    msg = of.ofp_packet_out()
    msg.data = event.ofp
    msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
    msg.in_port = event.port
    event.connection.send(msg)
    rate_limited_log(log, "debug", f"Flooding packet from switch {event.dpid}, port {event.port}", f"flood_{event.dpid}_{event.port}")

def forward_packet(event, path, packet):
    """Forward a packet to the next switch in the path."""
    current_switch = event.dpid
    current_pos = path.index(current_switch)
    
    # If this is the last switch in the path, send to the host
    if current_pos == len(path) - 1:
        # Find the destination MAC and its port
        if packet.dst in mac_to_port:
            _, dst_port = mac_to_port[packet.dst]
            log.debug(f"Forwarding to destination host on switch {current_switch}, port {dst_port}")
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            msg.actions.append(of.ofp_action_output(port=dst_port))
            msg.in_port = event.port
            event.connection.send(msg)
        else:
            # If we don't know the destination port, flood
            log.warning(f"Unknown destination port for {packet.dst} on last switch {current_switch}, flooding")
            flood_packet(event)
        return
    
    # Otherwise, forward to the next switch in the path
    next_switch = path[current_pos + 1]
    if next_switch in adjacency_list[current_switch]:
        out_port = adjacency_list[current_switch][next_switch]
        log.debug(f"Forwarding from switch {current_switch} to switch {next_switch} on port {out_port}")
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=out_port))
        msg.in_port = event.port
        event.connection.send(msg)
    else:
        log.warning(f"No adjacency information for switch {current_switch} to {next_switch}, flooding")
        flood_packet(event)

def _handle_LinkEvent(event):
    """Handle link events to maintain topology information."""
    link = event.link
    if event.added:  # Link added
        src, dst = link.dpid1, link.dpid2
        port_src, port_dst = link.port1, link.port2

        # Update adjacency list with the link ports
        adjacency_list[src][dst] = port_src
        adjacency_list[dst][src] = port_dst
        log.info(f"Link added: {src} <--> {dst} (ports: {port_src} <--> {port_dst})")
        
        # Create switch name mappings if they don't exist
        if src not in dpid_to_name:
            dpid_to_name[src] = f"s{src}"
        if dst not in dpid_to_name:
            dpid_to_name[dst] = f"s{dst}"
        
        # Clear path cache when topology changes
        path_table.clear()
        log.info("Path cache cleared due to topology change")
        
        # Log the current adjacency list for debugging
        log.info(f"Current adjacency list: {adjacency_list}")
    elif event.removed:  # Link removed
        src, dst = link.dpid1, link.dpid2
        
        # Remove from adjacency list
        if dst in adjacency_list[src]:
            del adjacency_list[src][dst]
        if src in adjacency_list[dst]:
            del adjacency_list[dst][src]
        
        log.info(f"Link removed: {src} <--> {dst}")
        
        # Clear path cache when topology changes
        path_table.clear()
        log.info("Path cache cleared due to topology change")

        # Log the current adjacency list for debugging
        log.info(f"Current adjacency list: {adjacency_list}")

def get_command_id_from_packet(packet):
    """Extract command ID from packet data if present."""
    try:
        # Check if packet has data payload
        if hasattr(packet, 'payload') and packet.payload:
            # Look for command ID in packet data
            data = str(packet.payload)
            if 'command_id:' in data:
                # Extract command ID from packet data
                command_id = data.split('command_id:')[1].split()[0]
                log.info(f"Found command ID in packet: {command_id}")
                return command_id
    except Exception as e:
        log.warning(f"Error extracting command ID from packet: {e}")
    return None

def launch():
    """Initialize the controller components."""
    # Make sure the OpenFlow discovery component is running
    if not core.hasComponent("openflow_discovery"):
        log.info("Dependency not met: openflow_discovery not running. Starting it...")
        from pox.openflow.discovery import launch as launch_discovery
        launch_discovery()
    
    # Register event handlers
    core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
    core.openflow_discovery.addListenerByName("LinkEvent", _handle_LinkEvent)
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    core.openflow.addListenerByName("ConnectionDown", _handle_ConnectionDown)
    
    # Add startup delay before trying to connect to FastAPI
    from pox.lib.recoco import Timer
    Timer(STARTUP_DELAY, check_fastapi_connection)
    log.info(f"Will attempt to connect to FastAPI server in {STARTUP_DELAY} seconds...")
    
    log.info("SDN Controller with Path Tracking Started")
