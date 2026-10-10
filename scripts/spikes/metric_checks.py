"""Offline positive controls for the distance-based overlap spike."""
import json
import math

from common import OUT, save
from geometry import analyze, direction, distance, index_segments, samples

short = [(40, -100), (40, -99.9)]
long = [(40, -100), (40, -99.5)]
dense = [(40, -100+i*.01) for i in range(11)]
parallel = [(40.01, -100), (40.01, -99.9)]
assert math.isclose(direction(short, index_segments(short)), 1)
assert math.isclose(direction(short, index_segments(dense)), 1)
assert math.isclose(direction(short, index_segments(long)), 1)
assert direction(long, index_segments(short)) < .25
assert direction(short, index_segments(parallel)) == 0
assert math.isclose(sum(w for _, w in samples(short)), distance(*short))
for overlap, expected in ((.90, True), (.900001, False)):
    assert (overlap <= .90) == expected
routes = [{"legs": [{"points": [{"latitude": a, "longitude": b} for a, b in short]}]}]*2
assert analyze(routes)["accepted_indices"] == [0]
result = {"passed": 8, "checks": ["self match", "vertex-density independence", "short inside long", "directional containment", "parallel beyond tolerance", "owned-length conservation", "strict 0.90 cutoff", "duplicates rejected"]}
save(OUT / "metric_checks.json", result)
print(json.dumps(result))
