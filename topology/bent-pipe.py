"""
                          Simpilified "Bent-Pipe" topology for Starlink

               192.168.1.1/24                    100.64.0.1/10               10.10.10.101/24
User  -----------------------  Router  -----------------------  PoP  -----------------------  Dst
        192.168.1.101/24                 100.76.100.1/10               10.10.10.1/24

## Topology

User:
User device (e.g., laptop) connected to the Router.

Router:
The stock Starlink user router provisions a 192.168.1.0/24 network for end devices.

PoP:
Simplified PoP (Point of Presence) structure combined with landing ground stations.
In real Starlink networks, there is 1 IP-Hop between the user router to the PoP,
which traverses the User Dish, (potentially multiple) satellites, landing ground stations, and to the PoP.
For normal Starlink subscribers, CGNAT is utilized for IPv4, and the PoP / Gateway is always accessible at 100.64.0.1.
On the WAN side of the router, a address from 100.64.0.1/10 is assigned.

Dst:
In this topology, we simpilify the connectivity between PoP and destination server.
In real Starlink networks, network packets exit the PoP go through the IXP and transit to the destination server via terrestrial networks.

## Emulation

In this topology, we emulate the 15s latency handover pattern for the satellite link, i.e., the link between Router and PoP.
The latency and throughput traces are loaded from CSV files.
We assume the link between User and Router, and between PoP and Dst are stable and negligible.
"""

import csv
import time
import threading
from multiprocessing import Process, Value, Lock

from mininet.cli import CLI
from mininet.net import Mininet, Host
from mininet.log import setLogLevel
from mininet.link import TCLink


class NetworkConfigThread(threading.Thread):
    def __init__(self, net, host_name, dev):
        super().__init__()
        self.net = net
        self.host_name = host_name
        self.dev = dev

    def run(self):
        configureStaticNetworkConditions(self.net, self.host_name, self.dev)


def configureStaticNetworkConditions(net, host_name, dev, delay=100, bw=100, loss=2):
    host = net.get(host_name)
    for intf in host.intfList():
        if intf.link and str(intf) == dev:
            intfs = [intf.link.intf1, intf.link.intf2]
            intfs[0].config(bw=bw)
            intfs[0].config(delay="{}ms".format(delay))
            intfs[0].config(loss=loss)

            intfs[1].config(bw=bw)
            intfs[1].config(delay="{}ms".format(delay))
            intfs[1].config(loss=loss)

            print(intfs[0].config)


def configureNetworkConditions(net, host_name, dev, column, barrier, line_number, line_lock, update_event):
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

    user = net.addHost('user')
    router = net.addHost('router')
    pop = net.addHost('pop')
    dst = net.addHost('dst')

    linkopt = {'bw': 1000}
    # delay is one way delay
    linkopt_starlink = {'bw': 100, 'delay': "100ms", 'loss': 2}

    net.addLink(user, router, cls=TCLink, **linkopt)
    net.addLink(router, pop, cls=TCLink, **linkopt_starlink)
    net.addLink(pop, dst, cls=TCLink, **linkopt)
    net.build()

    user.cmd("ifconfig user-eth0 0")
    user.cmd("ifconfig user-eth0 192.168.1.101 netmask 255.255.255.0")
    user.cmd("ip route add default scope global nexthop via 192.168.1.1 dev user-eth0")
    user.cmd("ip route add 10.10.10.0/24 via 192.168.1.1")

    router.cmd("ifconfig router-eth0 0")
    router.cmd("ifconfig router-eth1 0")
    router.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    router.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")
    router.cmd("ifconfig router-eth0 192.168.1.1 netmask 255.255.255.0")
    router.cmd("ifconfig router-eth1 100.76.100.1 netmask 255.192.0.0")
    router.cmd("ip route add default scope global nexthop via 100.64.0.1 dev router-eth0")
    router.cmd("ip route add 10.10.10.0/24 via 100.64.0.1")

    pop.cmd("ifconfig pop-eth0 0")
    pop.cmd("ifconfig pop-eth1 0")
    pop.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    pop.cmd("echo 1 > /proc/sys/net/ipv4/conf/all/proxy_arp")
    pop.cmd("ifconfig pop-eth0 100.64.0.1 netmask 255.192.0.0")
    pop.cmd("ifconfig pop-eth1 10.10.10.1 netmask 255.255.255.0")
    pop.cmd("ip route add 192.168.1.0/24 via 100.76.100.1")

    dst.cmd("ifconfig dst-eth0 0")
    dst.cmd("ifconfig dst-eth0 10.10.10.101 netmask 255.255.255.0")
    dst.cmd("ip route add default scope global nexthop via 10.10.10.101 dev dst-eth0")

    net_thread = NetworkConfigThread(net, "router", "router-eth1")
    net_thread.start()
    net_thread.join()

    CLI(net)
    net.stop()
