# Latency traces

Currently, it supports the `ping` latency trace from the `LENS` dataset, which is equivalent to the following

```bash
ping -D -c 360000 -i 0.01 -I <nic> <gateway-ip> > <output-file-name>.txt
```

Run the `convert.py` script to convert the raw `ping` output to the required CSV format.
