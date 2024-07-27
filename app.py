import time
import csv
import mininet.node
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from multiprocessing import Process
import numpy as np
from mininet.cli import CLI
import time
import threading
import random

iface1 = "r2-eth0"
current_line_number = 0
current_line_number_5g = 0

def auto_test():
    for _ in range(100):
        h1.sendCmd('xterm -title "node: h1 server" -hold -e "./picoquicdemo -M 1 -p 4434 -G bbr1 -q ./server_qlog -w ./sample/" &')
        h2.sendCmd('xterm -title "node: h2 client" -hold -e "./picoquicdemo -n test -M 1 -A 10.0.5.3/3 -G bbr1 -q ./client_qlog -o /usr 10.0.1.2 4434 /testfile" &')
        time.sleep(95)
        h1.sendInt()
        h2.sendInt()
        h1.waitOutput()
        h2.waitOutput()
        time.sleep(5)

class NetworkConfigThread(threading.Thread):
    def __init__(self, net, host_name, dev, step, column):
        super().__init__()
        self.net = net
        self.host_name = host_name
        self.column = column
        self.dev = dev
        self.step = step

    def run(self):
        configureNetworkConditions(self.net, self.host_name, self.dev, self.step, self.column)

class NetworkConfigThread_Starlink(threading.Thread):
    def __init__(self, net, host_name, dev, step, column):
        super().__init__()
        self.net = net
        self.host_name = host_name
        self.dev = dev
        self.step = step
        self.column = column
        self.stop_event = threading.Event()

    def run(self):
        configureNetworkConditions_starlink(self.net, self.host_name, self.dev, self.step, self.column, self.stop_event)

    def stop(self):
        self.stop_event.set()

def configureNetworkConditions_starlink(net, host_name, dev, step, column, stop_event):
    global current_line_number

    with open('./lagos.csv', 'r') as file:
        reader = csv.reader(file)
        latency_lines = list(reader)

    host = net.get(host_name)

    initialBW = float(latency_lines[current_line_number][column - 2])
    cmd_bw = 'tc qdisc replace dev {} root handle 1: tbf rate {}mbit burst 15k latency 50ms'.format(dev, initialBW)
    result_bw = host.cmd(cmd_bw)

    initialDelay = float(latency_lines[current_line_number][column])
    cmd_jitter = 'tc qdisc add dev {} parent 1:1 handle 10: netem delay {}ms'.format(dev, initialDelay)
    result_jitter = host.cmd(cmd_jitter)

    while True:
        if stop_event.is_set():
            break

        currentDelay = float(latency_lines[current_line_number][column])

        update_cmd = 'tc qdisc change dev {} parent 1:1 handle 10: netem delay {}ms'.format(dev, currentDelay)
        result = host.cmd(update_cmd)

        currentBW = float(latency_lines[current_line_number][column - 2])
        update_cmd_bw = 'tc qdisc change dev {} root handle 1: tbf rate {}mbit burst 15k latency 50ms'.format(dev, currentBW)
        result = host.cmd(update_cmd_bw)

        current_line_number = (current_line_number + 1) % len(latency_lines)

        time.sleep(step)

        if current_line_number >= len(latency_lines):
            current_line_number = 0

def configureNetworkConditions(net, host_name, dev, step, column):
    global current_line_number_5g
    with open('./5G.csv', 'r') as file:
        reader = csv.reader(file)
        latency_lines = list(reader)

    host = net.get(host_name)
    initialBW = float(latency_lines[current_line_number_5g][column - 2])
    cmd_bw = 'tc qdisc replace dev {} root handle 1: tbf rate {}mbit burst 15k latency 50ms'.format(dev, initialBW)
    result_bw = host.cmd(cmd_bw)

    initialDelay = float(latency_lines[current_line_number_5g][column])
    cmd_jitter = 'tc qdisc add dev {} parent 1:1 handle 10: netem delay {}ms'.format(dev, initialDelay)
    result_jitter = host.cmd(cmd_jitter)

    while True:
        currentDelay = float(latency_lines[current_line_number_5g][column])
        update_cmd = 'tc qdisc change dev {} parent 1:1 handle 10: netem delay {}ms'.format(dev, currentDelay)
        result = host.cmd(update_cmd)
        currentBW = float(latency_lines[current_line_number_5g][column - 2])
        update_cmd_bw = 'tc qdisc change dev {} root handle 1: tbf rate {}mbit burst 15k latency 50ms'.format(dev, currentBW)
        result = host.cmd(update_cmd_bw)

        current_line_number_5g = (current_line_number_5g + 1) % len(latency_lines)

        time.sleep(step)

        if current_line_number_5g >= len(latency_lines):
            current_line_number_5g = 0

def link_interruption(node: mininet.node.Host, link: str, loss_rate: int):
    for intf in node.intfList():
        if intf.link and str(intf) == link:
            intfs = [intf.link.intf1, intf.link.intf2]
            intfs[0].config(loss = loss_rate)
            intfs[1].config(loss = loss_rate)


def handover_event(node: mininet.node.Host):
    network_thread2 = NetworkConfigThread_Starlink(net, 'r2', 'r2-eth1', 0.1, 3)
    network_thread2.start()
    network_thread4 = NetworkConfigThread_Starlink(net, 'r4', 'r4-eth0', 0.1, 2)
    network_thread4.start()

    while True:
        stop_event = threading.Event()
        network_thread2.stop()
        network_thread4.stop()
        network_thread2.join()
        network_thread4.join()

        network_thread2 = NetworkConfigThread_Starlink(net, 'r2', 'r2-eth1', 0.1, 3)
        network_thread4 = NetworkConfigThread_Starlink(net, 'r4', 'r4-eth0', 0.1, 2)
        print("Handover")
        loss_rate = random.choice([2, 3])
        # link_interruption(node, iface1, loss_rate)
        network_thread2.start()
        network_thread4.start()

        time.sleep(15)

if '__main__' == __name__:
    setLogLevel('info')
    net = Mininet(link=TCLink)

    h1 = net.addHost('h1')
    h2 = net.addHost('h2')
    r1 = net.addHost('r1')
    r2 = net.addHost('r2')
    r3 = net.addHost('r3')
    r4 = net.addHost('r4')
    r5 = net.addHost('r5')

    linkopt_server = {'bw': 1000}
    linkopt_starlink = {'loss': 2}
    linkopt_broadband = {'loss': 1}

    net.addLink(r1, h1, cls=TCLink, **linkopt_server)
    net.addLink(r1, r4, cls=TCLink, **linkopt_server)
    net.addLink(r1, r5, cls=TCLink, **linkopt_server)
    net.addLink(r4, r2, cls=TCLink, **linkopt_server)
    net.addLink(r5, r3, cls=TCLink, **linkopt_server)
    net.addLink(r2, h2, cls=TCLink, **linkopt_starlink)
    net.addLink(r3, h2, cls=TCLink, **linkopt_broadband)
    net.build()

    r1.cmd("ifconfig r1-eth0 0")
    r1.cmd("ifconfig r1-eth1 0")
    r1.cmd("ifconfig r1-eth2 0")

    r1.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    r1.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")

    r1.cmd("ifconfig r1-eth0 10.0.1.1 netmask 255.255.255.0")
    r1.cmd("ifconfig r1-eth1 10.0.2.1 netmask 255.255.255.0")
    r1.cmd("ifconfig r1-eth2 10.0.3.1 netmask 255.255.255.0")

    r4.cmd("ifconfig r4-eth0 0")
    r4.cmd("ifconfig r4-eth1 0")

    r4.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    r4.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")

    r4.cmd("ifconfig r4-eth0 10.0.2.4 netmask 255.255.255.0")
    r4.cmd("ifconfig r4-eth1 10.0.6.4 netmask 255.255.255.0")

    r5.cmd("ifconfig r5-eth0 0")
    r5.cmd("ifconfig r5-eth1 0")

    r5.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    r5.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")

    r5.cmd("ifconfig r5-eth0 10.0.3.4 netmask 255.255.255.0")
    r5.cmd("ifconfig r5-eth1 10.0.7.4 netmask 255.255.255.0")

    r2.cmd("ifconfig r2-eth0 0")
    r2.cmd("ifconfig r2-eth1 0")

    r2.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    r2.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")

    r2.cmd("ifconfig r2-eth0 10.0.6.2 netmask 255.255.255.0")
    r2.cmd("ifconfig r2-eth1 10.0.4.2 netmask 255.255.255.0")

    r3.cmd("ifconfig r3-eth0 0")
    r3.cmd("ifconfig r3-eth1 0")

    r3.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    r3.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")

    r3.cmd("ifconfig r3-eth0 10.0.7.2 netmask 255.255.255.0")
    r3.cmd("ifconfig r3-eth1 10.0.5.2 netmask 255.255.255.0")

    r2.cmd("ip route add 10.0.1.0/24 via 10.0.6.4")
    r3.cmd("ip route add 10.0.1.0/24 via 10.0.7.4")

    r1.cmd("ip route add 10.0.4.0/24 via 10.0.2.4")
    r1.cmd("ip route add 10.0.5.0/24 via 10.0.3.4")

    r4.cmd("ip route add 10.0.1.0/24 via 10.0.2.1")
    r5.cmd("ip route add 10.0.1.0/24 via 10.0.3.1")
    r4.cmd("ip route add 10.0.4.0/24 via 10.0.6.2")
    r5.cmd("ip route add 10.0.5.0/24 via 10.0.7.2")

    h1.cmd("ifconfig h1-eth0 0")

    h2.cmd("ifconfig h2-eth0 0")
    h2.cmd("ifconfig h2-eth1 0")

    h1.cmd("ifconfig h1-eth0 10.0.1.2 netmask 255.255.255.0")

    h2.cmd("ifconfig h2-eth0 10.0.4.3 netmask 255.255.255.0")
    h2.cmd("ifconfig h2-eth1 10.0.5.3 netmask 255.255.255.0")

    h1.cmd("ip route add default scope global nexthop via 10.0.1.1 dev h1-eth0")

    h2.cmd("ip rule add from 10.0.4.3 table 1")
    h2.cmd("ip rule add from 10.0.5.3 table 2")

    h2.cmd("ip route add 10.0.6.0/24 dev h2-eth0 table 1")
    h2.cmd("ip route add 10.0.4.0/24 dev h2-eth0 table 1")
    h2.cmd("ip route add 10.0.2.0/24 dev h2-eth0 table 1")
    h2.cmd("ip route add 10.0.1.0/24 dev h2-eth0 table 1")

    h2.cmd("ip route add 10.0.7.0/24 dev h2-eth1 table 2")
    h2.cmd("ip route add 10.0.5.0/24 dev h2-eth1 table 2")
    h2.cmd("ip route add 10.0.3.0/24 dev h2-eth1 table 2")
    h2.cmd("ip route add 10.0.1.0/24 dev h2-eth1 table 2")

    h2.cmd("ip route add default scope global nexthop via 10.0.4.2 dev h2-eth0")

    h2.cmd('xterm -title "node: h2 monitoring" -hold -e "sudo bwm-ng" &')

    test_process = Process(target=auto_test)

    test_process.start()

    network_thread1 = NetworkConfigThread(net, 'r3', 'r3-eth1', 0.1, 2)
    network_thread3 = NetworkConfigThread(net, 'r5', 'r5-eth0', 0.1, 3)

    change_latency_process = Process(target=handover_event, args=(r2,))

    change_latency_process.start()
    network_thread1.start()
    network_thread3.start()
    network_thread1.join()
    network_thread3.join()

    change_latency_process.join()
    CLI(net)
    net.stop()
