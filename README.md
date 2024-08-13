# LEONetEM

Network Emulator for LEO Satellite Networks

## Prerequisites

* [Mininet](http://mininet.org/)

See [Mininet on headless server](#mininet-on-headless-server) when running on a headless server.

## Topology

For more information about the Starlink access network topology, please refer to:

* [**Measuring the Satellite Links of a LEO Network**](https://pan.uvic.ca/webb/download/file.php?id=42372), Jianping Pan, Jinwei Zhao, Lin Cai, 2024 IEEE 59th International Conference on Communications (ICC'24)
* [**Measuring a Low-Earth-Orbit Satellite Network**](https://ieeexplore.ieee.org/document/10294034), Jianping Pan, Jinwei Zhao, Lin Cai
2023 IEEE 34th Annual International Symposium on Personal, Indoor and Mobile Radio Communications (PIMRC'23), doi: 10.1109/PIMRC56721.2023.10294034

### Simpilified "Bent-Pipe" topology for Starlink

See [`bent-pipe.py`](./topology/bent-pipe.py).

```
            192.168.1.1/24                  100.64.0.1/10             10.10.10.101/24
User --------------------- Router ----------------------- PoP ----------------------- Dst
     192.168.1.101/24             100.76.100.1/10             10.10.10.1/24
```

**User**

User device (e.g., laptop) connected to the Router.

**Router**

The stock Starlink user router provisions a `192.168.1.0/24` network for end devices.

**PoP**

Simplified PoP (Point of Presence) structure combined with landing ground stations.

In real Starlink networks, there is 1 IP-Hop between the user router to the PoP, which traverses the User Dish, (potentially multiple) satellites, landing ground stations, then finally to the gateway at the PoP.

For normal Starlink subscribers, CGNAT is utilized for IPv4, and the gateway / PoP is always accessible at `100.64.0.1`.

On the WAN side of the router, an address from `100.64.0.1/10` is assigned.

**Dst**

In this topology, we simpilify the connectivity between PoP and destination servers.

In real Starlink networks, network packets exiting the PoP go through IXPs and transit to the destination server via terrestrial networks.

## Emulation

In this topology, we emulate the 15s latency handover pattern for the satellite link, i.e., the link between the `Router` and `PoP`.

The latency traces are loaded from CSV files.

We assume the link between the `User` and `Router`, and between `PoP` and `Dst` are stable and negligible.

## Note

### Mininet on headless server

When installing Mininet on a headless server, you may need to install X11 related utilities and enable X11-forwarding for SSH.

Some useful settings are provided below.

#### On the server

Enable X11 forwarding in `/etc/ssh/sshd_config` with `X11Forwarding yes` and restart sshd.

Create an empty `.Xauthority` file if not exists in the $HOME directory,

```bash
touch $HOME/.Xauthority
```

add the following line to `~/.bashrc` or other shell configuration files,

```bash
export XAUTHORITY=$HOME/.Xauthority
```

#### On the client

Enable X11 forwarding in `$HOME/.ssh/config`:

```
Host *
    ForwardX11 yes
    ForwardX11Trusted yes
```

When using macOS or Windows as the SSH client, you may need to install [XQuartz](https://www.xquartz.org/) or equivalent X11 server.

When SSH to the server, use the `-X` option:

```bash
ssh -X user@server
```
