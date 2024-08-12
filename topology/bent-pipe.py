"""
h1 - r - PoP - h2
client - router - PoP - server
"""

import time
import csv
import threading
import sched
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from multiprocessing import Process, Value, Lock
from mininet.cli import CLI

iface1 = "r2-eth0"
init_flags = {
    'r3-eth1': False,
    'r5-eth0': False,
    'r2-eth1': False,
    'r4-eth0': False
}

barrier = threading.Barrier(4)
line_number_5g = Value('i', 0)
line_number_starlink = Value('i', 0)
line_lock = Lock()
update_event = threading.Event()
file_counter = Value('i', 0)


class NetworkConfigThread_Starlink(threading.Thread):
    def __init__(self, net, host_name, dev, column, barrier, line_number, line_lock, update_event):
        super().__init__()
        self.net = net
        self.host_name = host_name
        self.dev = dev
        self.column = column
        self.barrier = barrier
        self.line_number = line_number
        self.line_lock = line_lock
        self.update_event = update_event

    def run(self):
        configureNetworkConditions_starlink(self.net, self.host_name, self.dev, self.column, self.barrier, self.line_number, self.line_lock, self.update_event)

def configureNetworkConditions_starlink(net, host_name, dev, column, barrier, line_number, line_lock, update_event):
    global init_flags

    with open('./lagos.csv', 'r') as file:
        reader = csv.reader(file)
        latency_lines = list(reader)

    host = net.get(host_name)

    with line_lock:
        initialBW = float(latency_lines[line_number.value][column - 2])
        cmd_bw = 'tc qdisc replace dev {} root handle 1: tbf rate {}mbit burst 15k latency 50ms'.format(dev, initialBW)
        host.cmd(cmd_bw)

        initialDelay = float(latency_lines[line_number.value][column])
        cmd_jitter = 'tc qdisc add dev {} parent 1:1 handle 10: netem delay {}ms loss 2%'.format(dev, initialDelay)
        host.cmd(cmd_jitter)

        if not init_flags[dev]:
            init_flags[dev] = True
            # check_and_start_test()

    barrier.wait()

    while True:
        update_event.wait()
        update_event.clear()

        with line_lock:
            current_line_number = line_number.value
            currentBW = float(latency_lines[current_line_number][column - 2])
            update_cmd_bw = 'tc qdisc change dev {} root handle 1: tbf rate {}mbit burst 15k latency 50ms'.format(dev, currentBW)
            host.cmd(update_cmd_bw)

            currentDelay = float(latency_lines[current_line_number][column])
            update_cmd = 'tc qdisc change dev {} parent 1:1 handle 10: netem delay {}ms loss 2%'.format(dev, currentDelay)
            host.cmd(update_cmd)

        barrier.wait()

def update_lines_periodically(scheduler, step, start_time):
    global line_number_5g, line_number_starlink
    with line_lock:
        line_number_5g.value = (line_number_5g.value + 1) % len(open('./5G.csv').readlines())
        line_number_starlink.value = (line_number_starlink.value + 1) % len(open('./lagos.csv').readlines())
    update_event.set()

    next_time = start_time + step
    current_time = time.perf_counter()
    sleep_time = next_time - current_time

    if sleep_time > 0:
        scheduler.enter(sleep_time, 1, update_lines_periodically, (scheduler, step, next_time))
    else:
        scheduler.enter(0, 1, update_lines_periodically, (scheduler, step, time.perf_counter()))


if '__main__' == __name__:
    setLogLevel('info')
    net = Mininet(link=TCLink)

    client = net.addHost('client')
    server = net.addHost('server')
    router = net.addHost('router')
    pop = net.addHost('pop')

    net.addLink(client, router, cls=TCLink)
    net.addLink(router, pop, cls=TCLink)
    net.addLink(pop, server, cls=TCLink)
    net.build()

    client.cmd("ifconfig client-eth0 0")
    client.cmd("ifconfig client-eth0 192.168.1.101 netmask 255.255.255.0")
    client.cmd("ip route add default scope global nexthop via 192.168.1.1 dev client-eth0")
    client.cmd("ip route add 10.10.10.0/24 via 192.168.1.1")

    router.cmd("ifconfig router-eth0 0")
    router.cmd("ifconfig router-eth1 0")
    router.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    router.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")
    router.cmd("ifconfig router-eth0 192.168.1.1 netmask 255.255.255.0")
    # 100.64.0.0/10
    # assume the WAN side IP of the router is 100.76.100.1
    router.cmd("ifconfig router-eth1 100.76.100.1 netmask 255.192.0.0")
    router.cmd("ip route add default scope global nexthop via 100.64.0.1 dev router-eth0")
    router.cmd("ip route add 10.10.10.0/24 via 100.64.0.1")

    pop.cmd("ifconfig pop-eth0 0")
    pop.cmd("ifconfig pop-eth1 0")
    pop.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    pop.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")
    pop.cmd("ifconfig pop-eth0 100.64.0.1 netmask 255.192.0.0")
    # the link between PoP and server is simplified
    pop.cmd("ifconfig pop-eth1 10.10.10.1 netmask 255.255.255.0")
    pop.cmd("ip route add 192.168.1.0/24 via 100.76.100.1")

    server.cmd("ifconfig server-eth0 0")
    server.cmd("ifconfig server-eth0 10.10.10.101 netmask 255.255.255.0")
    server.cmd("ip route add default scope global nexthop via 10.10.10.101 dev server-eth0")

    # network_thread2 = NetworkConfigThread_Starlink(net, 'r2', 'r2-eth1', 3, barrier, line_number_starlink, line_lock, update_event)
    # network_thread4 = NetworkConfigThread_Starlink(net, 'r4', 'r4-eth0', 2, barrier, line_number_starlink, line_lock, update_event)

    # network_thread2.start()
    # network_thread4.start()

    # scheduler = sched.scheduler(time.time, time.sleep)
    # start_time = time.perf_counter()
    # scheduler.enter(0.1, 1, update_lines_periodically, (scheduler, 0.1, start_time))
    # update_thread = threading.Thread(target=scheduler.run)
    # update_thread.start()

    CLI(net)
    net.stop()
