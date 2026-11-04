#!/usr/bin/env python3
"""Regression test for sch_netlist.py against the known-good connectivity of
STM32_Board.kicad_sch (verified by hand against the drawn wires 2026-11-04).
Run: python3 -I AUDIT/scripts/test_sch_netlist.py"""
import json, subprocess, sys, os, tempfile
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(os.path.dirname(here))
sch = os.path.join(root, 'STM32_Board', 'STM32_Board.kicad_sch')
out = os.path.join(tempfile.mkdtemp(), 'n.json')
subprocess.run([sys.executable, '-I', os.path.join(here, 'sch_netlist.py'), sch, '--json', out], check=True, capture_output=True)
d = json.load(open(out))
nets = {n['name']: set(n['pins']) for n in d['nets'] if n['npins'] > 1}
def has(net, *pins):
    missing = [p for p in pins if not any(x.startswith(p + '(') for x in nets.get(net, ()))]
    assert not missing, f"{net}: missing {missing}; have {sorted(nets.get(net, ()))}"
has('GND', 'U1.8', 'U1.23', 'U1.35', 'U1.47', 'C1.2', 'C2.2', 'C3.2', 'C4.2', 'C5.2', 'C6.2', 'C7.2', 'C8.2', 'C9.2', 'SW1.1')
has('+3.3V', 'U1.1', 'U1.24', 'U1.36', 'U1.48', 'C1.1', 'C2.1', 'C3.1', 'C4.1', 'C5.1', 'C8.1', 'FB1.2', 'SW1.3')
has('+3.3VA', 'U1.9', 'C6.1', 'C7.1', 'FB1.1')
has('BOOT0', 'U1.44', 'R1.1')
has('NRST', 'U1.7', 'C9.1')
has('SW_BOOT0', 'R1.2', 'SW1.2')
assert len(nets['GND']) == 14 and len(nets['+3.3V']) == 12, (len(nets['GND']), len(nets['+3.3V']))
singles = [n for n in d['nets'] if n['npins'] == 1]
assert len(singles) == 37, len(singles)   # all unused GPIO/OSC pins are floating
assert not [n for n in d['nets'] if n['npins'] == 0], "dangling label present"
syms = [s for s in d['symbols'] if not s['ref'].startswith('#')]
assert len(syms) == 13
print("OK: 6 multi-pin nets, 37 floating MCU pins, 13 components, no dangling labels")
