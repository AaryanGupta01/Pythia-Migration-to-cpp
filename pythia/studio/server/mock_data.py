"""Scripted demo project for the mock engine: file texts + per-function outcome metadata.

Pure data. `mock_engine.py` parses FILES with `ast` (so line numbers are always consistent),
compiles the PySub with the real PYTHIA front-end when importable, and combines the result
with META to produce FunctionRecords (CONTRACTS §2).

META value keys (all optional; default = verified filler):
  st        final status: verified|guarded|declined|failed|not_eligible
  elig      static class: verifiable (default) | fixable | not_eligible
  share/calls/speedup   trace numbers (share is a relative weight; the engine normalises all shares to sum to ~0.93)          probe  probe_speedup for declined
  annotated explicit auto-annotated text       pysub  final PySub (LLM rewrite)
  attempts  list[str] PySub candidates; all but the last must fail the typechecker (unless fail=True)
  reason    plain-English reason (fixable / not_eligible / declined / failed)
  diag      [(line, col, kind, msg)] eligibility diagnostics override
  types     ([arg types], ret type) for unannotated functions
  mismatch  {"args","python","cpp","kind"}     exc      exc_matches for the replay
  boundary  boundary penalty                   arg_elems / ret_elems average sizes
"""

PROJECT_NAME = "textlab"

FILES = {}

FILES["textlab/text/distance.py"] = '''"""String distance and similarity metrics used by the fuzzy-dedup stage."""

MAX_EDIT = 64


def edit_distance(a: str, b: str) -> int:
    """Classic two-row Levenshtein distance."""
    n: int = len(a)
    m: int = len(b)
    prev: list[int] = []
    for j in range(m + 1):
        prev.append(j)
    for i in range(1, n + 1):
        cur: list[int] = [i]
        for j in range(1, m + 1):
            cost: int = 0
            if a[i - 1] != b[j - 1]:
                cost = 1
            best: int = prev[j] + 1
            if cur[j - 1] + 1 < best:
                best = cur[j - 1] + 1
            if prev[j - 1] + cost < best:
                best = prev[j - 1] + cost
            cur.append(best)
        prev = cur
    return prev[m]


def hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return -1
    d: int = 0
    for i in range(len(a)):
        if a[i] != b[i]:
            d += 1
    return d


def lcs_length(a, b):
    n = len(a)
    m = len(b)
    prev = []
    for j in range(m + 1):
        prev.append(0)
    for i in range(1, n + 1):
        cur = [0]
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                cur.append(prev[j - 1] + 1)
            elif prev[j] >= cur[j - 1]:
                cur.append(prev[j])
            else:
                cur.append(cur[j - 1])
        prev = cur
    return prev[m]


def jaro_similarity(s1, s2):
    """Jaro similarity in [0, 1]."""
    if s1 == s2:
        return 1.0
    window = max(len(s1), len(s2)) // 2 - 1
    flags1 = [False] * len(s1)
    flags2 = [False] * len(s2)
    matches = 0
    for i, c in enumerate(s1):
        lo = max(0, i - window)
        hi = min(len(s2), i + window + 1)
        for j in range(lo, hi):
            if not flags2[j] and s2[j] == c:
                flags1[i] = True
                flags2[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    transpositions = 0
    k = 0
    for i in range(len(s1)):
        if flags1[i]:
            while not flags2[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
    m = float(matches)
    return (m / len(s1) + m / len(s2) + (m - transpositions / 2) / m) / 3.0


def normalized_similarity(a: str, b: str, dist: int) -> float:
    longest: int = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1.0 - float(dist) / float(longest)


def common_prefix_len(a: str, b: str) -> int:
    n: int = min(len(a), len(b))
    i: int = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def is_palindrome(s: str) -> bool:
    i: int = 0
    j: int = len(s) - 1
    while i < j:
        if s[i] != s[j]:
            return False
        i += 1
        j -= 1
    return True


def within_budget(a: str, b: str) -> bool:
    return abs(len(a) - len(b)) <= MAX_EDIT


class DistanceCache:
    def __init__(self):
        self.hits = 0
        self.table = {}

    def get(self, a, b):
        key = (a, b) if a <= b else (b, a)
        if key in self.table:
            self.hits += 1
            return self.table[key]
        return None
'''

FILES["textlab/text/tokenize.py"] = '''"""Tokenisation helpers and a tiny byte-pair-encoding trainer."""
import re
import unicodedata
from collections import Counter

STOPWORDS = ["the", "a", "an", "of", "and", "to", "in", "is", "it"]
WORD_RE = re.compile(r"[A-Za-z0-9']+")


def count_pair(tokens: list[str], a: str, b: str) -> int:
    """Number of adjacent (a, b) occurrences: the BPE trainer's inner loop."""
    total: int = 0
    for i in range(len(tokens) - 1):
        if tokens[i] == a and tokens[i + 1] == b:
            total += 1
    return total


def merge_pair(tokens: list[str], a: str, b: str) -> list[str]:
    out: list[str] = []
    i: int = 0
    while i < len(tokens):
        if i < len(tokens) - 1 and tokens[i] == a and tokens[i + 1] == b:
            out.append(a + b)
            i += 2
        else:
            out.append(tokens[i])
            i += 1
    return out


def count_vowels(s: str) -> int:
    n: int = 0
    for i in range(len(s)):
        c: str = s[i]
        if c == "a" or c == "e" or c == "i" or c == "o" or c == "u":
            n += 1
    return n


def is_stopword(w: str) -> bool:
    for s in STOPWORDS:
        if s == w:
            return True
    return False


def char_ngrams(s: str, n: int) -> list[str]:
    return [s[i:i + n] for i in range(len(s) - n + 1)]


def word_lengths(words: list[str]) -> list[int]:
    return [len(w) for w in words]


def split_words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return " ".join(text.split()).lower()


def token_freq(tokens: list[str]) -> dict[str, int]:
    return dict(Counter(tokens))


def build_vocab(path: str, min_count: int = 2) -> list[str]:
    counts = Counter()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            counts.update(split_words(line))
    return [w for w, c in counts.items() if c >= min_count]
'''

FILES["textlab/ml/kmeans.py"] = '''"""A small k-means implementation on lists of float vectors."""


def squared_dist(a: list[float], b: list[float]) -> float:
    s: float = 0.0
    for i in range(len(a)):
        d: float = a[i] - b[i]
        s += d * d
    return s


def assign_clusters(points: list[list[float]], centroids: list[list[float]]) -> list[int]:
    """Index of the nearest centroid for every point."""
    labels: list[int] = []
    for p in points:
        best: int = 0
        best_d: float = 1.0e300
        for c in range(len(centroids)):
            d: float = 0.0
            cen: list[float] = centroids[c]
            for i in range(len(p)):
                diff: float = p[i] - cen[i]
                d += diff * diff
            if d < best_d:
                best_d = d
                best = c
        labels.append(best)
    return labels


def update_centroids(points, labels, k):
    dim = len(points[0])
    sums = [[0.0] * dim for _ in range(k)]
    counts = [0] * k
    for p, lab in zip(points, labels):
        counts[lab] += 1
        for i in range(dim):
            sums[lab][i] += p[i]
    return [[s / max(counts[c], 1) for s in sums[c]] for c in range(k)]


def inertia(points: list[list[float]], centroids: list[list[float]], labels: list[int]) -> float:
    total: float = 0.0
    for idx in range(len(points)):
        cen: list[float] = centroids[labels[idx]]
        p: list[float] = points[idx]
        for i in range(len(p)):
            diff: float = p[i] - cen[i]
            total += diff * diff
    return total


def init_centroids(points: list[list[float]], k: int, seed: int) -> list[list[float]]:
    state: int = seed
    out: list[list[float]] = []
    for c in range(k):
        state = (state * 1103515245 + 12345) % 2147483648
        out.append(points[state % len(points)])
    return out


def mean_point(points: list[list[float]]) -> list[float]:
    dim: int = len(points[0])
    out: list[float] = []
    for i in range(dim):
        out.append(0.0)
    for p in points:
        for i in range(dim):
            out[i] += p[i]
    for i in range(dim):
        out[i] = out[i] / len(points)
    return out


def row_norms(matrix: list[list[float]]) -> list[float]:
    """L2 norm of every row. Called once per epoch on the full 10k x 128 matrix."""
    out: list[float] = []
    for row in matrix:
        s: float = 0.0
        for v in row:
            s += v * v
        out.append(s ** 0.5)
    return out


def kmeans_fit(points, k, iters=20):
    centroids = init_centroids(points, k, 7)
    labels = []
    for _ in range(iters):
        labels = assign_clusters(points, centroids)
        centroids = update_centroids(points, labels, k)
    return centroids, inertia(points, centroids, labels)
'''

FILES["textlab/sim/nbody.py"] = '''"""Direct-summation n-body simulation on flat float lists (x,y,z interleaved)."""

G = 6.674e-3


def advance(pos: list[float], vel: list[float], mass: list[float], n: int, dt: float) -> None:
    """One symplectic Euler step; mutates pos and vel in place."""
    for i in range(n):
        ax: float = 0.0
        ay: float = 0.0
        az: float = 0.0
        for j in range(n):
            if i != j:
                dx: float = pos[3 * j] - pos[3 * i]
                dy: float = pos[3 * j + 1] - pos[3 * i + 1]
                dz: float = pos[3 * j + 2] - pos[3 * i + 2]
                r2: float = dx * dx + dy * dy + dz * dz + 0.01
                inv: float = mass[j] / (r2 * (r2 ** 0.5))
                ax += dx * inv
                ay += dy * inv
                az += dz * inv
        vel[3 * i] += ax * dt
        vel[3 * i + 1] += ay * dt
        vel[3 * i + 2] += az * dt
    for i in range(n):
        pos[3 * i] += vel[3 * i] * dt
        pos[3 * i + 1] += vel[3 * i + 1] * dt
        pos[3 * i + 2] += vel[3 * i + 2] * dt


def energy(pos: list[float], vel: list[float], mass: list[float], n: int) -> float:
    e: float = 0.0
    for i in range(n):
        v2: float = vel[3 * i] * vel[3 * i] + vel[3 * i + 1] * vel[3 * i + 1] + vel[3 * i + 2] * vel[3 * i + 2]
        e += 0.5 * mass[i] * v2
        for j in range(i + 1, n):
            dx: float = pos[3 * i] - pos[3 * j]
            dy: float = pos[3 * i + 1] - pos[3 * j + 1]
            dz: float = pos[3 * i + 2] - pos[3 * j + 2]
            e -= mass[i] * mass[j] / ((dx * dx + dy * dy + dz * dz + 0.01) ** 0.5)
    return e


def init_bodies(n: int, seed: int) -> list[float]:
    state: int = seed
    out: list[float] = []
    for i in range(3 * n):
        state = (state * 6364136223846793005 + 1442695040888963407) % 9223372036854775807
        out.append(float(state % 2000) / 1000.0 - 1.0)
    return out


def momentum(vel: list[float], mass: list[float], n: int) -> float:
    px: float = 0.0
    for i in range(n):
        px += vel[3 * i] * mass[i]
    return px


def clip_velocity(vel: list[float], limit: float) -> int:
    clipped: int = 0
    for i in range(len(vel)):
        if vel[i] > limit:
            vel[i] = limit
            clipped += 1
        elif vel[i] < -limit:
            vel[i] = -limit
            clipped += 1
    return clipped


def leapfrog(pos, vel, acc, dt):
    return [p + v * dt + 0.5 * a * dt * dt for p, v, a in zip(pos, vel, acc)]


class Body:
    def __init__(self, x, y, z, m):
        self.x, self.y, self.z, self.m = x, y, z, m

    def kinetic(self, vx, vy, vz):
        return 0.5 * self.m * (vx * vx + vy * vy + vz * vz)
'''

FILES["textlab/num/primes.py"] = '''"""Number-theory helpers used to derive hash-bucket sizes and test inputs."""


def sieve(n: int) -> list[int]:
    """Primes below n (sieve of Eratosthenes)."""
    flags: list[int] = []
    for i in range(n + 1):
        flags.append(1)
    flags[0] = 0
    if n >= 1:
        flags[1] = 0
    p: int = 2
    while p * p <= n:
        if flags[p] == 1:
            q: int = p * p
            while q <= n:
                flags[q] = 0
                q += p
        p += 1
    primes: list[int] = []
    for i in range(2, n + 1):
        if flags[i] == 1:
            primes.append(i)
    return primes


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d: int = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def prime_count(n: int) -> int:
    c: int = 0
    for i in range(2, n):
        if is_prime_inline(i):
            c += 1
    return c


def collatz_len(n: int) -> int:
    steps: int = 1
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


def gcd(a: int, b: int) -> int:
    while b != 0:
        t: int = b
        b = a % b
        a = t
    return a


def mod_pow(base: int, exp: int, mod: int) -> int:
    result: int = 1
    base = base % mod
    while exp > 0:
        if exp % 2 == 1:
            result = (result * base) % mod
        exp = exp // 2
        base = (base * base) % mod
    return result


def factorize(n):
    out = []
    p = 2
    while p * p <= n:
        q, r = divmod(n, p)
        while r == 0:
            out.append(p)
            n = q
            q, r = divmod(n, p)
        p += 1
    if n > 1:
        out.append(n)
    return out


def fib_big(n: int) -> int:
    a: int = 0
    b: int = 1
    for _ in range(n):
        t: int = a + b
        a = b
        b = t
    return a


def digit_sum(n: int) -> int:
    s: int = 0
    while n > 0:
        s += n % 10
        n = n // 10
    return s


def isqrt(n: int) -> int:
    lo: int = 0
    hi: int = n + 1
    while lo + 1 < hi:
        mid: int = (lo + hi) // 2
        if mid * mid <= n:
            lo = mid
        else:
            hi = mid
    return lo


def is_perfect(n: int) -> bool:
    s: int = 1
    d: int = 2
    while d * d <= n:
        if n % d == 0:
            s += d
            if d ** 2 != n:
                s += n // d
        d += 1
    return n > 1 and s == n
'''

FILES["textlab/util/stats.py"] = '''"""Descriptive statistics on plain Python lists."""
import math
from collections import Counter


def mean(xs):
    total = 0.0
    for x in xs:
        total += x
    return total / len(xs)


def variance(xs: list[float]) -> float:
    n: int = len(xs)
    m: float = 0.0
    for x in xs:
        m += x
    m = m / n
    acc: float = 0.0
    for x in xs:
        acc += (x - m) * (x - m)
    return acc / n


def stddev(xs: list[float]) -> float:
    return math.sqrt(variance(xs))


def median(xs):
    ys = sorted(xs)
    n = len(ys)
    if n % 2 == 1:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0


def percentile(xs, q):
    ys = sorted(xs)
    pos = (len(ys) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ys) - 1)
    return ys[lo] + (ys[hi] - ys[lo]) * (pos - lo)


def histogram(xs: list[float], lo: float, hi: float, bins: int) -> list[int]:
    counts: list[int] = []
    for _ in range(bins):
        counts.append(0)
    width: float = (hi - lo) / bins
    for x in xs:
        k: int = int((x - lo) / width)
        if k >= bins:
            k = bins - 1
        if k < 0:
            k = 0
        counts[k] += 1
    return counts


def moving_average(xs, window):
    out = []
    acc = 0.0
    for i in range(len(xs)):
        acc += xs[i]
        if i >= window:
            acc -= xs[i - window]
        if i >= window - 1:
            out.append(acc / window)
    return out


def cumulative_sum(xs: list[int]) -> list[int]:
    out: list[int] = []
    run: int = 0
    for x in xs:
        run += x
        out.append(run)
    return out


def argmax(xs: list[float]) -> int:
    best: int = 0
    for i in range(1, len(xs)):
        if xs[i] > xs[best]:
            best = i
    return best


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(x, hi))


def zscore(xs: list[float], mu: float, sigma: float) -> list[float]:
    out: list[float] = []
    for x in xs:
        out.append((x - mu) / sigma)
    return out


def mode_of(xs):
    return Counter(xs).most_common(1)[0][0]
'''

FILES["textlab/features/vectorize.py"] = '''"""Turn token streams into numeric feature vectors."""
import math
import numpy as np

NUM_BUCKETS = 4096


def tfidf_matrix(docs, vocab):
    tf = np.zeros((len(docs), len(vocab)))
    for i, d in enumerate(docs):
        for w in d:
            tf[i, vocab[w]] += 1
    df = (tf > 0).sum(axis=0)
    return tf * np.log(len(docs) / (1 + df))


def to_dense(rows, width):
    return np.array([r + [0.0] * (width - len(r)) for r in rows])


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot: float = 0.0
    na: float = 0.0
    nb: float = 0.0
    for i in range(len(a)):
        dot += a[i] * b[i]
        na += a[i] * a[i]
        nb += b[i] * b[i]
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def hash_features(codes: list[int], buckets: int) -> list[int]:
    out: list[int] = []
    for _ in range(buckets):
        out.append(0)
    h: int = 5381
    for c in codes:
        h = h * 33 + c
        out[h % buckets] += 1
    return out


def l2_normalize(vec):
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def bucketize(x: float, edges: list[float]) -> int:
    k: int = 0
    while k < len(edges) and x >= edges[k]:
        k += 1
    return k


def one_hot(idx: int, size: int) -> list[int]:
    out: list[int] = []
    for i in range(size):
        if i == idx:
            out.append(1)
        else:
            out.append(0)
    return out


def softmax(xs):
    m = max(xs)
    es = [math.exp(x - m) for x in xs]
    z = sum(es)
    return [e / z for e in es]


def feature_names(prefix, n):
    return {f"{prefix}_{i}": i for i in range(n)} if n else []
'''

FILES["textlab/io/loader.py"] = '''"""Corpus loading and result persistence (I/O bound, intentionally not accelerated)."""
import csv
import hashlib
import json


def load_corpus(path):
    docs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            docs.append(line.rstrip("\\n"))
    return docs


def parse_row(row):
    if row.isdigit():
        return int(row)
    try:
        return float(row)
    except ValueError:
        return row


def iter_batches(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def read_config(path):
    with open(path) as fh:
        return json.load(fh)


def save_results(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        for r in rows:
            w.writerow(r)


def checksum_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()
'''

FILES["textlab/matrix/linalg.py"] = '''"""Dense linear algebra on row-major flat float lists."""


def matmul(a: list[float], b: list[float], n: int, m: int, p: int) -> list[float]:
    """(n x m) @ (m x p) -> (n x p), all row-major."""
    out: list[float] = []
    for i in range(n):
        for j in range(p):
            s: float = 0.0
            for k in range(m):
                s += a[i * m + k] * b[k * p + j]
            out.append(s)
    return out


def transpose(a: list[float], n: int, m: int) -> list[float]:
    out: list[float] = []
    for j in range(m):
        for i in range(n):
            out.append(a[i * m + j])
    return out


def mat_vec(a: list[float], x: list[float], n: int, m: int) -> list[float]:
    out: list[float] = []
    for i in range(n):
        s: float = 0.0
        for k in range(m):
            s += a[i * m + k] * x[k]
        out.append(s)
    return out


def identity(n: int) -> list[float]:
    out: list[float] = []
    for i in range(n):
        for j in range(n):
            if i == j:
                out.append(1.0)
            else:
                out.append(0.0)
    return out


def trace(a: list[float], n: int) -> float:
    t: float = 0.0
    for i in range(n):
        t += a[i * n + i]
    return t


def frobenius(a: list[float]) -> float:
    s: float = 0.0
    for v in a:
        s += v * v
    return s ** 0.5


def row_sums(a: list[float], n: int, m: int) -> list[float]:
    out: list[float] = []
    for i in range(n):
        s: float = 0.0
        for k in range(m):
            s += a[i * m + k]
        out.append(s)
    return out


def outer(x: list[float], y: list[float]) -> list[float]:
    out: list[float] = []
    for a in x:
        for b in y:
            out.append(a * b)
    return out
'''

FILES["textlab/pipeline/runner.py"] = '''"""Wires loading, featurisation, clustering and reporting together."""
import time

from textlab.io.loader import load_corpus, save_results
from textlab.text.distance import edit_distance
from textlab.ml.kmeans import kmeans_fit


def timed(label):
    def deco(fn):
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            out = fn(*args, **kwargs)
            print(f"[{label}] {time.perf_counter() - t0:.2f}s")
            return out
        return wrapper
    return deco


@timed("dedup")
def dedup(docs, threshold=0.85):
    kept = []
    for d in docs:
        if all(edit_distance(d, k) > (1 - threshold) * len(d) for k in kept):
            kept.append(d)
    return kept


def run_pipeline(corpus_path, out_path, k=8):
    docs = dedup(load_corpus(corpus_path))
    points = [[float(len(d)), float(d.count(" "))] for d in docs]
    centroids, inertia = kmeans_fit(points, k)
    save_results(out_path, [[i, *c] for i, c in enumerate(centroids)])
    return inertia
'''

FILES["main.py"] = '''"""Entry point: `python main.py --small` runs the whole TextLab pipeline."""
import argparse

from textlab.pipeline.runner import run_pipeline


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--corpus", default="data/corpus.txt")
    return ap.parse_args(argv)


def main():
    args = parse_args()
    inertia = run_pipeline(args.corpus, "out/centroids.csv", k=4 if args.small else 16)
    print(f"final inertia {inertia:.3f}")


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------------------------------------
# Per-function outcomes. Anything not listed defaults to a small verified function.
# ---------------------------------------------------------------------------------------------
_NP = "calls numpy ('import numpy as np') which PySub does not model"
_OPEN = "uses file I/O: open() is not defined in PySub"


def _D(*items):
    return list(items)


META = {
    # ---- distance.py ------------------------------------------------------------------------
    "textlab/text/distance.py::edit_distance": dict(share=1.2, calls=48210, speedup=38.2, arg_elems=21.4, ret_elems=1.0),
    "textlab/text/distance.py::hamming": dict(share=0.004, calls=9120, speedup=14.1),
    "textlab/text/distance.py::lcs_length": dict(
        share=0.071, calls=6320, speedup=22.4, types=(["str", "str"], "int"),
        annotated='''def lcs_length(a: str, b: str) -> int:
    n: int = len(a)
    m: int = len(b)
    prev: list[int] = []
    for j in range(m + 1):
        prev.append(0)
    for i in range(1, n + 1):
        cur: list[int] = [0]
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                cur.append(prev[j - 1] + 1)
            elif prev[j] >= cur[j - 1]:
                cur.append(prev[j])
            else:
                cur.append(cur[j - 1])
        prev = cur
    return prev[m]
'''),
    "textlab/text/distance.py::jaro_similarity": dict(
        share=0.052, calls=11840, speedup=17.9, elig="fixable", types=(["str", "str"], "float"),
        reason="needs annotations, and enumerate() / list repetition are outside PySub: rewrite as indexed loops",
        attempts=['''def jaro_similarity(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    window: int = max(len(s1), len(s2)) // 2 - 1
    flags1: list[bool] = [False] * len(s1)
    flags2: list[bool] = [False] * len(s2)
    matches: int = 0
    for i, c in enumerate(s1):
        lo: int = max(0, i - window)
        hi: int = min(len(s2), i + window + 1)
        for j in range(lo, hi):
            if not flags2[j] and s2[j] == c:
                flags1[i] = True
                flags2[j] = True
                matches += 1
                break
    return float(matches)
''', '''def jaro_similarity(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    n1: int = len(s1)
    n2: int = len(s2)
    window: int = max(n1, n2) // 2 - 1
    flags1: list[bool] = []
    for i in range(n1):
        flags1.append(False)
    flags2: list[bool] = []
    for j in range(n2):
        flags2.append(False)
    matches: int = 0
    for i in range(n1):
        lo: int = max(0, i - window)
        hi: int = min(n2, i + window + 1)
        for j in range(lo, hi):
            if (not flags2[j]) and s2[j] == s1[i]:
                flags1[i] = True
                flags2[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    transpositions: int = 0
    k: int = 0
    for i in range(n1):
        if flags1[i]:
            while not flags2[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
    m: float = float(matches)
    return (m / n1 + m / n2 + (m - transpositions / 2) / m) / 3.0
''']),
    "textlab/text/distance.py::normalized_similarity": dict(share=0.006, calls=48210, speedup=2.4),
    "textlab/text/distance.py::common_prefix_len": dict(share=0.003, calls=5200, speedup=9.7),
    "textlab/text/distance.py::is_palindrome": dict(share=0.001, calls=800, speedup=6.8),
    "textlab/text/distance.py::within_budget": dict(
        share=0.002, calls=48210, speedup=1.9,
        annotated='''def within_budget(a: str, b: str) -> bool:
    return abs(len(a) - len(b)) <= 64
'''),
    "textlab/text/distance.py::DistanceCache.__init__": dict(st="not_eligible", elig="not_eligible", reason="method of class DistanceCache", diag=_D((6, 5, "TypeError", "methods are outside the v1 analysis scope"))),
    "textlab/text/distance.py::DistanceCache.get": dict(st="not_eligible", elig="not_eligible", share=0.009, calls=48210, reason="method of class DistanceCache", diag=_D((10, 5, "TypeError", "methods are outside the v1 analysis scope"))),

    # ---- tokenize.py ------------------------------------------------------------------------
    "textlab/text/tokenize.py::count_pair": dict(share=0.088, calls=2610, speedup=29.4, arg_elems=4200.0, ret_elems=1.0),
    "textlab/text/tokenize.py::merge_pair": dict(share=0.043, calls=820, speedup=14.6, arg_elems=4200.0, ret_elems=4100.0),
    "textlab/text/tokenize.py::count_vowels": dict(share=0.002, calls=3300, speedup=8.8),
    "textlab/text/tokenize.py::is_stopword": dict(
        share=0.003, calls=61800, speedup=4.2,
        annotated='''def is_stopword(w: str) -> bool:
    for s in ["the", "a", "an", "of", "and", "to", "in", "is", "it"]:
        if s == w:
            return True
    return False
'''),
    "textlab/text/tokenize.py::char_ngrams": dict(
        share=0.024, calls=5400, speedup=11.3, elig="fixable",
        reason="list comprehension with a slice is outside PySub: rewrite as a loop that builds the substring",
        attempts=['''def char_ngrams(s: str, n: int) -> list[str]:
    out: list[str] = []
    for i in range(len(s) - n + 1):
        out.append(s[i:i + n])
    return out
''', '''def char_ngrams(s: str, n: int) -> list[str]:
    out: list[str] = []
    for i in range(len(s) - n + 1):
        g: str = ""
        for j in range(n):
            g = g + s[i + j]
        out.append(g)
    return out
''']),
    "textlab/text/tokenize.py::word_lengths": dict(
        share=0.009, calls=2100, speedup=9.5, elig="fixable",
        reason="list comprehension is outside PySub: rewrite as a for loop with append",
        attempts=['''def word_lengths(words: list[str]) -> list[int]:
    out: list[int] = []
    for w in words:
        out.append(len(w))
    return out
''']),
    "textlab/text/tokenize.py::split_words": dict(
        st="not_eligible", elig="not_eligible", share=0.036, calls=14000,
        reason="calls re.findall (module 're' and compiled patterns are not supported)",
        diag=_D((38, 12, "TypeError", "name 'WORD_RE' is not defined in PySub"), (38, 12, "TypeError", "module 're' is not supported"))),
    "textlab/text/tokenize.py::normalize_text": dict(
        st="not_eligible", elig="fixable", share=0.011, calls=14000, types=(["str"], "str"),
        reason="LLM could not produce a PySub equivalent: unicodedata.normalize and str.split() have no PySub model",
        attempts=['''def normalize_text(text: str) -> str:
    out: str = ""
    for i in range(len(text)):
        out = out + text[i]
    return out.lower()
''', '''def normalize_text(text: str) -> str:
    words: list[str] = text.split()
    return " ".join(words).lower()
''', '''def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()
'''], fail=True),
    "textlab/text/tokenize.py::token_freq": dict(
        st="not_eligible", elig="not_eligible", share=0.018, calls=420,
        reason="uses collections.Counter (a dict subclass) and dict(); only plain dict[K, V] literals are supported",
        diag=_D((49, 17, "TypeError", "function 'dict' is not defined"), (49, 22, "TypeError", "name 'Counter' is not defined"))),
    "textlab/text/tokenize.py::build_vocab": dict(
        st="not_eligible", elig="not_eligible", share=0.002, calls=3, reason=_OPEN,
        diag=_D((53, 10, "SyntaxError", "'with' statements are outside the PySub subset"), (54, 14, "TypeError", "function 'open' is not defined"))),

    # ---- kmeans.py --------------------------------------------------------------------------
    "textlab/ml/kmeans.py::squared_dist": dict(
        st="declined", share=0.064, calls=412000, probe=0.31, arg_elems=8.0, ret_elems=1.0, boundary=0.78,
        reason="called 412,000 times on 8-element vectors: marshalling (~3.1 us/call) costs more than the ~0.9 us it saves"),
    "textlab/ml/kmeans.py::assign_clusters": dict(share=0.5, calls=18, speedup=52.8, arg_elems=16000.0, ret_elems=2000.0),
    "textlab/ml/kmeans.py::update_centroids": dict(
        share=0.083, calls=18, speedup=24.1, elig="fixable", types=(["list[list[float]]", "list[int]", "int"], "list[list[float]]"),
        reason="zip(), list repetition and nested comprehensions are outside PySub: rewrite with indexed loops",
        attempts=['''def update_centroids(points: list[list[float]], labels: list[int], k: int) -> list[list[float]]:
    dim: int = len(points[0])
    sums: list[list[float]] = [[0.0] * dim for _ in range(k)]
    counts: list[int] = [0] * k
    for p, lab in zip(points, labels):
        counts[lab] += 1
        for i in range(dim):
            sums[lab][i] += p[i]
    return sums
''', '''def update_centroids(points: list[list[float]], labels: list[int], k: int) -> list[list[float]]:
    dim: int = len(points[0])
    sums: list[list[float]] = []
    counts: list[int] = []
    for c in range(k):
        row: list[float] = []
        for i in range(dim):
            row.append(0.0)
        sums.append(row)
        counts.append(0)
    for idx in range(len(points)):
        lab: int = labels[idx]
        counts[lab] += 1
        for i in range(dim):
            sums[lab][i] += points[idx][i]
    out: list[list[float]] = []
    for c in range(k):
        cen: list[float] = []
        denom: int = max(counts[c], 1)
        for i in range(dim):
            cen.append(sums[c][i] / denom)
        out.append(cen)
    return out
''']),
    "textlab/ml/kmeans.py::inertia": dict(share=0.057, calls=18, speedup=31.0, arg_elems=16000.0, ret_elems=1.0),
    "textlab/ml/kmeans.py::init_centroids": dict(st="guarded", share=0.002, calls=3, speedup=3.1, exc=0),
    "textlab/ml/kmeans.py::mean_point": dict(share=0.004, calls=60, speedup=12.3),
    "textlab/ml/kmeans.py::row_norms": dict(
        st="declined", share=0.041, calls=20, probe=0.74, arg_elems=1280000.0, ret_elems=10000.0, boundary=0.64,
        reason="one call per epoch on a 10,000 x 128 matrix: copying 1.28M floats across the boundary costs more than the compute saves"),
    "textlab/ml/kmeans.py::kmeans_fit": dict(
        st="not_eligible", elig="fixable", share=0.006, calls=1,
        types=(["list[list[float]]", "int", "int"], "tuple[list[list[float]], float]"),
        reason="returns a tuple (centroids, inertia): tuple returns are outside PySub and changing the return type would break callers",
        attempts=['''def kmeans_fit(points: list[list[float]], k: int, iters: int) -> list[list[float]]:
    return points
''', '''def kmeans_fit(points: list[list[float]], k: int, iters: int) -> tuple[list[list[float]], float]:
    centroids: list[list[float]] = init_centroids(points, k, 7)
    return centroids, 0.0
''', '''def kmeans_fit(points: list[list[float]], k: int, iters: int):
    return init_centroids(points, k, 7), 0.0
'''], fail=True),

    # ---- nbody.py ---------------------------------------------------------------------------
    "textlab/sim/nbody.py::advance": dict(share=0.4, calls=400, speedup=81.3, exc=0, arg_elems=192.0, ret_elems=0.0),
    "textlab/sim/nbody.py::energy": dict(share=0.052, calls=40, speedup=64.5, arg_elems=192.0),
    "textlab/sim/nbody.py::init_bodies": dict(st="guarded", share=0.001, calls=2, speedup=5.4, exc=0),
    "textlab/sim/nbody.py::momentum": dict(share=0.002, calls=40, speedup=7.7),
    "textlab/sim/nbody.py::clip_velocity": dict(share=0.003, calls=400, speedup=9.1, exc=0),
    "textlab/sim/nbody.py::leapfrog": dict(
        share=0.019, calls=400, speedup=19.6, elig="fixable", types=(["list[float]", "list[float]", "list[float]", "float"], "list[float]"),
        reason="unannotated, and zip() inside a comprehension is outside PySub: rewrite as an indexed loop",
        attempts=['''def leapfrog(pos: list[float], vel: list[float], acc: list[float], dt: float) -> list[float]:
    out: list[float] = []
    for i in range(len(pos)):
        out.append(pos[i] + vel[i] * dt + 0.5 * acc[i] * dt * dt)
    return out
''']),
    "textlab/sim/nbody.py::Body.__init__": dict(st="not_eligible", elig="not_eligible", reason="method of class Body", diag=_D((4, 5, "TypeError", "methods are outside the v1 analysis scope"))),
    "textlab/sim/nbody.py::Body.kinetic": dict(st="not_eligible", elig="not_eligible", share=0.008, calls=1200, reason="method of class Body", diag=_D((7, 5, "TypeError", "methods are outside the v1 analysis scope"))),

    # ---- primes.py --------------------------------------------------------------------------
    "textlab/num/primes.py::sieve": dict(share=0.28, calls=14, speedup=61.0, arg_elems=1.0, ret_elems=78498.0),
    "textlab/num/primes.py::is_prime": dict(share=0.047, calls=88400, speedup=47.2, exc=0),
    "textlab/num/primes.py::prime_count": dict(
        st="not_eligible", elig="not_eligible", share=0.006, calls=12,
        reason="calls 'is_prime_inline', which is not defined in this module (dead import left behind by a refactor)",
        diag=_D((29, 12, "TypeError", "function 'is_prime_inline' is not defined"))),
    "textlab/num/primes.py::collatz_len": dict(st="guarded", share=0.034, calls=30000, speedup=21.5, exc=2),
    "textlab/num/primes.py::gcd": dict(share=0.008, calls=126000, speedup=6.3),
    "textlab/num/primes.py::mod_pow": dict(st="guarded", share=0.011, calls=9800, speedup=18.8, exc=4),
    "textlab/num/primes.py::factorize": dict(
        share=0.016, calls=3000, speedup=12.9, elig="fixable", types=(["int"], "list[int]"),
        reason="unannotated, and tuple unpacking from divmod() is outside PySub: rewrite with // and %",
        attempts=['''def factorize(n: int) -> list[int]:
    out: list[int] = []
    p: int = 2
    while p * p <= n:
        q, r = divmod(n, p)
        while r == 0:
            out.append(p)
            n = q
            q, r = divmod(n, p)
        p += 1
    if n > 1:
        out.append(n)
    return out
''', '''def factorize(n: int) -> list[int]:
    out: list[int] = []
    p: int = 2
    while p * p <= n:
        while n % p == 0:
            out.append(p)
            n = n // p
        p += 1
    if n > 1:
        out.append(n)
    return out
''']),
    "textlab/num/primes.py::fib_big": dict(
        st="failed", share=0.005, calls=640, speedup=None,
        reason="replay mismatch: fib_big(94) is 19740274219868223167 in CPython but exceeds int64, so the compiled code raises OverflowError",
        mismatch=dict(args="(94,)", python="19740274219868223167", cpp="OverflowError: integer overflow in '+'", kind="exception")),
    "textlab/num/primes.py::digit_sum": dict(share=0.002, calls=7100, speedup=5.2),
    "textlab/num/primes.py::isqrt": dict(share=0.001, calls=500, speedup=7.4),
    "textlab/num/primes.py::is_perfect": dict(st="guarded", share=0.003, calls=240, speedup=24.9, exc=0),

    # ---- stats.py ---------------------------------------------------------------------------
    "textlab/util/stats.py::mean": dict(
        share=0.004, calls=2600, speedup=3.6, types=(["list[float]"], "float"),
        annotated='''def mean(xs: list[float]) -> float:
    total: float = 0.0
    for x in xs:
        total += x
    return total / len(xs)
'''),
    "textlab/util/stats.py::variance": dict(share=0.009, calls=2600, speedup=8.4),
    "textlab/util/stats.py::stddev": dict(
        st="not_eligible", elig="not_eligible", share=0.001, calls=2600,
        reason="calls math.sqrt (module 'math' is not supported; use x ** 0.5)",
        diag=_D((24, 12, "TypeError", "name 'math' is not defined"))),
    "textlab/util/stats.py::median": dict(
        share=0.007, calls=900, speedup=7.9, elig="fixable", types=(["list[float]"], "float"),
        reason="sorted() is not defined in PySub: rewrite with an explicit insertion sort",
        attempts=['''def median(xs: list[float]) -> float:
    ys: list[float] = sorted(xs)
    n: int = len(ys)
    if n % 2 == 1:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0
''', '''def median(xs: list[float]) -> float:
    ys: list[float] = []
    for x in xs:
        ys.append(x)
    for i in range(1, len(ys)):
        key: float = ys[i]
        j: int = i - 1
        while j >= 0 and ys[j] > key:
            ys[j + 1] = ys[j]
            j -= 1
        ys[j + 1] = key
    n: int = len(ys)
    if n % 2 == 1:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0
''']),
    "textlab/util/stats.py::percentile": dict(
        st="not_eligible", elig="fixable", share=0.005, calls=900, types=(["list[float]", "float"], "float"),
        reason="LLM rewrite needs sorted() and float-to-int truncation semantics it could not reproduce under replay-safe PySub",
        attempts=['''def percentile(xs: list[float], q: float) -> float:
    ys: list[float] = sorted(xs)
    return ys[int((len(ys) - 1) * q)]
''', '''def percentile(xs: list[float], q: float) -> float:
    ys: list[float] = xs.sort()
    return ys[int((len(ys) - 1) * q)]
''', '''def percentile(xs: list[float], q: float) -> float:
    return xs[int((len(xs) - 1) * q)]
'''], fail=True),
    "textlab/util/stats.py::histogram": dict(share=0.014, calls=300, speedup=16.2, arg_elems=20000.0, ret_elems=64.0),
    "textlab/util/stats.py::moving_average": dict(
        share=0.012, calls=40, speedup=13.1, types=(["list[float]", "int"], "list[float]"),
        annotated='''def moving_average(xs: list[float], window: int) -> list[float]:
    out: list[float] = []
    acc: float = 0.0
    for i in range(len(xs)):
        acc += xs[i]
        if i >= window:
            acc -= xs[i - window]
        if i >= window - 1:
            out.append(acc / window)
    return out
'''),
    "textlab/util/stats.py::cumulative_sum": dict(share=0.002, calls=700, speedup=6.0),
    "textlab/util/stats.py::argmax": dict(share=0.001, calls=1300, speedup=4.7),
    "textlab/util/stats.py::clamp": dict(share=0.002, calls=22000, speedup=1.4),
    "textlab/util/stats.py::zscore": dict(share=0.003, calls=300, speedup=9.0),
    "textlab/util/stats.py::mode_of": dict(
        st="not_eligible", elig="not_eligible", share=0.002, calls=40,
        reason="uses collections.Counter and tuple indexing; no PySub model for either",
        diag=_D((54, 12, "TypeError", "name 'Counter' is not defined"))),

    # ---- vectorize.py -----------------------------------------------------------------------
    "textlab/features/vectorize.py::tfidf_matrix": dict(st="not_eligible", elig="not_eligible", share=0.058, calls=6, reason=_NP, diag=_D((2, 8, "SyntaxError", "import statements are outside the PySub subset"), (8, 10, "TypeError", "name 'np' is not defined"))),
    "textlab/features/vectorize.py::to_dense": dict(st="not_eligible", elig="not_eligible", share=0.007, calls=6, reason=_NP, diag=_D((15, 12, "TypeError", "name 'np' is not defined"))),
    "textlab/features/vectorize.py::cosine_sim": dict(
        st="declined", share=0.027, calls=3200, probe=0.58, arg_elems=512.0, ret_elems=1.0, boundary=0.52,
        reason="two 512-float vectors per call: copying 1,024 floats (~2.4 us) outweighs the ~1.1 us of arithmetic saved"),
    "textlab/features/vectorize.py::hash_features": dict(st="guarded", share=0.021, calls=1800, speedup=15.7, exc=3),
    "textlab/features/vectorize.py::l2_normalize": dict(
        share=0.013, calls=1800, speedup=8.3, elig="fixable", types=(["list[float]"], "list[float]"),
        reason="generator expression, sum() and math.sqrt are outside PySub: rewrite with loops and ** 0.5",
        attempts=['''def l2_normalize(vec: list[float]) -> list[float]:
    norm: float = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec
''', '''def l2_normalize(vec: list[float]) -> list[float]:
    acc: float = 0.0
    for v in vec:
        acc += v * v
    norm: float = acc ** 0.5
    if norm == 0.0:
        return vec
    out: list[float] = []
    for v in vec:
        out.append(v / norm)
    return out
''']),
    "textlab/features/vectorize.py::bucketize": dict(share=0.005, calls=44000, speedup=3.3),
    "textlab/features/vectorize.py::one_hot": dict(share=0.002, calls=900, speedup=5.9),
    "textlab/features/vectorize.py::softmax": dict(
        st="not_eligible", elig="fixable", share=0.003, calls=60,
        reason="needs math.exp, which PySub does not provide, so no behaviour-preserving rewrite exists",
        attempts=['''def softmax(xs: list[float]) -> list[float]:
    m: float = max(xs)
    es: list[float] = [math.exp(x - m) for x in xs]
    return es
''', '''def softmax(xs: list[float]) -> list[float]:
    out: list[float] = []
    for x in xs:
        out.append(2.718281828459045 ** x)
    return out
''', '''def softmax(xs: list[float]) -> list[float]:
    m: float = xs[0]
    for x in xs:
        m = max(m, x)
    out: list[float] = []
    for x in xs:
        out.append((2.718281828459045 ** (x - m)))
    return out
'''], fail=True, types=(["list[float]"], "list[float]"),
        replay_err="replay mismatch: softmax([0.1, 2.3, -4.0]) differs from CPython in the last bit (x ** y is not math.exp)"),
    "textlab/features/vectorize.py::feature_names": dict(
        st="not_eligible", elig="not_eligible", share=0.001, calls=2,
        reason="returns a dict in one branch and a list in the other (dynamic typing)",
        diag=_D((58, 12, "TypeError", "variable type changes: dict[str, int] vs list"))),

    # ---- loader.py --------------------------------------------------------------------------
    "textlab/io/loader.py::load_corpus": dict(st="not_eligible", elig="not_eligible", share=0.033, calls=1, reason=_OPEN, diag=_D((6, 10, "SyntaxError", "'with' statements are outside the PySub subset"))),
    "textlab/io/loader.py::parse_row": dict(st="not_eligible", elig="not_eligible", share=0.012, calls=14000, reason="returns int, float or str depending on the input (dynamic typing)", diag=_D((16, 16, "TypeError", "function return type changes: int vs float vs str"))),
    "textlab/io/loader.py::iter_batches": dict(st="not_eligible", elig="not_eligible", share=0.004, calls=3, reason="is a generator ('yield'); generators are outside PySub", diag=_D((26, 9, "SyntaxError", "'yield' is outside the PySub subset"))),
    "textlab/io/loader.py::read_config": dict(st="not_eligible", elig="not_eligible", share=0.0, calls=1, reason="uses file I/O and the json module", diag=_D((31, 10, "SyntaxError", "'with' statements are outside the PySub subset"))),
    "textlab/io/loader.py::save_results": dict(st="not_eligible", elig="not_eligible", share=0.004, calls=1, reason="uses file I/O and the csv module", diag=_D((37, 10, "SyntaxError", "'with' statements are outside the PySub subset"))),
    "textlab/io/loader.py::checksum_file": dict(st="not_eligible", elig="not_eligible", calls=None, share=None, reason="uses hashlib and binary file I/O", diag=_D((45, 9, "TypeError", "name 'hashlib' is not defined"))),

    # ---- linalg.py --------------------------------------------------------------------------
    "textlab/matrix/linalg.py::matmul": dict(share=0.22, calls=260, speedup=44.0, arg_elems=40000.0, ret_elems=10000.0),
    "textlab/matrix/linalg.py::transpose": dict(share=0.012, calls=260, speedup=11.2, arg_elems=10000.0, ret_elems=10000.0),
    "textlab/matrix/linalg.py::mat_vec": dict(share=0.018, calls=900, speedup=26.8),
    "textlab/matrix/linalg.py::identity": dict(share=0.001, calls=40, speedup=10.5),
    "textlab/matrix/linalg.py::trace": dict(share=0.001, calls=40, speedup=6.6),
    "textlab/matrix/linalg.py::frobenius": dict(share=0.003, calls=300, speedup=7.9),
    "textlab/matrix/linalg.py::row_sums": dict(share=0.004, calls=300, speedup=12.5),
    "textlab/matrix/linalg.py::outer": dict(share=0.002, calls=100, speedup=9.2),

    # ---- pipeline / main --------------------------------------------------------------------
    "textlab/pipeline/runner.py::timed": dict(st="not_eligible", elig="not_eligible", share=0.0, calls=3, reason="returns a closure (decorator factory)", diag=_D((6, 5, "SyntaxError", "nested function definitions are outside the PySub subset"))),
    "textlab/pipeline/runner.py::timed.<locals>.deco": dict(st="not_eligible", elig="not_eligible", reason="nested function", diag=_D((7, 9, "SyntaxError", "nested function definitions are outside the PySub subset"))),
    "textlab/pipeline/runner.py::timed.<locals>.deco.<locals>.wrapper": dict(st="not_eligible", elig="not_eligible", reason="nested function", diag=_D((8, 13, "SyntaxError", "variadic arguments are outside the PySub subset"))),
    "textlab/pipeline/runner.py::dedup": dict(st="not_eligible", elig="not_eligible", share=0.051, calls=1, reason="uses all() over a generator expression and a decorator", diag=_D((17, 12, "SyntaxError", "generator expressions are outside the PySub subset"))),
    "textlab/pipeline/runner.py::run_pipeline": dict(st="not_eligible", elig="not_eligible", share=0.0, calls=1, reason="calls file I/O helpers and unpacks tuples", diag=_D((25, 9, "SyntaxError", "tuple unpacking is outside the PySub subset"))),
    "main.py::parse_args": dict(st="not_eligible", elig="not_eligible", share=0.0, calls=1, reason="uses argparse", diag=_D((8, 10, "TypeError", "name 'argparse' is not defined"))),
    "main.py::main": dict(st="not_eligible", elig="not_eligible", share=0.0, calls=1, reason="entry point: prints, reads files and calls non-PySub code", diag=_D((14, 12, "TypeError", "name 'run_pipeline' is not defined"))),
}

# trace profile defaults for the e2e numbers
TRACE_CMD = "python main.py --small"
E2E = dict(before_s=14.62, after_s=4.31)
