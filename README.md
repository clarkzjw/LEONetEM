# LEONetEM

Network Emulator for LEO Satellite Networks

## Topology

### Simpilified "Bent-Pipe" topology for Starlink

```
            192.168.1.1/24                  100.64.0.1/10             10.10.10.101/24
User --------------------- Router ----------------------- PoP ----------------------- Dst
     192.168.1.101/24             100.76.100.1/10             10.10.10.1/24
```

**User**

User device (e.g., laptop) connected to the Router.

**Router**

The stock Starlink user router provisions a 192.168.1.0/24 network for end devices.

**PoP**

Simplified PoP (Point of Presence) structure combined with landing ground stations.

In real Starlink networks, there is 1 IP-Hop between the user router to the PoP, which traverses the User Dish, (potentially multiple) satellites, landing ground stations, and to the PoP.

For normal Starlink subscribers, CGNAT is utilized for IPv4, and the PoP / Gateway is always accessible at 100.64.0.1.

On the WAN side of the router, a address from 100.64.0.1/10 is assigned.

**Dst**

In this topology, we simpilify the connectivity between PoP and destination server.

In real Starlink networks, network packets exit the PoP go through the IXP and transit to the destination server via terrestrial networks.

## Emulation

In this topology, we emulate the 15s latency handover pattern for the satellite link, i.e., the link between Router and PoP.

The latency and throughput traces are loaded from CSV files.

We assume the link between User and Router, and between PoP and Dst are stable and negligible.
