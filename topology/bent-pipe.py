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
import sched
import argparse
import threading
from collections import defaultdict
from multiprocessing import Process, Value, Lock

from mininet.cli import CLI
from mininet.net import Mininet, Host
from mininet.log import setLogLevel
from mininet.link import TCLink


update_event = threading.Event()
latency_update_interval = 1


class NetworkConfigThread(threading.Thread):
    def __init__(self, net, host_name, dev, latency_trace=None):
        super().__init__()
        self.net = net
        self.host_name = host_name
        self.dev = dev
        self.latency = defaultdict(float)
        self.start_time = None
        if latency_trace:
            self.latency_trace = self.load_latency_trace(latency_trace)

    def load_latency_trace(self, filename: str):
        with open(filename, "r") as csv_file:
            reader = csv.reader(csv_file)
            next(reader)
            for row in reader:
                self.latency[float(row[1])] = float(row[2])

    def get_closest_latency(self) -> float:
        now_relative = time.time() - self.start_time
        closest_time = min(self.latency.keys(), key=lambda x: abs(x - now_relative))
        return self.latency[closest_time] / 2.0


    def configureNetworkConditions(self):
        self.configureStaticNetworkConditions()

        while True:
            update_event.wait()
            now = time.time()
            delay = self.get_closest_latency()
            print("\nUpdate network conditions, now: {}, {} seconds passed, latency: {}".format(now, now - self.start_time, delay))
            self.configureStaticNetworkConditions(delay=delay)
            update_event.clear()


    def configureStaticNetworkConditions(self, delay=100, bw=100, loss=2):
        host = self.net.get(self.host_name)
        for intf in host.intfList():
            if intf.link and str(intf) == self.dev:
                intfs = [intf.link.intf1, intf.link.intf2]
                # intfs[0].config(bw=bw)
                intfs[0].config(delay="{}ms".format(delay))
                intfs[0].config(loss=loss)

                # intfs[1].config(bw=bw)
                intfs[1].config(delay="{}ms".format(delay))
                intfs[1].config(loss=loss)

    def run(self):
        self.start_time = time.time()

        scheduler = sched.scheduler(time.time, time.sleep)
        scheduler.enter(latency_update_interval, 1, update_periodically, (scheduler, self.start_time, latency_update_interval))
        update_thread = threading.Thread(target=scheduler.run)
        update_thread.start()

        self.configureNetworkConditions()


def update_periodically(scheduler, start_time, step):
    next_time = start_time + step
    current_time = time.time()
    sleep_time = next_time - current_time

    if sleep_time > 0:
        update_event.set()
        scheduler.enter(sleep_time, 1, update_periodically, (scheduler, next_time, step))
    else:
        scheduler.enter(0, 1, update_periodically, (scheduler, time.time(), step))


if '__main__' == __name__:
    parser = argparse.ArgumentParser(description='LEONetEM')
    parser.add_argument('--latency', type=str, help='Latency trace file in CSV format')
    args = parser.parse_args()

    if not args.latency:
        print("Please specify the latency trace file")
        exit(1)

    print(args.latency)

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

    net_thread = NetworkConfigThread(net, "router", "router-eth1", args.latency)
    net_thread.start()

    net_thread.join()
    CLI(net)
    net.stop()
