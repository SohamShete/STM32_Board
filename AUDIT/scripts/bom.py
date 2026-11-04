#!/usr/bin/env python3
"""Grouped BOM from AUDIT/out/netlist.json (produced by sch_netlist.py).
Usage: python3 bom.py AUDIT/out/netlist.json > AUDIT/out/bom.csv"""
import json, sys
from collections import defaultdict
d = json.load(open(sys.argv[1]))
g = defaultdict(list)
for s in d['symbols']:
    if s['ref'].startswith('#') or s['in_bom'] != 'yes': continue
    g[(s['value'], s['footprint'] or '')].append(s['ref'])
print('Qty,Value,Footprint,References')
for (v, fp), refs in sorted(g.items(), key=lambda kv: kv[1][0]):
    print(f'{len(refs)},{v},{fp or "<MISSING>"},"{" ".join(sorted(refs))}"')
