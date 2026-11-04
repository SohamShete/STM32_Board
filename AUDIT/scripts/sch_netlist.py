#!/usr/bin/env python3
"""Minimal KiCad 9 schematic (.kicad_sch) netlist extractor.

Usage: python3 sch_netlist.py path/to/file.kicad_sch [--json out.json]

Pure-Python s-expression parser; no KiCad installation required. It
places every symbol pin from the embedded lib_symbols, applies the
instance rotation/mirror, then unions pins, wire endpoints, junctions,
labels and power symbols into nets. Output: one line per net with its
member pins (Ref.pin pinname), and a list of pins that touch nothing
(unconnected). Intended as a re-runnable check for AUDIT/.
"""
import sys, json, math, re
from collections import defaultdict

# ---------- s-expression parser ----------
def parse(text):
    tok = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+')
    stack = [[]]
    for m in tok.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            l = stack.pop(); stack[-1].append(l)
        elif t.startswith('"'):
            stack[-1].append(t[1:-1].replace('\\"', '"'))
        else:
            try:
                stack[-1].append(float(t) if ('.' in t or 'e' in t) and not t.startswith('0x') else int(t))
            except ValueError:
                stack[-1].append(t)
    return stack[0][0]

def kids(node, key):
    return [n for n in node[1:] if isinstance(n, list) and n and n[0] == key]

def kid(node, key, default=None):
    k = kids(node, key)
    return k[0] if k else default

def prop(sym, name):
    for p in kids(sym, 'property'):
        if p[1] == name:
            return p[2]
    return None

# ---------- geometry ----------
def r2(v): return round(v, 3)

def place(px, py, at, mirror):
    """Transform lib pin coordinate (px,py) into schematic coordinates."""
    x, y, rot = at[0], at[1], (at[2] if len(at) > 2 else 0)
    # KiCad lib Y axis points up; schematic Y points down.
    lx, ly = px, -py
    if mirror == 'x':   # mirror about X axis (flip vertically)
        ly = -ly
    elif mirror == 'y': # mirror about Y axis (flip horizontally)
        lx = -lx
    a = math.radians(rot)
    # rotation is counter-clockwise on screen (y down) => standard with negated angle
    rx = lx * math.cos(a) + ly * math.sin(a)
    ry = -lx * math.sin(a) + ly * math.cos(a)
    return r2(x + rx), r2(y + ry)

def main():
    path = sys.argv[1]
    out_json = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
    root = parse(open(path, encoding='utf-8').read())
    assert root[0] == 'kicad_sch'

    # library symbols -> pins, incl. extends/derived handling (basic)
    libs = {}
    for ls in kids(kid(root, 'lib_symbols'), 'symbol'):
        name = ls[1]
        pins = []  # (unit, number, name, type, x, y, len, rot)
        for unit in kids(ls, 'symbol'):
            for p in kids(unit, 'pin'):
                at = kid(p, 'at')
                pins.append(dict(unit=unit[1], etype=p[1], gtype=p[2],
                                 number=str(kid(p, 'number')[1]), name=str(kid(p, 'name')[1]),
                                 x=at[1], y=at[2]))
        power = kid(ls, 'power') is not None
        libs[name] = dict(pins=pins, power=power)

    # Union-find over points
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb

    wires = []
    for w in kids(root, 'wire'):
        pts = [(r2(p[1]), r2(p[2])) for p in kids(kid(w, 'pts'), 'xy')]
        wires.append(pts)
        for a, b in zip(pts, pts[1:]):
            union(('pt', a), ('pt', b))
    # points lying in the middle of a wire segment also connect (T junctions w/o explicit junction are not connected in KiCad unless a junction exists; KiCad does connect pin endpoints landing on a wire mid-segment? No: pins must be on endpoints or junctions. Labels can sit mid-wire.)
    def on_segment(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        if abs((x2-x1)*(y-y1) - (y2-y1)*(x-x1)) > 1e-3: return False
        return min(x1,x2)-1e-3 <= x <= max(x1,x2)+1e-3 and min(y1,y2)-1e-3 <= y <= max(y1,y2)+1e-3

    def attach(p, allow_mid=True):
        """Connect point p to any wire it touches (endpoints, or mid-segment if allowed)."""
        for pts in wires:
            for a, b in zip(pts, pts[1:]):
                if p == a or p == b or (allow_mid and on_segment(p, a, b)):
                    union(('pt', p), ('pt', a))

    junctions = [(r2(j[1]), r2(j[2])) for j in (kid(x, 'at') for x in kids(root, 'junction'))]
    for j in junctions:
        attach(j)

    labels = []
    for kind in ('label', 'global_label', 'hierarchical_label'):
        for l in kids(root, kind):
            at = kid(l, 'at'); p = (r2(at[1]), r2(at[2]))
            labels.append((kind, l[1], p))
            attach(p)
            union(('pt', p), ('net', l[1] if l[1] else '<EMPTY LABEL>'))

    noconn = [(r2(n[1]), r2(n[2])) for n in (kid(x, 'at') for x in kids(root, 'no_connect'))]

    pins = []  # placed pins
    symbols = []
    for s in kids(root, 'symbol'):
        lib_id = kid(s, 'lib_id')[1]
        at = kid(s, 'at')[1:]
        mirror = kid(s, 'mirror'); mirror = mirror[1] if mirror else None
        unit = kid(s, 'unit')[1]
        ref, val, fp = prop(s, 'Reference'), prop(s, 'Value'), prop(s, 'Footprint')
        lib = libs[lib_id]
        symbols.append(dict(ref=ref, value=val, footprint=fp, lib_id=lib_id, at=at, mirror=mirror,
                            dnp=kid(s, 'dnp', [None, 'no'])[1], in_bom=kid(s, 'in_bom', [None, 'yes'])[1]))
        for p in lib['pins']:
            if p['unit'].rsplit('_', 2)[-2] not in ('0', str(unit)):
                continue
            pos = place(p['x'], p['y'], at, mirror)
            pins.append(dict(ref=ref, value=val, number=p['number'], name=p['name'], etype=p['etype'], pos=pos,
                             power=lib['power'], lib_id=lib_id))
            attach(pos, allow_mid=False)
            # also connect if pin sits exactly on a junction
            if pos in junctions:
                union(('pt', pos), ('pt', pos))
            if lib['power']:
                union(('pt', pos), ('net', val))

    # Build nets
    groups = defaultdict(lambda: dict(pins=[], labels=set(), ncs=[]))
    for p in pins:
        groups[find(('pt', p['pos']))]['pins'].append(p)
    for kind, txt, p in labels:
        groups[find(('pt', p))]['labels'].add(txt or '<EMPTY LABEL>')
    for p in noconn:
        groups[find(('pt', p))]['ncs'].append(p)

    nets = []
    for g in groups.values():
        name = None
        pw = [p['value'] for p in g['pins'] if p['power']]
        if pw: name = pw[0]
        elif g['labels']: name = sorted(g['labels'])[0]
        members = [p for p in g['pins'] if not p['power']]
        if not members and not g['labels']: continue
        nets.append(dict(name=name or '(unnamed)', labels=sorted(g['labels']),
                         pins=sorted(f"{p['ref']}.{p['number']}({p['name']})" for p in members),
                         npins=len(members)))
    nets.sort(key=lambda n: (-n['npins'], n['name']))

    print(f"# {path}")
    print(f"# symbols: {len(symbols)}  wires: {len(wires)}  junctions: {len(junctions)}  labels: {len(labels)}  no_connects: {len(noconn)}")
    print("\n## Components")
    for s in sorted(symbols, key=lambda s: s['ref']):
        if s['ref'].startswith('#'): continue
        print(f"  {s['ref']:6} {s['value']:16} fp={s['footprint'] or '<none>'!r:40} dnp={s['dnp']} in_bom={s['in_bom']}")
    print("\n## Nets")
    for n in nets:
        flag = ''
        if n['npins'] == 1: flag = '   <-- SINGLE-PIN NET'
        if n['npins'] == 0: flag = '   <-- LABEL WITH NO PINS'
        print(f"  {n['name']:14} [{n['npins']}] " + ', '.join(n['pins']) + (f"  labels={n['labels']}" if len(n['labels']) > 1 or (n['labels'] and n['labels'][0] != n['name']) else '') + flag)
    print("\n## Unconnected pins (no wire/label/power at pin end)")
    for p in pins:
        if p['power']: continue
        if find(('pt', p['pos'])) == ('pt', p['pos']) and sum(1 for q in pins if q['pos'] == p['pos']) == 1 and not any(('pt', p['pos']) == find(k) for k in parent if k != ('pt', p['pos'])):
            print(f"  {p['ref']}.{p['number']} ({p['name']}, {p['etype']}) at {p['pos']}" + ("  [no_connect]" if p['pos'] in noconn else ''))
    if out_json:
        json.dump(dict(symbols=symbols, nets=nets), open(out_json, 'w'), indent=1)

if __name__ == '__main__':
    main()
