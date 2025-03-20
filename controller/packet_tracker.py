from pox.core import core
from pox.lib.packet import ethernet, ipv4
from pox.lib.addresses import EthAddr
import json

log = core.getLogger()

def _handle_PacketIn(event):
    packet = event.parsed
    if not packet:
        return

    if isinstance(packet.next, ipv4):
        src_ip = packet.next.srcip
        dst_ip = packet.next.dstip
        switch_dpid = event.dpid
        in_port = event.port

        log.info(f"Packet from {src_ip} to {dst_ip} through switch {switch_dpid}, port {in_port}")

        # Send data over WebSocket (Modify this part to fit your WebSocket setup)
        packet_data = {
            "src": str(src_ip),
            "dst": str(dst_ip),
            "switch": switch_dpid,
            "port": in_port
        }
        # Assuming you have a WebSocket function to send this data
        # send_packet_data(json.dumps(packet_data))  

def launch():
    core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
    log.info("Packet Tracker Module Loaded")
