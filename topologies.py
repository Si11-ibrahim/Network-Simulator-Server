from mininet.topo import Topo


# Custom topology classes
class CustomTopo(Topo):
    def build(self, num_switches=1, num_hosts=1):
        if num_switches > 20 or num_hosts > 100:
            raise ValueError("Exceeds max allowed: 20 switches, 100 hosts.")

        switches = []
        for i in range(num_switches):
            switch = self.addSwitch(f's{i+1}')
            switches.append(switch)

        for i in range(num_hosts):
            host = self.addHost(f'h{i+1}')
            switch_index = i % num_switches
            self.addLink(host, switches[switch_index])

        for i in range(num_switches - 1):
            self.addLink(switches[i], switches[i + 1])


class StarTopo(Topo):
    def __init__(self, num_hosts, num_switches):
        super().__init__()
        switch = self.addSwitch("s1")

        for i in range(num_hosts):
            host = self.addHost(f"h{i+1}")
            self.addLink(host, switch)


class RingTopo(Topo):
    def __init__(self, num_devices):
        super().__init__()
        nodes = [self.addSwitch(f"s{i+1}") for i in range(num_devices)]

        for i in range(num_devices):
            self.addLink(nodes[i], nodes[(i+1) % num_devices])


class FullMeshTopo(Topo):
    def __init__(self, num_hosts):
        super(FullMeshTopo, self).__init__()
        # Create hosts
        hosts = []
        for i in range(num_hosts):
            host = self.addHost(f'h{i+1}')
            hosts.append(host)

        # Fully connect all hosts (Mesh topology)
        for i in range(num_hosts):
            for j in range(i + 1, num_hosts):
                self.addLink(hosts[i], hosts[j])

class PartialMeshTopo(Topo):
    def __init__(self, num_hosts):
        super(PartialMeshTopo, self).__init__()

        # Create hosts
        hosts = []
        for i in range(num_hosts):
            host = self.addHost(f'h{i+1}')
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
