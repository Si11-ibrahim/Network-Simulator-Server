from mininet.topo import Topo


# Custom topology classes
class CustomTopo(Topo):
    def build(self, num_switches=1, num_hosts=1):
        if num_switches > 20 or num_hosts > 100:
            raise ValueError("Exceeds max allowed: 20 switches, 100 hosts.")

        switches = []
        for i in range(num_switches):
            switch = self.addSwitch(f"s{i+1}")
            switches.append(switch)

        for i in range(num_hosts):
            host = self.addHost(f"h{i+1}")
            switch_index = i % num_switches
            self.addLink(host, switches[switch_index])

        for i in range(num_switches - 1):
            self.addLink(switches[i], switches[i + 1])



class RingTopo(Topo):
    def __init__(self, num_hosts):
        super().__init__()
        # Create switches
        switches = [self.addSwitch(f"s{i+1}") for i in range(num_hosts)]
        
        # Create hosts and connect each to its switch
        for i in range(num_hosts):
            host = self.addHost(f"h{i+1}")
            self.addLink(host, switches[i])
        
        # Connect switches in a ring
        for i in range(num_hosts):
            self.addLink(switches[i], switches[(i+1) % num_hosts])


class FullMeshTopo(Topo):
    def __init__(self, num_hosts):
        super(FullMeshTopo, self).__init__()
        # Create hosts
        hosts = []
        for i in range(num_hosts):
            host = self.addHost(f"h{i+1}")
            hosts.append(host)

        # Fully connect all hosts (Mesh topology)
        for i in range(num_hosts):
            for j in range(i + 1, num_hosts):
                self.addLink(hosts[i], hosts[j])

class Partial_MeshTopo(Topo):
    def __init__(self, num_hosts):
        super(Partial_MeshTopo, self).__init__()

        # Create hosts
        hosts = []
        for i in range(num_hosts):
            host = self.addHost(f"h{i+1}")
            hosts.append(host)

        # Create partial mesh connections
        for i in range(num_hosts):
            if i < num_hosts - 1:
                self.addLink(hosts[i], hosts[i+1])  # Connect each host to the next
                
            if i < num_hosts - 2:
                self.addLink(hosts[i], hosts[i+2])  # Skipping one for partial connectivity

        # Optionally, connect the last host back to the first for a looped structure
        if num_hosts > 2:
            self.addLink(hosts[num_hosts-1], hosts[0])

class StarTopo(Topo):
    def __init__(self, num_hosts):
        super(StarTopo, self).__init__()

        switch = self.addSwitch("s1")  # Add a central switch

        # Create hosts and connect them to the switch
        for i in range(num_hosts):
            host = self.addHost(f"h{i+1}")
            self.addLink(host, switch)

class PartialMeshTopo(Topo):
    def __init__(self, num_hosts):
        super().__init__()
        switch = self.addSwitch('s1')
        # Create hosts and connect them in a partial mesh
        hosts = []
        for i in range(1, num_hosts + 1):
            host = self.addHost(f"h{i}")
            hosts.append(host)
            self.addLink(host, switch)  # Connect each host to the switch

        # Add additional host-to-host links for partial mesh
        for i in range(len(hosts)):
            if i < len(hosts) - 1:
                self.addLink(hosts[i], hosts[i + 1])  # Connect adjacent hosts
            if i < len(hosts) - 2:
                self.addLink(hosts[i], hosts[i + 2])  # Connect skipping one

class FatTree(Topo):
    def __init__(self, num_hosts):
        super(FatTree, self).__init__()

        # Determine k value based on the number of hosts
        k = 2
        while (k // 2) * (k // 2) * k < num_hosts:
            k += 2

        pod = k
        num_core = (pod // 2) ** 2
        num_agg = pod * pod // 2
        num_edge = num_agg

        # Creating switches
        core_switches = []
        agg_switches = []
        edge_switches = []

        # Add Core Switches
        for i in range(num_core):
            sw = self.addSwitch(f's{i+1}')
            core_switches.append(sw)

        # Add Aggregation Switches
        for i in range(num_agg):
            sw = self.addSwitch(f's{num_core + i + 1}')
            agg_switches.append(sw)

        # Add Edge Switches
        for i in range(num_edge):
            sw = self.addSwitch(f's{num_core + num_agg + i + 1}')
            edge_switches.append(sw)

        # Creating links between switches
        # Core to Aggregation Layer
        for i in range(num_core):
            core_sw = core_switches[i]
            start = i % (pod // 2)
            for j in range(pod):
                self.addLink(core_sw, agg_switches[start + j * (pod // 2)], bw=10)

        # Aggregation to Edge Layer
        for i in range(num_agg):
            group = i // (pod // 2)
            for j in range(pod // 2):
                self.addLink(agg_switches[i], edge_switches[group * (pod // 2) + j], bw=10)

        # Creating hosts and linking to edge switches
        host_count = 0
        for i in range(num_edge):
            for j in range(2):
                host_count += 1
                if host_count > num_hosts:
                    return
                host = self.addHost(f'h{host_count}', bw=10)
                self.addLink(edge_switches[i], host)


class TreeTopo(Topo):
    def __init__(self, num_hosts):
        super(TreeTopo, self).__init__()

        if num_hosts < 3:
            raise ValueError("Tree topology requires at least 3 hosts.")

        # Create root switch
        root_switch = self.addSwitch("s1")
        switches = [root_switch]
        hosts = []
        host_index = 1
        switch_index = 2  # Start from s2
        queue = [root_switch]

        while host_index <= num_hosts:
            parent_switch = queue.pop(0)

            # Attach exactly 2 hosts to the current switch if possible
            host_count = min(2, num_hosts - host_index + 1)
            for _ in range(host_count):
                host = self.addHost(f"h{host_index}")
                self.addLink(parent_switch, host)
                
                hosts.append(host)
                host_index += 1

            # Only add child switches if there are hosts left
            # Check if we need to add a left child switch
            if host_index <= num_hosts:
                # Calculate how many hosts will be under this branch
                hosts_remaining = num_hosts - host_index + 1
                
                # Only add a switch if it will have at least one host
                if hosts_remaining > 0:
                    left_switch = self.addSwitch(f"s{switch_index}")
                    self.addLink(parent_switch, left_switch)
                    queue.append(left_switch)
                    switches.append(left_switch)
                    switch_index += 1

            # Check if we need to add a right child switch
            if host_index <= num_hosts:
                # Calculate how many hosts will be under this branch
                hosts_remaining = num_hosts - host_index + 1
                
                # Only add a switch if it will have at least one host
                if hosts_remaining > 0:
                    right_switch = self.addSwitch(f"s{switch_index}")
                    self.addLink(parent_switch, right_switch)
                    queue.append(right_switch)
                    switches.append(right_switch)
                    switch_index += 1

        # Create JSON response
        topology_data = {
            "message": "Tree topology generated successfully!",
            "topology": {
                "hosts": [str(h) for h in hosts],
                "switches": [str(s) for s in switches],
                "links": [(str(link[0]), str(link[1])) for link in self.links()]
            },
            "status": "success"
        }

