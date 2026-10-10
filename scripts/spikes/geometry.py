"""Spike-only D09 distance samples, midpoint weights, 100m point/polyline matches."""
import bisect
import hashlib
import itertools
import json
import math

R = 6371008.8
STEP = 804.672


def distance(a, b):
    lat1, lat2 = map(math.radians, (a[0], b[0]))
    dlat, dlon = map(math.radians, (b[0]-a[0], b[1]-a[1]))
    return 2*R*math.asin(min(1, math.sqrt(math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2)))


def points(route):
    return [(p["latitude"], p["longitude"]) for leg in route["legs"] for p in leg["points"]]


def samples(vertices):
    chain = [0.0]
    for a, b in itertools.pairwise(vertices):
        chain.append(chain[-1] + distance(a, b))
    stations = [i*STEP for i in range(math.ceil(chain[-1]/STEP))] + [chain[-1]]
    bounds = [0] + [(a+b)/2 for a, b in itertools.pairwise(stations)] + [chain[-1]]
    result = []
    for i, station in enumerate(stations):
        index = min(bisect.bisect_right(chain, station)-1, len(vertices)-2)
        span = chain[index+1]-chain[index]
        f = (station-chain[index])/span if span else 0
        a, b = vertices[index:index+2]
        result.append(((a[0]+f*(b[0]-a[0]), a[1]+f*(b[1]-a[1])), bounds[i+1]-bounds[i]))
    return result


def index_segments(vertices):
    index = {}
    for a, b in itertools.pairwise(vertices):
        for x in range(math.floor((min(a[0], b[0])-.003)*100), math.floor((max(a[0], b[0])+.003)*100)+1):
            for y in range(math.floor((min(a[1], b[1])-.003)*100), math.floor((max(a[1], b[1])+.003)*100)+1):
                index.setdefault((x, y), []).append((a, b))
    return index


def nearby(q, segment):
    a, b = segment
    scale = R*math.pi/180
    cosine = math.cos(math.radians(q[0]))
    ax, ay = (a[1]-q[1])*scale*cosine, (a[0]-q[0])*scale
    bx, by = (b[1]-q[1])*scale*cosine, (b[0]-q[0])*scale
    dx, dy = bx-ax, by-ay
    t = max(0, min(1, -(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
    return math.hypot(ax+t*dx, ay+t*dy) <= 100


def direction(source, target_index):
    weighted = samples(source)
    return sum(w for q, w in weighted if any(nearby(q, s) for s in target_index.get((math.floor(q[0]*100), math.floor(q[1]*100)), [])))/sum(w for _, w in weighted)


def analyze(routes):
    vertices = [points(route) for route in routes]
    indices = [index_segments(v) for v in vertices]
    pairs = []
    for i, j in itertools.combinations(range(len(routes)), 2):
        a, b = direction(vertices[i], indices[j]), direction(vertices[j], indices[i])
        pairs.append({"pair": [i, j], "directional": [a, b], "symmetric": max(a, b), "distinct": max(a, b) <= .90})
    ids = [hashlib.sha256(json.dumps(v).encode()).hexdigest() for v in vertices]
    accepted = []
    for i in sorted(range(len(routes)), key=lambda k: ids[k]):
        if all(next(p["distinct"] for p in pairs if set(p["pair"]) == {i, j}) for j in accepted):
            accepted.append(i)
    return {"pairs": pairs, "canonical_ids": ids, "accepted_indices": accepted[:3]}
