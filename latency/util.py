import re
import json
import json
from dataclasses import dataclass


@dataclass
class Ping:
    ts: list[float]
    rtt: list[float]


def load_ping(filename: str) -> Ping:
    with open(filename, "r") as f:
        count = 0
        v_Ping = Ping(ts=[], rtt=[])
        for line in f.readlines():
            match = re.search(r"\[(\d+\.\d+)\].*icmp_seq=(\d+).*time=(\d+(\.\d+)?)", line)
            if match:
                count += 1
                timestamp = float(match.group(1))
                rtt = float(match.group(3))
                v_Ping.ts.append(timestamp)
                v_Ping.rtt.append(rtt)

        assert (len(v_Ping.ts) == len(v_Ping.rtt))
        return v_Ping
