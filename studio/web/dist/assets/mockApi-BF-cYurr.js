var Ge=Object.defineProperty;var He=(r,e,t)=>e in r?Ge(r,e,{enumerable:!0,configurable:!0,writable:!0,value:t}):r[e]=t;var ke=(r,e,t)=>He(r,typeof e!="symbol"?e+"":e,t);const Ae={"textlab/__init__.py":'"""textlab: a small text and clustering toolkit."""',"textlab/main.py":`import argparse
import time

from textlab.text.distance import fuzzy_dedupe
from textlab.ml.kmeans import assign_clusters
`,"textlab/report.py":`import statistics
`,"textlab/text/distance.py":`"""String distances used for fuzzy de-duplication."""
`,"textlab/text/tokenize.py":`import re
import unicodedata

STOPWORDS = set(open("stopwords.txt").read().split())
`,"textlab/text/features.py":`import numpy as np

VOCAB_LIMIT = 50000
`,"textlab/ml/kmeans.py":`"""Hand-written k-means building blocks."""
`,"textlab/sim/nbody.py":`"""Direct-summation n-body step."""
`,"textlab/data/loader.py":`import json
`,"textlab/utils/mathx.py":`"""Small numeric helpers."""
`,"textlab/utils/cache.py":`import functools
import time
`},Se=[{file:"textlab/text/distance.py",kind:"v",share:.205,calls:1204,speedup:38.2,elems:38,src:`def edit_distance(a: str, b: str) -> int:
    n = len(a)
    m = len(b)
    prev: list[int] = []
    for j in range(m + 1):
        prev.append(j)
    for i in range(1, n + 1):
        cur = [i]
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[m]`},{file:"textlab/text/distance.py",kind:"v",share:.031,calls:3120,speedup:29.7,elems:41,src:`def lcs_length(a: str, b: str) -> int:
    table: list[list[int]] = []
    for i in range(len(a) + 1):
        table.append([0] * (len(b) + 1))
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    return table[len(a)][len(b)]`},{file:"textlab/text/distance.py",kind:"v",share:.012,calls:9400,speedup:21.4,elems:24,src:`def hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return -1
    diff = 0
    for i in range(len(a)):
        if a[i] != b[i]:
            diff += 1
    return diff`},{file:"textlab/text/distance.py",kind:"a",share:.017,calls:5200,speedup:17.8,elems:30,src:`def similarity(a, b):
    if len(a) == 0 or len(b) == 0:
        return 0.0
    matches = 0
    for ch in a:
        if ch in b:
            matches += 1
    return 2.0 * matches / (len(a) + len(b))`,annotated:`def similarity(a: str, b: str) -> float:
    if len(a) == 0 or len(b) == 0:
        return 0.0
    matches = 0
    for ch in a:
        if ch in b:
            matches += 1
    return 2.0 * matches / (len(a) + len(b))`,reason:"Parameters are unannotated; observed types (str, str) -> float supply the annotations."},{file:"textlab/text/distance.py",kind:"v",share:.004,calls:800,speedup:12.1,elems:18,src:`def common_prefix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return i`},{file:"textlab/text/distance.py",kind:"v",share:.006,calls:1204,speedup:33,elems:38,src:`def normalized_distance(a: str, b: str) -> float:
    longest = max(len(a), len(b))
    if longest == 0:
        return 0.0
    return edit_distance(a, b) / longest`},{file:"textlab/text/distance.py",kind:"v",share:.052,calls:40,speedup:27.6,elems:600,src:`def fuzzy_dedupe(words: list[str], max_dist: int) -> list[int]:
    keep: list[int] = []
    for i in range(len(words)):
        dup = False
        for k in keep:
            if edit_distance(words[i], words[k]) <= max_dist:
                dup = True
                break
        if not dup:
            keep.append(i)
    return keep`},{file:"textlab/text/tokenize.py",kind:"v",share:.092,calls:410,speedup:24.6,elems:4200,src:`def count_pairs(ids: list[int]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for i in range(len(ids) - 1):
        key = ids[i] * 65536 + ids[i + 1]
        counts[key] = counts.get(key, 0) + 1
    return counts`},{file:"textlab/text/tokenize.py",kind:"g",share:.024,calls:410,speedup:18.3,elems:4200,src:`def merge_pair(ids: list[int], a: int, b: int, new_id: int) -> list[int]:
    out: list[int] = []
    i = 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == a and ids[i + 1] == b:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out`,extraNotes:[{line:2,cls:"D7 memory is not reclaimed",detail:"The runtime does not free the list built inside the call; a long-lived process would grow with every merge.",mitigation:"An arena releases all allocations made during one call after the result has been copied back to Python.",severity:"divergent"}]},{file:"textlab/text/tokenize.py",kind:"l",share:.071,calls:2210,speedup:14.9,elems:120,src:`def char_histogram(text):
    letters = [c for c in text if c.isalpha()]
    counts = {}
    for c in letters:
        counts[c] = counts.get(c, 0) + 1
    return counts`,annotated:`def char_histogram(text: str) -> dict[str, int]:
    letters = [c for c in text if c.isalpha()]
    counts = {}
    for c in letters:
        counts[c] = counts.get(c, 0) + 1
    return counts`,attempts:[{source:"api",error:"line 6: method 'isalpha' of str is not part of PySub; call ord() and compare code points",pysub:`def char_histogram(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in text:
        if c.isalpha():
            counts[c] = counts.get(c, 0) + 1
    return counts`},{source:"api",error:null,pysub:`def char_histogram(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in text:
        o = ord(c)
        if (o >= 65 and o <= 90) or (o >= 97 and o <= 122):
            counts[c] = counts.get(c, 0) + 1
    return counts`}],reason:"List comprehension is outside PySub; a loop rewrite is straightforward."},{file:"textlab/text/tokenize.py",kind:"l",share:.038,calls:2210,speedup:11.2,elems:120,src:`def split_words(text):
    words = []
    start = 0
    for i, ch in enumerate(text):
        if ch == " ":
            if i > start:
                words.append(text[start:i])
            start = i + 1
    if start < len(text):
        words.append(text[start:])
    return words`,annotated:`def split_words(text: str) -> list[str]:
    words = []
    start = 0
    for i, ch in enumerate(text):
        if ch == " ":
            if i > start:
                words.append(text[start:i])
            start = i + 1
    if start < len(text):
        words.append(text[start:])
    return words`,attempts:[{source:"cache",error:null,pysub:`def split_words(text: str) -> list[str]:
    words: list[str] = []
    start = 0
    for i in range(len(text)):
        if text[i] == " ":
            if i > start:
                words.append(text[start:i])
            start = i + 1
    if start < len(text):
        words.append(text[start:])
    return words`}],reason:"enumerate() is not part of PySub."},{file:"textlab/text/tokenize.py",kind:"n",share:.021,calls:2210,reason:"Calls re.sub: module `re` is not available in PySub (no imports).",src:`def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\\s+", " ", text).strip()`},{file:"textlab/text/tokenize.py",kind:"n",share:.006,calls:410,reason:"Calls unicodedata.normalize: external module, non-ASCII text handling.",src:`def strip_accents(text):
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))`},{file:"textlab/text/tokenize.py",kind:"n",share:.003,calls:8800,reason:"Reads module-level set STOPWORDS built at import time from a file (not a literal constant).",src:`def is_stopword(word: str) -> bool:
    return word in STOPWORDS`},{file:"textlab/text/features.py",kind:"g",share:.043,calls:6100,speedup:26.1,elems:22,src:`def ngram_hash(s: str, n: int) -> int:
    h = 7
    for i in range(len(s) - n + 1):
        for j in range(n):
            h = (h * 31 + ord(s[i + j])) % 1000000007
    return h`},{file:"textlab/text/features.py",kind:"v",share:.016,calls:52e3,speedup:45.3,elems:1,src:`def is_prime(n: int) -> bool:
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True`},{file:"textlab/text/features.py",kind:"v",share:.054,calls:6,speedup:61.8,elems:1,src:`def prime_count(limit: int) -> int:
    sieve = [True] * (limit + 1)
    count = 0
    for i in range(2, limit + 1):
        if sieve[i]:
            count += 1
            for j in range(i * i, limit + 1, i):
                sieve[j] = False
    return count`},{file:"textlab/text/features.py",kind:"v",share:.011,calls:2210,speedup:19.5,elems:120,src:`def vowel_ratio(s: str) -> float:
    if len(s) == 0:
        return 0.0
    vowels = 0
    for ch in s:
        if ch in "aeiouAEIOU":
            vowels += 1
    return vowels / len(s)`},{file:"textlab/text/features.py",kind:"d",share:.034,calls:1e6,probe:.62,elems:1e4,reason:"Compiles and typechecks, but the ranker predicts a net loss: 1,000,000 calls each marshal a 10,000-element list (about 80 MB per second of copying) for about 2 microseconds of arithmetic saved.",src:`def rolling_checksum(data: list[int]) -> int:
    acc = 0
    for i in range(len(data)):
        acc = (acc * 31 + data[i]) % 65521
    return acc`},{file:"textlab/text/features.py",kind:"v",share:.002,calls:3300,speedup:9.4,elems:1,src:`def tfidf_weight(tf: int, df: int, n_docs: int) -> float:
    if df == 0:
        return 0.0
    return (1.0 + tf) * (n_docs / df)`},{file:"textlab/text/features.py",kind:"lx",share:.019,calls:410,src:`def build_feature_vector(doc):
    counts = {w: doc.count(w) for w in set(doc.split())}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [v for _, v in ranked[:64]]`,annotated:`def build_feature_vector(doc: str) -> list[int]:
    counts = {w: doc.count(w) for w in set(doc.split())}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [v for _, v in ranked[:64]]`,attempts:[{source:"api",error:"line 2: dict comprehension is not part of PySub",pysub:`def build_feature_vector(doc: str) -> list[int]:
    counts: dict[str, int] = {}
    for w in set(doc.split()):
        counts[w] = doc.count(w)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [v for _, v in ranked[:64]]`},{source:"api",error:"line 5: sorted() with a key function (lambda) is not part of PySub",pysub:`def build_feature_vector(doc: str) -> list[int]:
    counts: dict[str, int] = {}
    for w in doc.split():
        counts[w] = counts.get(w, 0) + 1
    values: list[int] = []
    for w in counts:
        values.append(counts[w])
    values.sort(key=lambda v: -v)
    return values[:64]`},{source:"api",error:"line 8: lambda is not part of PySub; sort() takes no key argument",pysub:`def build_feature_vector(doc: str) -> list[int]:
    counts: dict[str, int] = {}
    for w in doc.split():
        counts[w] = counts.get(w, 0) + 1
    values: list[int] = []
    for w in counts:
        values.append(counts[w])
    values.sort(reverse=True)
    return values[:64]`}],reason:"LLM rewrite did not pass the typechecker after 3 attempts: sort(reverse=True) keyword arguments are not part of PySub. Left as Python."},{file:"textlab/text/features.py",kind:"n",share:.008,calls:60,reason:"Calls numpy (np.zeros, np.dot): third-party array library is outside PySub.",src:`def tfidf_matrix(docs, vocab):
    m = np.zeros((len(docs), len(vocab)))
    for i, d in enumerate(docs):
        for j, w in enumerate(vocab):
            m[i, j] = d.count(w)
    return m @ m.T`},{file:"textlab/text/features.py",kind:"fx",share:.003,calls:60,reason:"Fixable (sorted with a key function), but only 0.3% of runtime: below the rewrite threshold, so no LLM call was spent.",src:`def top_k_terms(counts, k):
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [w for w, _ in ranked[:k]]`},{file:"textlab/ml/kmeans.py",kind:"v",share:.028,calls:48e4,speedup:31.4,elems:8,src:`def dist2(p: list[float], q: list[float]) -> float:
    total = 0.0
    for i in range(len(p)):
        d = p[i] - q[i]
        total += d * d
    return total`},{file:"textlab/ml/kmeans.py",kind:"v",share:.142,calls:60,speedup:42.7,elems:8e3,src:`def assign_clusters(points: list[list[float]], cents: list[list[float]]) -> list[int]:
    labels: list[int] = []
    for p in points:
        best = 0
        best_d = dist2(p, cents[0])
        for c in range(1, len(cents)):
            d = dist2(p, cents[c])
            if d < best_d:
                best_d = d
                best = c
        labels.append(best)
    return labels`},{file:"textlab/ml/kmeans.py",kind:"v",share:.047,calls:60,speedup:27.9,elems:8e3,src:`def update_centroids(points: list[list[float]], labels: list[int], k: int) -> list[list[float]]:
    dim = len(points[0])
    sums: list[list[float]] = []
    counts: list[int] = []
    for c in range(k):
        sums.append([0.0] * dim)
        counts.append(0)
    for i in range(len(points)):
        c = labels[i]
        counts[c] += 1
        for j in range(dim):
            sums[c][j] += points[i][j]
    for c in range(k):
        if counts[c] > 0:
            for j in range(dim):
                sums[c][j] = sums[c][j] / counts[c]
    return sums`},{file:"textlab/ml/kmeans.py",kind:"v",share:.009,calls:60,speedup:36.8,elems:8e3,src:`def inertia(points: list[list[float]], cents: list[list[float]], labels: list[int]) -> float:
    total = 0.0
    for i in range(len(points)):
        total += dist2(points[i], cents[labels[i]])
    return total`},{file:"textlab/ml/kmeans.py",kind:"g",share:.001,calls:1,speedup:6.2,elems:8e3,src:`def init_centroids(points: list[list[float]], k: int, seed: int) -> list[list[float]]:
    state = seed
    chosen: list[list[float]] = []
    for c in range(k):
        state = (state * 1103515245 + 12345) % 2147483648
        chosen.append(points[state % len(points)])
    return chosen`},{file:"textlab/sim/nbody.py",kind:"v",share:.171,calls:300,speedup:54,elems:96,src:`def step(pos: list[float], vel: list[float], mass: list[float], dt: float) -> None:
    n = len(mass)
    for i in range(n):
        for j in range(n):
            if i != j:
                dx = pos[3 * j] - pos[3 * i]
                dy = pos[3 * j + 1] - pos[3 * i + 1]
                dz = pos[3 * j + 2] - pos[3 * i + 2]
                d2 = dx * dx + dy * dy + dz * dz + 0.01
                inv = mass[j] / (d2 * d2 ** 0.5)
                vel[3 * i] += dx * inv * dt
                vel[3 * i + 1] += dy * inv * dt
                vel[3 * i + 2] += dz * inv * dt
    for i in range(3 * n):
        pos[i] += vel[i] * dt`},{file:"textlab/sim/nbody.py",kind:"v",share:.014,calls:30,speedup:40.2,elems:96,src:`def energy(pos: list[float], vel: list[float], mass: list[float]) -> float:
    n = len(mass)
    e = 0.0
    for i in range(n):
        v2 = vel[3 * i] * vel[3 * i] + vel[3 * i + 1] * vel[3 * i + 1] + vel[3 * i + 2] * vel[3 * i + 2]
        e += 0.5 * mass[i] * v2
    return e`},{file:"textlab/sim/nbody.py",kind:"v",share:.002,calls:30,speedup:15.3,elems:96,src:`def center_of_mass(pos: list[float], mass: list[float]) -> list[float]:
    total = 0.0
    c = [0.0, 0.0, 0.0]
    for i in range(len(mass)):
        total += mass[i]
        for k in range(3):
            c[k] += pos[3 * i + k] * mass[i]
    for k in range(3):
        c[k] = c[k] / total
    return c`},{file:"textlab/sim/nbody.py",kind:"n",share:.001,calls:8,reason:"Method of class Body: v1 only compiles module-level functions.",src:`def kinetic(self):
        return 0.5 * self.mass * (self.vx ** 2 + self.vy ** 2 + self.vz ** 2)`},{file:"textlab/data/loader.py",kind:"n",share:.018,calls:1,reason:"Performs file I/O (open, read): outside PySub.",src:`def read_corpus(path):
    with open(path) as fh:
        return [line.strip() for line in fh if line.strip()]`},{file:"textlab/data/loader.py",kind:"a",share:.005,calls:4100,speedup:8.7,elems:80,src:`def parse_line(line):
    parts = line.split(",")
    return [p.strip() for p in parts]`,annotated:`def parse_line(line: str) -> list[str]:
    parts = line.split(",")
    return [p.strip() for p in parts]`,reason:"List comprehension with method call: left as Python."},{file:"textlab/data/loader.py",kind:"n",share:.001,calls:1,reason:"Imports json and reads a file.",src:`def load_labels(path):
    with open(path) as fh:
        return json.load(fh)`},{file:"textlab/utils/mathx.py",kind:"v",share:.003,calls:12e4,speedup:14.1,elems:1,src:`def clamp(x: int, lo: int, hi: int) -> int:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x`},{file:"textlab/utils/mathx.py",kind:"v",share:.002,calls:9e3,speedup:17.2,elems:1,src:`def gcd(a: int, b: int) -> int:
    while b != 0:
        t = a % b
        a = b
        b = t
    return a`},{file:"textlab/utils/mathx.py",kind:"v",share:.002,calls:2e3,speedup:22.4,elems:1,src:`def collatz_steps(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:7e3,speedup:10.8,elems:1,src:`def digit_sum(n: int) -> int:
    total = 0
    while n > 0:
        total += n % 10
        n = n // 10
    return total`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:7e3,speedup:11.9,elems:1,src:`def popcount(n: int) -> int:
    count = 0
    while n > 0:
        count += n & 1
        n = n >> 1
    return count`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:400,speedup:25.5,elems:1,src:`def fib(n: int) -> int:
    a = 0
    b = 1
    for i in range(n):
        t = a + b
        a = b
        b = t
    return a`},{file:"textlab/utils/mathx.py",kind:"g",share:.001,calls:300,speedup:19,elems:1,src:`def power_mod(base: int, exp: int, mod: int) -> int:
    result = 1
    base = base % mod
    while exp > 0:
        if exp % 2 == 1:
            result = result * base % mod
        exp = exp // 2
        base = base * base % mod
    return result`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:500,speedup:13.3,elems:1,src:`def isqrt(n: int) -> int:
    if n < 2:
        return n
    lo = 1
    hi = n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid * mid <= n:
            lo = mid
        else:
            hi = mid - 1
    return lo`},{file:"textlab/utils/mathx.py",kind:"v",share:.002,calls:1800,speedup:20.7,elems:240,src:`def mean(xs: list[float]) -> float:
    if len(xs) == 0:
        return 0.0
    total = 0.0
    for x in xs:
        total += x
    return total / len(xs)`},{file:"textlab/utils/mathx.py",kind:"v",share:.002,calls:1800,speedup:19.8,elems:240,src:`def variance(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    m = mean(xs)
    acc = 0.0
    for x in xs:
        acc += (x - m) * (x - m)
    return acc / n`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:15e3,speedup:8.9,elems:1,src:`def abs_diff(a: int, b: int) -> int:
    if a > b:
        return a - b
    return b - a`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:15e3,speedup:8.1,elems:1,src:`def sign(x: float) -> int:
    if x > 0.0:
        return 1
    if x < 0.0:
        return -1
    return 0`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:3e3,speedup:9.9,elems:1,src:`def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t`},{file:"textlab/utils/mathx.py",kind:"v",share:.001,calls:800,speedup:16.5,elems:1,src:`def is_even(n: int) -> bool:
    return n % 2 == 0`},{file:"textlab/utils/mathx.py",kind:"f",share:.004,calls:3600,elems:1,mismatch:{args:"(2.5,)",python:"2",cpp:"3",kind:"value"},src:`def round_half_even(x: float) -> int:
    return int(round(x))`,reason:"Replay mismatch: Python round() is round-half-to-even; the generated C++ rounds half away from zero. First counterexample: round_half_even(2.5) -> Python 2, C++ 3."},{file:"textlab/utils/mathx.py",kind:"fx",share:.002,calls:120,reason:"Fixable (sorted() is outside PySub), but only 0.2% of runtime: below the rewrite threshold.",src:`def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2`},{file:"textlab/utils/cache.py",kind:"n",share:.003,calls:12,reason:"Defines a closure: inner function `wrapper` captures `cache` from the enclosing scope.",src:`def memoize(fn):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    return wrapper`},{file:"textlab/utils/cache.py",kind:"n",share:.001,calls:40,reason:"Nested function and dynamic typing (returns a callable).",src:`def timed(label):
    def deco(fn):
        def inner(*a, **k):
            t0 = time.perf_counter()
            r = fn(*a, **k)
            print(label, time.perf_counter() - t0)
            return r
        return inner
    return deco`},{file:"textlab/report.py",kind:"n",share:.002,calls:1,reason:"Uses f-strings and str.join over a generator.",src:`def format_table(rows):
    width = max(len(r[0]) for r in rows)
    return "\\n".join(f"{name:<{width}}  {val:8.2f}" for name, val in rows)`},{file:"textlab/report.py",kind:"n",share:.001,calls:1,reason:"Calls statistics.mean/stdev: module `statistics` is not available in PySub.",src:`def summarize(values):
    return statistics.mean(values), statistics.stdev(values)`},{file:"textlab/main.py",kind:"n",share:.004,calls:1,reason:"Calls argparse.ArgumentParser: module `argparse` is not part of PySub.",src:`def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true")
    return ap.parse_args()`},{file:"textlab/main.py",kind:"n",share:.012,calls:1,reason:"Orchestrates other modules, prints, and reads files (I/O and calls into non-PySub code).",src:`def run_pipeline(small):
    corpus = read_corpus("data/corpus.txt")
    words = [w for line in corpus for w in split_words(normalize(line))]
    keep = fuzzy_dedupe(words[: 600 if small else 4000], 2)
    print("kept", len(keep), "of", len(words))
    return keep`},{file:"textlab/main.py",kind:"n",share:.003,calls:1,reason:"Entry point: prints, times execution with time.perf_counter, calls argparse.",src:`def main():
    args = parse_args()
    t0 = time.perf_counter()
    run_pipeline(args.small)
    print("done in", round(time.perf_counter() - t0, 2), "s")`}],Je=new Set(["def","return","if","elif","else","for","while","in","not","and","or","True","False","None","pass","break","continue","import","from","class","lambda","is","with","try","except","global"]),Ve=["**=","//=","<<=",">>="],Xe=["==","!=","<=",">=","+=","-=","*=","/=","%=","//","**","->","<<",">>","&=","|="];function Qe(r){const e=[],t=r.replace(/\r\n/g,`
`).split(`
`),o=[0];let d=0;for(let i=0;i<t.length;i++){const c=t[i],p=i+1;let g=0;if(d===0){const P=/^[ \t]*/.exec(c),k=P[0].replace(/\t/g,"    ").length,m=c.slice(P[0].length);if(m===""||m.startsWith("#"))continue;if(k>o[o.length-1])o.push(k),e.push({kind:"INDENT",value:"",line:p,col:1});else for(;k<o[o.length-1];)o.pop(),e.push({kind:"DEDENT",value:"",line:p,col:1});g=P[0].length}for(;g<c.length;){const P=c[g];if(P===" "||P==="	"){g++;continue}if(P==="#")break;const k=g+1;if(/[A-Za-z_]/.test(P)){let m=g;for(;m<c.length&&/\w/.test(c[m]);)m++;const w=c.slice(g,m);e.push({kind:Je.has(w)?"KEYWORD":"NAME",value:w,line:p,col:k}),g=m}else if(/\d/.test(P)||P==="."&&/\d/.test(c[g+1]??"")){const m=/^(0[xX][0-9a-fA-F_]+|\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?|\.\d+)/.exec(c.slice(g));e.push({kind:"NUMBER",value:m[0],line:p,col:k}),g+=m[0].length}else if(P==='"'||P==="'"){if(c.startsWith(P.repeat(3),g)){const u=c.indexOf(P.repeat(3),g+3);if(e.push({kind:"STRING",value:'"""…"""',line:p,col:k}),u>=0){g=u+3;continue}let l=i+1;for(;l<t.length&&!t[l].includes(P.repeat(3));)l++;i=l;break}let w=g+1;for(;w<c.length&&c[w]!==P;)w+=c[w]==="\\"?2:1;e.push({kind:"STRING",value:c.slice(g,w+1),line:p,col:k}),g=w+1}else{const m=c.slice(g,g+3),w=c.slice(g,g+2),u=Ve.includes(m)?m:Xe.includes(w)?w:P;"([{".includes(u)&&d++,")]}".includes(u)&&(d=Math.max(0,d-1)),e.push({kind:"OP",value:u,line:p,col:k}),g+=u.length}}d===0&&e.push({kind:"NEWLINE",value:"",line:p,col:c.length+1})}for(;o.length>1;)o.pop(),e.push({kind:"DEDENT",value:"",line:t.length,col:1});return e.push({kind:"ENDMARKER",value:"",line:t.length+1,col:1}),e}class Q extends Error{constructor(t,o,d){super(t);ke(this,"line");ke(this,"col");this.line=o,this.col=d}}const R=(r,e,t,o)=>({t:r,line:e.line,col:e.col,ty:null,...t?{attrs:t}:{},...o?{kids:o}:{}});class et{constructor(e){ke(this,"p",0);this.toks=e}get cur(){return this.toks[this.p]}peekIs(e){return this.cur.value===e&&(this.cur.kind==="OP"||this.cur.kind==="KEYWORD")}accept(e){return this.peekIs(e)?(this.p++,!0):!1}expect(e){if(!this.accept(e))throw new Q(`expected '${e}' but found '${this.cur.value||this.cur.kind.toLowerCase()}'`,this.cur.line,this.cur.col)}expectKind(e){if(this.cur.kind!==e)throw new Q(`expected ${e.toLowerCase()} but found '${this.cur.value||this.cur.kind.toLowerCase()}'`,this.cur.line,this.cur.col);return this.toks[this.p++]}module(){const e=[];for(;this.cur.kind!=="ENDMARKER";){if(this.cur.kind==="NEWLINE"){this.p++;continue}e.push(this.stmt())}return R("Module",{line:1,col:1},void 0,{body:e})}block(){this.expect(":");const e=[];if(this.cur.kind==="NEWLINE"){for(this.p++,this.expectKind("INDENT");this.cur.kind!=="DEDENT"&&this.cur.kind!=="ENDMARKER";){if(this.cur.kind==="NEWLINE"){this.p++;continue}e.push(this.stmt())}this.cur.kind==="DEDENT"&&this.p++}else e.push(this.simple());return e}stmt(){const e=this.cur;if(e.kind==="KEYWORD")switch(e.value){case"def":return this.funcdef();case"if":return this.ifstmt();case"while":{this.p++;const t=this.expr();return R("While",e,void 0,{test:t,body:this.block()})}case"for":{this.p++;const t=this.targetList();this.expect("in");const o=this.expr(),d=this.block();return R("For",e,void 0,{target:t,iter:o,body:d})}case"class":throw new Q("classes are not supported in the playground subset",e.line,e.col);case"import":case"from":throw new Q("imports are not part of PySub",e.line,e.col);case"lambda":throw new Q("lambda is not part of PySub",e.line,e.col)}return this.simple()}targetList(){const e=this.postfix();if(this.peekIs(",")){const t=[e];for(;this.accept(",")&&!this.peekIs("in");)t.push(this.postfix());return R("Tuple",e,void 0,{elts:t})}return e}funcdef(){const e=this.cur;this.expect("def");const t=this.expectKind("NAME").value;this.expect("(");const o=[];for(;!this.peekIs(")");){const p=this.expectKind("NAME");let g;if(this.accept(":")&&(g=this.annotation()),o.push(R("Arg",p,{name:p.value},g?{annotation:g}:void 0)),!this.accept(","))break}this.expect(")");let d;this.accept("->")&&(d=this.annotation());const i=this.block(),c={args:o,body:i};return d&&(c.returns=d),R("FunctionDef",e,{name:t},c)}annotation(){const e=this.cur,t=this.cur.kind==="NAME"||this.cur.kind==="KEYWORD"?this.toks[this.p++].value:(()=>{throw new Q("bad annotation",e.line,e.col)})();if(this.accept("[")){const o=[this.annotation()];for(;this.accept(",");)o.push(this.annotation());return this.expect("]"),R("TypeRef",e,{name:t},{params:o})}return R("TypeRef",e,{name:t})}ifstmt(){const e=this.cur;this.p++;const t=this.expr(),o=this.block();let d=[];return this.peekIs("elif")?d=[this.ifstmt()]:this.peekIs("else")&&(this.p++,d=this.block()),R("If",e,void 0,{test:t,body:o,orelse:d})}simple(){const e=this.cur;let t;if(this.accept("return"))t=R("Return",e,void 0,this.cur.kind==="NEWLINE"?void 0:{value:this.exprList()});else if(this.accept("pass"))t=R("Pass",e);else if(this.accept("break"))t=R("Break",e);else if(this.accept("continue"))t=R("Continue",e);else{const o=this.exprList();if(this.accept(":")){const d=this.annotation(),i=this.accept("=")?this.expr():void 0;t=R("AnnAssign",e,void 0,{target:o,annotation:d,...i?{value:i}:{}})}else if(this.cur.kind==="OP"&&/^(\*\*|\/\/|<<|>>|[+\-*/%&|])=$/.test(this.cur.value)){const d=this.toks[this.p++].value.slice(0,-1);t=R("AugAssign",e,{op:d},{target:o,value:this.expr()})}else if(this.accept("=")){let d=this.exprList();const i=[o];for(;this.accept("=");)i.push(d),d=this.exprList();t=R("Assign",e,void 0,{targets:i,value:d})}else t=R("Expr",e,void 0,{value:o})}if(this.cur.kind==="NEWLINE")this.p++;else if(this.cur.kind!=="DEDENT"&&this.cur.kind!=="ENDMARKER")throw new Q(`unexpected '${this.cur.value}'`,this.cur.line,this.cur.col);return t}exprList(){const e=this.expr();if(this.peekIs(",")){const t=[e];for(;this.accept(",")&&!(this.cur.kind==="NEWLINE"||this.peekIs(")")||this.peekIs("="));)t.push(this.expr());return R("Tuple",e,void 0,{elts:t})}return e}expr(){const e=this.orExpr();if(this.peekIs("if")){this.p++;const t=this.orExpr();this.expect("else");const o=this.expr();return R("IfExp",e,void 0,{test:t,body:e,orelse:o})}return e}orExpr(){let e=this.andExpr();for(;this.peekIs("or");){const t=this.toks[this.p++];e=R("BoolOp",t,{op:"or"},{values:[e,this.andExpr()]})}return e}andExpr(){let e=this.notExpr();for(;this.peekIs("and");){const t=this.toks[this.p++];e=R("BoolOp",t,{op:"and"},{values:[e,this.notExpr()]})}return e}notExpr(){if(this.peekIs("not")){const e=this.toks[this.p++];return R("UnaryOp",e,{op:"not"},{operand:this.notExpr()})}return this.compare()}compare(){var d;const e=this.bin(0),t=[],o=[];for(;;){const i=this.cur;let c=null;if(i.kind==="OP"&&["<",">","<=",">=","==","!="].includes(i.value)?(c=i.value,this.p++):i.kind==="KEYWORD"&&i.value==="in"?(c="in",this.p++):i.kind==="KEYWORD"&&i.value==="not"&&((d=this.toks[this.p+1])==null?void 0:d.value)==="in"?(c="not in",this.p+=2):i.kind==="KEYWORD"&&i.value==="is"&&(this.p++,c=this.accept("not")?"is not":"is"),!c)break;t.push(c),o.push(this.bin(0))}return t.length?R("Compare",e,{ops:t},{left:e,comparators:o}):e}bin(e){const t=[["|"],["^"],["&"],["<<",">>"],["+","-"],["*","/","//","%"]];if(e>=t.length)return this.unary();let o=this.bin(e+1);for(;this.cur.kind==="OP"&&t[e].includes(this.cur.value);){const d=this.toks[this.p++];o=R("BinOp",d,{op:d.value},{left:o,right:this.bin(e+1)})}return o}unary(){if(this.cur.kind==="OP"&&["-","+","~"].includes(this.cur.value)){const e=this.toks[this.p++];return R("UnaryOp",e,{op:e.value},{operand:this.unary()})}return this.power()}power(){const e=this.postfix();if(this.peekIs("**")){const t=this.toks[this.p++];return R("BinOp",t,{op:"**"},{left:e,right:this.unary()})}return e}postfix(){let e=this.atom();for(;;)if(this.peekIs("(")){const t=this.toks[this.p++],o=[];for(;!this.peekIs(")")&&(o.push(this.expr()),!!this.accept(",")););this.expect(")"),e=R("Call",t,void 0,{func:e,args:o})}else if(this.peekIs("[")){const t=this.toks[this.p++];let o=this.expr();if(this.peekIs(":")){this.p++;const d=this.peekIs("]")?void 0:this.expr();o=R("Slice",t,void 0,{lower:o,...d?{upper:d}:{}})}this.expect("]"),e=R("Subscript",t,void 0,{value:e,index:o})}else if(this.peekIs(".")){const t=this.toks[this.p++],o=this.expectKind("NAME").value;e=R("Attribute",t,{attr:o},{value:e})}else break;return e}atom(){const e=this.cur;if(e.kind==="NUMBER")return this.p++,R("Constant",e,{value:e.value,kind:/[.eE]/.test(e.value)&&!/^0[xX]/.test(e.value)?"float":"int"});if(e.kind==="STRING")return this.p++,R("Constant",e,{value:e.value,kind:"str"});if(e.kind==="KEYWORD"&&(e.value==="True"||e.value==="False"))return this.p++,R("Constant",e,{value:e.value,kind:"bool"});if(e.kind==="KEYWORD"&&e.value==="None")return this.p++,R("Constant",e,{value:"None",kind:"None"});if(e.kind==="NAME")return this.p++,R("Name",e,{id:e.value});if(this.accept("(")){if(this.accept(")"))return R("Tuple",e,void 0,{elts:[]});const t=this.expr();if(this.peekIs(",")){const o=[t];for(;this.accept(",")&&!this.peekIs(")");)o.push(this.expr());return this.expect(")"),R("Tuple",e,void 0,{elts:o})}return this.expect(")"),t}if(this.accept("[")){if(this.accept("]"))return R("List",e,void 0,{elts:[]});const t=this.expr();if(this.peekIs("for")){this.p++;const d=this.targetList();this.expect("in");const i=this.orExpr();let c;return this.accept("if")&&(c=this.orExpr()),this.expect("]"),R("ListComp",e,void 0,{elt:t,target:d,iter:i,...c?{cond:c}:{}})}const o=[t];for(;this.accept(",")&&!this.peekIs("]");)o.push(this.expr());return this.expect("]"),R("List",e,void 0,{elts:o})}if(this.accept("{")){const t=[],o=[];for(;!this.peekIs("}")&&(t.push(this.expr()),this.expect(":"),o.push(this.expr()),!!this.accept(",")););return this.expect("}"),R("Dict",e,void 0,{keys:t,values:o})}throw e.kind==="KEYWORD"&&e.value==="lambda"?new Q("lambda is not part of PySub",e.line,e.col):new Q(`unexpected '${e.value||e.kind.toLowerCase()}'`,e.line,e.col)}}function ge(r){const e=Qe(r);try{return{ast:new et(e).module(),diagnostics:[],tokens:e}}catch(t){if(t instanceof Q)return{ast:null,diagnostics:[{line:t.line,col:t.col,kind:"SyntaxError",msg:t.message}],tokens:e};throw t}}const N=(r,e)=>{var o;const t=(o=r.kids)==null?void 0:o[e];return t?Array.isArray(t)?t:[t]:[]},f=(r,e)=>{var o;const t=(o=r.kids)==null?void 0:o[e];return t&&!Array.isArray(t)?t:void 0},ce=r=>{var i;if(!r)return null;const e=String((i=r.attrs)==null?void 0:i.name),t=N(r,"params"),d={List:"list",Dict:"dict"}[e]??e;return t.length?`${d}[${t.map(ce).join(", ")}]`:d},fe=r=>{const e=/^list\[(.+)\]$/.exec(r??"");return e?e[1]:null},ze=r=>{const e=/^dict\[[^,]+,\s*(.+)\]$/.exec(r??"");return e?e[1]:null},Ee={len:"int",int:"int",float:"float",str:"str",abs:"int",ord:"int",chr:"str",sqrt:"float",bool:"bool",range:"range",sum:"int",min:"int",max:"int",round:"int",print:"None",floor:"int",exp:"float",log:"float",sin:"float",cos:"float"},qe=r=>JSON.parse(JSON.stringify(r));function be(r,e={}){var k,m,w,u;const t=qe(r),o=[],d={...e},i=(l,a,s)=>o.push({line:l.line,col:l.col,kind:a,msg:s});for(const l of N(t,"body"))l.t==="FunctionDef"&&(d[String((k=l.attrs)==null?void 0:k.name)]={params:N(l,"args").map(a=>ce(f(a,"annotation"))??"?"),ret:ce(f(l,"returns"))??"None"});const c={v:"None"},p=(l,a)=>{var D,A,x,_,h,S,$,v,O;let s=null;switch(l.t){case"Constant":{s=String((D=l.attrs)==null?void 0:D.kind);break}case"Name":{const E=String((A=l.attrs)==null?void 0:A.id);s=a[E]??null,!s&&!(E in d)&&!(E in Ee)&&i(l,"NameError",`name '${E}' is not defined`);break}case"BinOp":{const E=p(f(l,"left"),a),y=p(f(l,"right"),a),b=String((x=l.attrs)==null?void 0:x.op);E==="str"&&y==="str"&&b==="+"||E==="str"&&y==="int"&&b==="*"?s="str":E!=null&&E.startsWith("list")&&b==="+"?s=E:E==="str"||y==="str"?(i(l,"TypeError",`unsupported operand types for ${b}: '${E}' and '${y}'`),s=E):b==="/"||E==="float"||y==="float"?s="float":s=E==="bool"?"int":E??y;break}case"UnaryOp":{const E=p(f(l,"operand"),a);s=((_=l.attrs)==null?void 0:_.op)==="not"?"bool":E;break}case"BoolOp":{N(l,"values").forEach(E=>p(E,a)),s="bool";break}case"Compare":{p(f(l,"left"),a),N(l,"comparators").forEach(E=>p(E,a)),s="bool";break}case"IfExp":{p(f(l,"test"),a);const E=p(f(l,"body"),a),y=p(f(l,"orelse"),a);s=E==="int"&&y==="float"?"float":E;break}case"Call":{const E=f(l,"func"),y=N(l,"args").map(b=>p(b,a));if(E.t==="Name"){const b=String((h=E.attrs)==null?void 0:h.id);E.ty=null,b in d?s=d[b].ret:b in Ee?(s=Ee[b],["abs","min","max","sum"].includes(b)&&(s=y[0]==="float"?"float":fe(y[0])??y[0]??"int")):i(E,"NameError",`call to unknown function '${b}'`)}else if(E.t==="Attribute"){const b=p(f(E,"value"),a),j=String((S=E.attrs)==null?void 0:S.attr);b&&(b.startsWith("list")||b.startsWith("dict")||b==="str")?s=j==="append"||j==="sort"||j==="reverse"?"None":j==="pop"?fe(b)??"int":j==="get"?ze(b)??"int":j==="join"||j==="lower"||j==="upper"||j==="strip"?"str":j==="split"?"list[str]":j==="count"||j==="find"||j==="index"?"int":null:i(l,"TypeError",`calls on module or object '${((v=($=f(E,"value"))==null?void 0:$.attrs)==null?void 0:v.id)??"?"}' are outside PySub`)}break}case"Subscript":{const E=p(f(l,"value"),a),y=f(l,"index");if(y.t==="Slice"){N(y,"lower").forEach(j=>p(j,a));const b=f(y,"upper");b&&p(b,a),s=E}else p(y,a),s=E==="str"?"str":E!=null&&E.startsWith("dict")?ze(E):fe(E);break}case"Attribute":{p(f(l,"value"),a),i(l,"TypeError","attribute access is not part of PySub");break}case"List":{const E=N(l,"elts").map(y=>p(y,a));s=E.length?`list[${E[0]}]`:"list[int]";break}case"Tuple":{N(l,"elts").forEach(E=>p(E,a)),s="tuple";break}case"Dict":{const E=N(l,"keys").map(b=>p(b,a)),y=N(l,"values").map(b=>p(b,a));s=E.length?`dict[${E[0]}, ${y[0]}]`:"dict[str, int]";break}case"ListComp":{i(l,"UnsupportedConstruct","list comprehension is not part of PySub; rewrite with an explicit loop and .append");const E={...a},y=p(f(l,"iter"),a),b=f(l,"target");b.t==="Name"&&(E[String((O=b.attrs)==null?void 0:O.id)]=y==="range"?"int":fe(y)??"int"),s=`list[${p(f(l,"elt"),E)}]`;break}}return l.ty=s,s},g=(l,a)=>{var s,D,A;for(const x of l)switch(x.t){case"Assign":{const _=p(f(x,"value"),a);for(const h of N(x,"targets"))if(h.t==="Name"){const S=String((s=h.attrs)==null?void 0:s.id);a[S]&&_&&a[S]!==_&&!(a[S]==="float"&&_==="int")?i(h,"TypeError",`variable '${S}' changes type from ${a[S]} to ${_}`):!a[S]&&_&&(a[S]=_),h.ty=a[S]??_}else h.t==="Tuple"?N(h,"elts").forEach(S=>{var $,v,O;S.t==="Name"&&(a[String(($=S.attrs)==null?void 0:$.id)]=a[String((v=S.attrs)==null?void 0:v.id)]??"int",S.ty=a[String((O=S.attrs)==null?void 0:O.id)])}):p(h,a);break}case"AnnAssign":{const _=f(x,"target"),h=ce(f(x,"annotation"));_.t==="Name"&&h&&(a[String((D=_.attrs)==null?void 0:D.id)]=h,_.ty=h);const S=f(x,"value");S&&p(S,a);break}case"AugAssign":{const _=f(x,"target"),h=p(_,a),S=p(f(x,"value"),a);h==="int"&&S==="float"&&i(x,"TypeError","variable changes type from int to float in augmented assignment");break}case"Return":{const _=f(x,"value"),h=_?p(_,{...a}):"None";h&&c.v!==h&&!(c.v==="float"&&h==="int")&&c.v!=="?"&&i(x,"TypeError",`return type ${h} does not match declared ${c.v}`);break}case"Expr":p(f(x,"value"),a);break;case"If":p(f(x,"test"),a),g(N(x,"body"),a),g(N(x,"orelse"),a);break;case"While":p(f(x,"test"),a),g(N(x,"body"),a);break;case"For":{const _=p(f(x,"iter"),a),h=f(x,"target"),S=_==="range"?"int":_==="str"?"str":fe(_)??"int";h.t==="Name"?(a[String((A=h.attrs)==null?void 0:A.id)]=S,h.ty=S):h.t==="Tuple"&&N(h,"elts").forEach($=>{var v;$.t==="Name"&&(a[String((v=$.attrs)==null?void 0:v.id)]="int",$.ty="int")}),g(N(x,"body"),a);break}}};for(const l of N(t,"body")){if(l.t!=="FunctionDef")continue;const a={};for(const D of N(l,"args")){const A=ce(f(D,"annotation"));A||i(D,"TypeError",`missing annotation for parameter '${(m=D.attrs)==null?void 0:m.name}' (fixable: observed types can supply it)`),a[String((w=D.attrs)==null?void 0:w.name)]=A??"int",D.ty=A}const s=ce(f(l,"returns"));s||i(l,"TypeError",`missing return annotation for '${(u=l.attrs)==null?void 0:u.name}' (fixable)`),c.v=s??"?",l.ty=s,g(N(l,"body"),a)}const P=N(t,"body").filter(l=>l.t!=="FunctionDef");return c.v="?",g(P,{}),{ast:t,diagnostics:o,sigs:d}}function Ce(r,e=!1){const t=qe(r);let o=0,d=0;const i=new Set,c=(p,g)=>{var P,k,m,w,u;if(p.t==="For"){const l=f(p,"target");(l==null?void 0:l.t)==="Name"&&((P=f(p,"iter"))==null?void 0:P.t)==="Call"&&i.add(String((k=l.attrs)==null?void 0:k.id))}if(p.t==="BinOp"||p.t==="AugAssign"){const l=String((m=p.attrs)==null?void 0:m.op),a=f(p,p.t==="BinOp"?"left":"target"),s=f(p,p.t==="BinOp"?"right":"value");if(["+","-","*"].includes(l)&&p.ty!=="float"&&(a==null?void 0:a.ty)!=="float"&&(s==null?void 0:s.ty)!=="float"&&p.ty!=="str"&&!(p.ty??"").startsWith("list")){const D=x=>{var _,h;return x&&(x.t==="Constant"&&Number((_=x.attrs)==null?void 0:_.value)<1e6||x.t==="Name"&&i.has(String((h=x.attrs)==null?void 0:h.id)))},A=!!(e||D(a)&&D(s)||(D(a)||D(s))&&l!=="*"||l==="*"&&(D(a)||D(s))&&p.t==="BinOp"&&Number(D(a)?(w=a==null?void 0:a.attrs)==null?void 0:w.value:(u=s==null?void 0:s.attrs)==null?void 0:u.value)<1e6);p.attrs={...p.attrs,no_guard:A},A?o++:d++}if(p.t==="BinOp"&&(a==null?void 0:a.ty)==="int"!=((s==null?void 0:s.ty)==="int")&&((a==null?void 0:a.ty)==="float"||(s==null?void 0:s.ty)==="float")){const D=(a==null?void 0:a.ty)==="int"?"left":"right",A=f(p,D);p.kids[D]={t:"Coerce",line:A.line,col:A.col,ty:"float",attrs:{from:"int",to:"float"},kids:{value:A}}}}for(const l of Object.values(p.kids??{}))(Array.isArray(l)?l:[l]).forEach(a=>c(a,g||p.t==="For"||p.t==="While"))};return c(t,!1),{pir:t,elided:o,kept:d}}const V=r=>{if(!r)return"auto";if(r==="int")return"int64_t";if(r==="float")return"double";if(r==="bool")return"bool";if(r==="str")return"PyStr";if(r==="None")return"void";const e=/^list\[(.+)\]$/.exec(r);if(e)return`PyList<${V(e[1])}>`;const t=/^dict\[(.+?),\s*(.+)\]$/.exec(r);return t?`PyDict<${V(t[1])}, ${V(t[2])}>`:"auto"};function Oe(r,e=!0){var k;const t=[],o={},d=m=>{(o[m]||(o[m]=[])).push(t.length)};e&&t.push('#include "pyrt.hpp"',"using namespace pyrt;","","namespace pythia_mod {","");const i=m=>{var w,u,l,a,s,D,A,x,_,h,S;switch(m.t){case"Constant":{const $=(w=m.attrs)==null?void 0:w.kind,v=String((u=m.attrs)==null?void 0:u.value);return $==="str"?`PyStr(${v.replace(/^'|'$/g,'"')})`:$==="bool"?v==="True"?"true":"false":$==="None"?"nullptr":v}case"Name":return String((l=m.attrs)==null?void 0:l.id);case"Coerce":return`static_cast<double>(${i(f(m,"value"))})`;case"BinOp":{const $=String((a=m.attrs)==null?void 0:a.op),v=i(f(m,"left")),O=i(f(m,"right")),E=m.ty==="int";return m.ty==="str"||(m.ty??"").startsWith("list")?$==="+"?`py_concat(${v}, ${O})`:`py_repeat(${v}, ${O})`:$==="//"?`py_floordiv(${v}, ${O})`:$==="%"?`py_mod(${v}, ${O})`:$==="/"?`py_truediv(${v}, ${O})`:$==="**"?`py_pow(${v}, ${O})`:E&&["+","-","*"].includes($)&&!((s=m.attrs)!=null&&s.no_guard)?`${{"+":"py_add","-":"py_sub","*":"py_mul"}[$]}(${v}, ${O})`:`(${v} ${$} ${O})`}case"UnaryOp":return((D=m.attrs)==null?void 0:D.op)==="not"?`!${i(f(m,"operand"))}`:`${(A=m.attrs)==null?void 0:A.op}${i(f(m,"operand"))}`;case"BoolOp":return`(${N(m,"values").map(i).join(((x=m.attrs)==null?void 0:x.op)==="and"?" && ":" || ")})`;case"Compare":{let $=i(f(m,"left"));const v=[],O=(_=m.attrs)==null?void 0:_.ops;return N(m,"comparators").forEach((E,y)=>{const b=i(E),j=O[y];j==="in"?v.push(`py_contains(${b}, ${$})`):j==="not in"?v.push(`!py_contains(${b}, ${$})`):v.push(`(${$} ${j==="is"?"==":j==="is not"?"!=":j} ${b})`),$=b}),v.join(" && ")}case"IfExp":return`(${i(f(m,"test"))} ? ${i(f(m,"body"))} : ${i(f(m,"orelse"))})`;case"Call":{const $=f(m,"func"),v=N(m,"args").map(i);if($.t==="Name"){const O=String((h=$.attrs)==null?void 0:h.id);return O==="len"?`py_len(${v[0]})`:O==="print"?`py_print(${v.join(", ")})`:`${O}(${v.join(", ")})`}return $.t==="Attribute"?`${i(f($,"value"))}.${(S=$.attrs)==null?void 0:S.attr}(${v.join(", ")})`:"/*call*/"}case"Subscript":{const $=f(m,"index");return $.t==="Slice"?`py_slice(${i(f(m,"value"))}, ${i(f($,"lower"))}${f($,"upper")?", "+i(f($,"upper")):""})`:`${i(f(m,"value"))}.at(${i($)})`}case"List":return`${V(m.ty)}{${N(m,"elts").map(i).join(", ")}}`;case"Tuple":return`std::make_tuple(${N(m,"elts").map(i).join(", ")})`;case"Dict":return`${V(m.ty)}{${N(m,"keys").map(($,v)=>`{${i($)}, ${i(N(m,"values")[v])}}`).join(", ")}}`;default:return`/*${m.t}*/`}},c=[],p=(m,w)=>{var u,l,a,s,D,A,x;for(const _ of m)switch(d(_.line),_.t){case"Return":{const h=f(_,"value");t.push(`${w}return${h?" "+i(h):""};`);break}case"Pass":t.push(`${w}/* pass */`);break;case"Break":t.push(`${w}break;`);break;case"Continue":t.push(`${w}continue;`);break;case"Expr":t.push(`${w}${i(f(_,"value"))};`);break;case"Assign":{const h=N(_,"targets")[0],S=i(f(_,"value")),$=c[c.length-1];if(h.t==="Name"){const v=String((u=h.attrs)==null?void 0:u.id);$.has(v)?t.push(`${w}${v} = ${S};`):($.add(v),t.push(`${w}${V(h.ty)} ${v} = ${S};`))}else if(h.t==="Subscript")t.push(`${w}${i(f(h,"value"))}.set(${i(f(h,"index"))}, ${S});`);else if(h.t==="Tuple"){const v=N(h,"elts").map(i);t.push(`${w}std::tie(${v.join(", ")}) = std::make_tuple(${i(f(_,"value")).replace(/^std::make_tuple\(|\)$/g,"")});`)}else t.push(`${w}/* unsupported target */`);break}case"AnnAssign":{const h=f(_,"target"),S=f(_,"value");c[c.length-1].add(String((l=h.attrs)==null?void 0:l.id)),t.push(`${w}${V(h.ty)} ${i(h)}${S?" = "+i(S):""};`);break}case"AugAssign":{const h=f(_,"target"),S=String((a=_.attrs)==null?void 0:a.op),$=i(f(_,"value"));h.ty==="int"&&["+","-","*"].includes(S)&&!((s=_.attrs)!=null&&s.no_guard)?t.push(`${w}${i(h)} = ${{"+":"py_add","-":"py_sub","*":"py_mul"}[S]}(${i(h)}, ${$});`):S==="//"||S==="%"?t.push(`${w}${i(h)} = ${S==="//"?"py_floordiv":"py_mod"}(${i(h)}, ${$});`):t.push(`${w}${i(h)} ${S}= ${$};`);break}case"If":{t.push(`${w}if (${i(f(_,"test"))}) {`),p(N(_,"body"),w+"    ");let h=N(_,"orelse");for(;h.length===1&&h[0].t==="If";)t.push(`${w}} else if (${i(f(h[0],"test"))}) {`),d(h[0].line),p(N(h[0],"body"),w+"    "),h=N(h[0],"orelse");h.length&&(t.push(`${w}} else {`),p(h,w+"    ")),t.push(`${w}}`);break}case"While":t.push(`${w}while (${i(f(_,"test"))}) {`),p(N(_,"body"),w+"    "),t.push(`${w}}`);break;case"For":{const h=f(_,"target"),S=f(_,"iter"),$=h.t==="Name"?String((D=h.attrs)==null?void 0:D.id):"_it";if(c[c.length-1].add($),S.t==="Call"&&((x=(A=f(S,"func"))==null?void 0:A.attrs)==null?void 0:x.id)==="range"){const v=N(S,"args").map(i),[O,E,y]=v.length===1?["0",v[0],"1"]:[v[0],v[1],v[2]??"1"];t.push(`${w}for (int64_t ${$} = ${O}; ${$} < ${E}; ${$} += ${y}) {`)}else t.push(`${w}for (auto ${$} : ${i(S)}) {`);p(N(_,"body"),w+"    "),t.push(`${w}}`);break}default:t.push(`${w}/* ${_.t} */`)}};for(const m of N(r,"body")){if(m.t!=="FunctionDef")continue;const w=N(m,"args").map(u=>{var l;return`${V(u.ty)}${/^(PyStr|PyList|PyDict)/.test(V(u.ty))?" const&":""} ${(l=u.attrs)==null?void 0:l.name}`});d(m.line),t.push(`${V(m.ty)} ${(k=m.attrs)==null?void 0:k.name}(${w.join(", ")}) {`),c.push(new Set(N(m,"args").map(u=>{var l;return String((l=u.attrs)==null?void 0:l.name)}))),p(N(m,"body"),"    "),c.pop(),t.push("}","")}const g=N(r,"body").filter(m=>m.t!=="FunctionDef");g.length&&(t.push("int main() {"),c.push(new Set),p(g,"    "),c.pop(),t.push("    return 0;","}","")),e&&t.push("}  // namespace pythia_mod");const P={};for(const[m,w]of Object.entries(o))P[m]=w.map(u=>u+1);return{cpp:t.join(`
`),line_map:P}}function tt(r,e){var d,i;const t=N(e,"body").filter(c=>c.t==="FunctionDef"),o=["#include <pybind11/pybind11.h>","#include <pybind11/stl.h>",'#include "pyrt.hpp"','#include "'+r+'_fns.hpp"',"","namespace py = pybind11;","static PyObject* g_fallback = nullptr;","",`PYBIND11_MODULE(${r}, m) {`,'    g_fallback = py::exception<std::runtime_error>(m, "FallbackError").ptr();'];for(const c of t){const p=N(c,"args"),g=p.map(P=>{var k;return`${V(P.ty)} ${(k=P.attrs)==null?void 0:k.name}`}).join(", ");o.push(`    m.def("${(d=c.attrs)==null?void 0:d.name}", [](${g}) {`,"        pyrt::arena_begin();",`        auto r = pythia_mod::${(i=c.attrs)==null?void 0:i.name}(${p.map(P=>{var k;return(k=P.attrs)==null?void 0:k.name}).join(", ")});`,"        pyrt::arena_end();","        return r;","    });")}return o.push("}"),o.join(`
`)}function Te(r){const e=[],t=new Set,o=(i,c,p,g,P)=>{const k=`${i.line}:${c}`;t.has(k)||(t.add(k),e.push({line:i.line,col:i.col,cls:c,detail:p,mitigation:g,severity:P}))},d=(i,c)=>{var p,g,P,k,m,w,u,l;(i.t==="BinOp"||i.t==="AugAssign")&&["+","-","*"].includes(String((p=i.attrs)==null?void 0:p.op))&&i.ty==="int"&&((g=i.attrs)==null?void 0:g.no_guard)===!1&&o(i,"D1 unbounded-int vs int64","Python integers are arbitrary precision; the compiled code uses int64_t. A result outside +/-2^63 cannot be represented.","Arithmetic is overflow-checked: the call raises OverflowError instead of wrapping, and replay would flag any mismatch.","guarded"),i.t==="BinOp"&&(((P=i.attrs)==null?void 0:P.op)==="//"||((k=i.attrs)==null?void 0:k.op)==="%")&&o(i,"D3 floor division and modulo sign","C++ truncates toward zero; Python floors. Results differ for negative operands.","The runtime provides py_floordiv/py_mod which reproduce Python semantics exactly, including ZeroDivisionError.","exact"),i.t==="BinOp"&&((m=i.attrs)==null?void 0:m.op)==="/"&&o(i,"D4 true division","int / int yields float in Python; ZeroDivisionError message text differs between interpreters.","Division goes through py_truediv; the exception class is identical and the message is normalised.","exact"),i.t==="Subscript"&&i.ty!==null&&((w=f(i,"index"))==null?void 0:w.t)!=="Slice"&&o(i,"E2 indexing and bounds","Negative indexes and out-of-range access must behave like CPython.","Container access is bounds-checked and wraps negative indexes; IndexError is raised with the same class.","exact"),i.ty==="str"&&(i.t==="Subscript"||i.t==="BinOp")&&o(i,"D5 ASCII-only strings","Compiled strings are byte strings. Non-ASCII text would index differently from Python code points.","The wrapper raises FallbackError for non-ASCII input so the original Python runs instead.","guarded"),i.t==="BinOp"&&i.ty==="float"&&o(i,"D2 float evaluation order","IEEE-754 doubles are used; evaluation order matches the source.","Compiled with -O3 but without -ffast-math, so floating-point results are bitwise identical.","exact"),(i.t==="List"||i.t==="Call"&&((l=(u=f(i,"func"))==null?void 0:u.attrs)==null?void 0:l.attr)==="append")&&c>0&&o(i,"D7 memory is not reclaimed","The runtime does not free list/str allocations made inside the call.","An arena frees everything allocated during one call once the result has been copied back to Python.","divergent");for(const a of Object.values(i.kids??{}))(Array.isArray(a)?a:[a]).forEach(s=>d(s,c+(i.t==="For"||i.t==="While"?1:0)))};return d(r,0),e.sort((i,c)=>i.line-c.line)}function st(r,e="<input>"){const{ast:t,diagnostics:o,tokens:d}=ge(r);if(!t)return{ok:!1,diagnostics:o,tokens:d,ast:null,typed_ast:null,pir:null,cpp:"",fidelity:[]};const i=be(t);if(i.diagnostics.length)return{ok:!1,diagnostics:i.diagnostics,tokens:d,ast:t,typed_ast:i.ast,pir:null,cpp:"",fidelity:[]};const{pir:c,elided:p,kept:g}=Ce(i.ast),{cpp:P}=Oe(c),k=Te(c);return{ok:!0,diagnostics:[],tokens:d,ast:t,typed_ast:i.ast,pir:c,cpp:P,fidelity:k,guard_elision:{elided:p,kept:g}}}function Be(r){const{ast:e,diagnostics:t}=ge(r);if(!e)return{ok:!1,cpp:"",diagnostics:t,fidelity:[],cpp_line_map:{}};const o=be(e);if(o.diagnostics.length)return{ok:!1,cpp:"",diagnostics:o.diagnostics,fidelity:[],cpp_line_map:{}};const{pir:d}=Ce(o.ast),{cpp:i,line_map:c}=Oe(d);return{ok:!0,cpp:i,diagnostics:[],fidelity:Te(d),cpp_line_map:c}}class We{constructor(e){this.v=e}}class je{}class Pe{}const Ie=r=>r===null?"None":typeof r=="boolean"?r?"True":"False":typeof r=="string"?r:typeof r=="number"?Number.isInteger(r)?String(r):String(parseFloat(r.toPrecision(15))):Array.isArray(r)?"["+r.map(Ne).join(", ")+"]":"{"+[...r.entries()].map(([e,t])=>`${Ne(e)}: ${Ne(t)}`).join(", ")+"}",Ne=r=>typeof r=="string"?`'${r}'`:Ie(r);function it(r,e=4e6){var l;const{ast:t}=ge(r);if(!t)return{stdout:"",exception:"SyntaxError",steps:0};const d=be(t).ast,i={};for(const a of N(d,"body"))a.t==="FunctionDef"&&(i[String((l=a.attrs)==null?void 0:l.name)]=a);let c="",p=0;const g=()=>{if(++p>e)throw new Error("TimeoutError")},P=(a,s)=>{if(s===0)throw new Error("ZeroDivisionError");return Math.floor(a/s)},k=(a,s)=>{var D,A,x,_,h,S,$,v,O,E;switch(g(),a.t){case"Constant":{const y=(D=a.attrs)==null?void 0:D.kind,b=String((A=a.attrs)==null?void 0:A.value);return y==="str"?b.slice(1,-1):y==="bool"?b==="True":y==="None"?null:Number(b.replace(/_/g,""))}case"Name":{const y=String((x=a.attrs)==null?void 0:x.id);if(!s.has(y))throw new Error("NameError");return s.get(y)}case"UnaryOp":{const y=k(f(a,"operand"),s);return((_=a.attrs)==null?void 0:_.op)==="not"?!y:((h=a.attrs)==null?void 0:h.op)==="-"?-y:y}case"BoolOp":{const y=N(a,"values");let b=k(y[0],s);for(let j=1;j<y.length;j++){if(((S=a.attrs)==null?void 0:S.op)==="and"?!b:b)return b;b=k(y[j],s)}return b}case"IfExp":return k(f(a,"test"),s)?k(f(a,"body"),s):k(f(a,"orelse"),s);case"BinOp":{const y=k(f(a,"left"),s),b=k(f(a,"right"),s),j=String(($=a.attrs)==null?void 0:$.op);if(typeof y=="string"&&typeof b=="string")return y+b;if(typeof y=="string"&&typeof b=="number")return y.repeat(b);if(Array.isArray(y)&&Array.isArray(b))return[...y,...b];const L=Number(y),T=Number(b);switch(j){case"+":return L+T;case"-":return L-T;case"*":return L*T;case"/":if(T===0)throw new Error("ZeroDivisionError");return L/T;case"//":return P(L,T);case"%":if(T===0)throw new Error("ZeroDivisionError");return(L%T+T)%T;case"**":return Math.pow(L,T);case"&":return L&T;case"|":return L|T;case"^":return L^T;case"<<":return L<<T;case">>":return L>>T}return 0}case"Compare":{let y=k(f(a,"left"),s);const b=(v=a.attrs)==null?void 0:v.ops;for(let j=0;j<b.length;j++){const L=k(N(a,"comparators")[j],s),T=b[j];if(!(T==="<"?y<L:T===">"?y>L:T==="<="?y<=L:T===">="?y>=L:T==="=="||T==="is"?y===L:T==="!="||T==="is not"?y!==L:T==="in"?Array.isArray(L)?L.includes(y):String(L).includes(String(y)):!(Array.isArray(L)?L.includes(y):String(L).includes(String(y)))))return!1;y=L}return!0}case"List":return N(a,"elts").map(y=>k(y,s));case"Tuple":return N(a,"elts").map(y=>k(y,s));case"Dict":{const y=new Map;return N(a,"keys").forEach((b,j)=>y.set(k(b,s),k(N(a,"values")[j],s))),y}case"Subscript":{const y=k(f(a,"value"),s),b=f(a,"index");if(b.t==="Slice"){const C=Number(k(f(b,"lower"),s)),q=f(b,"upper"),Y=q?Number(k(q,s)):void 0;return y.slice(C,Y)}const j=k(b,s);if(y instanceof Map){if(!y.has(j))throw new Error("KeyError");return y.get(j)}const L=y,T=j<0?L.length+j:j;if(T<0||T>=L.length)throw new Error("IndexError");return L[T]}case"Call":{const y=f(a,"func"),b=N(a,"args").map(C=>k(C,s));if(y.t==="Attribute"){const C=k(f(y,"value"),s),q=String((O=y.attrs)==null?void 0:O.attr);if(Array.isArray(C)&&q==="append")return C.push(b[0]),null;if(Array.isArray(C)&&q==="pop")return C.pop()??null;if(typeof C=="string"&&q==="upper")return C.toUpperCase();if(typeof C=="string"&&q==="lower")return C.toLowerCase();throw new Error("AttributeError")}const j=String((E=y.attrs)==null?void 0:E.id);if(j==="print")return c+=b.map(Ie).join(" ")+`
`,null;if(j==="len")return typeof b[0]=="string"?b[0].length:b[0]instanceof Map?b[0].size:b[0].length;if(j==="range"){const[C,q,Y]=b,[G,oe,ie]=b.length===1?[0,C,1]:[C,q,Y??1],n=[];for(let I=G;ie>0?I<oe:I>oe;I+=ie)n.push(I),g();return n}if(j==="int")return Math.trunc(Number(b[0]));if(j==="float")return Number(b[0]);if(j==="str")return Ie(b[0]);if(j==="abs")return Math.abs(b[0]);if(j==="min")return Math.min(...Array.isArray(b[0])?b[0]:b);if(j==="max")return Math.max(...Array.isArray(b[0])?b[0]:b);if(j==="sum")return b[0].reduce((C,q)=>C+q,0);if(j==="ord")return b[0].charCodeAt(0);if(j==="chr")return String.fromCharCode(b[0]);if(j==="sqrt")return Math.sqrt(b[0]);const L=i[j];if(!L)throw new Error("NameError");const T=new Map;N(L,"args").forEach((C,q)=>{var Y;return T.set(String((Y=C.attrs)==null?void 0:Y.name),b[q])});try{w(N(L,"body"),T)}catch(C){if(C instanceof We)return C.v;throw C}return null}default:return null}},m=(a,s,D)=>{var A;if(a.t==="Name")D.set(String((A=a.attrs)==null?void 0:A.id),s);else if(a.t==="Tuple")N(a,"elts").forEach((x,_)=>m(x,s[_],D));else if(a.t==="Subscript"){const x=k(f(a,"value"),D),_=k(f(a,"index"),D);if(x instanceof Map)x.set(_,s);else{const h=x,S=_<0?h.length+_:_;if(S<0||S>=h.length)throw new Error("IndexError");h[S]=s}}},w=(a,s)=>{var D;for(const A of a)switch(g(),A.t){case"Assign":{const x=k(f(A,"value"),s);N(A,"targets").forEach(_=>m(_,x,s));break}case"AnnAssign":{const x=f(A,"value");x&&m(f(A,"target"),k(x,s),s);break}case"AugAssign":{const x=f(A,"target"),_=k(x,s),h=k(f(A,"value"),s),S=String((D=A.attrs)==null?void 0:D.op);let $;if(typeof _=="string")$=_+String(h);else{const v=_,O=h;$=S==="+"?v+O:S==="-"?v-O:S==="*"?v*O:S==="//"?P(v,O):S==="%"?(v%O+O)%O:S==="/"?v/O:v}m(x,$,s);break}case"Return":{const x=f(A,"value");throw new We(x?k(x,s):null)}case"Expr":k(f(A,"value"),s);break;case"Pass":break;case"Break":throw new je;case"Continue":throw new Pe;case"If":w(k(f(A,"test"),s)?N(A,"body"):N(A,"orelse"),s);break;case"While":{try{for(;k(f(A,"test"),s);)try{w(N(A,"body"),s)}catch(x){if(!(x instanceof Pe))throw x}}catch(x){if(!(x instanceof je))throw x}break}case"For":{const x=k(f(A,"iter"),s),_=typeof x=="string"?x.split(""):x instanceof Map?[...x.keys()]:x;try{for(const h of _){m(f(A,"target"),h,s);try{w(N(A,"body"),s)}catch(S){if(!(S instanceof Pe))throw S}}}catch(h){if(!(h instanceof je))throw h}break}}},u=new Map;try{for(const a of N(d,"body"))a.t!=="FunctionDef"&&w([a],u)}catch(a){return{stdout:c,exception:a instanceof Error?a.message:String(a),steps:p}}return{stdout:c,exception:null,steps:p}}const _e=r=>{let e=2166136261;for(let t=0;t<r.length;t++)e^=r.charCodeAt(t),e=Math.imul(e,16777619)>>>0;return e.toString(16).padStart(8,"0")},nt=r=>{let e=parseInt(_e(r),16)>>>0;return()=>{e=e+1831565813>>>0;let t=e;return t=Math.imul(t^t>>>15,t|1),t^=t+Math.imul(t^t>>>7,t|61),((t^t>>>14)>>>0)/4294967296}},xe=r=>Math.round(r*10)/10,re=r=>Math.round(r*100)/100,rt=`try:
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f
`;function at(r){const e=/def\s+(\w+)\(([^)]*)\)\s*(?:->\s*([^:]+))?:/.exec(r);if(!e||/self/.test(e[2]))return null;const t=e[2].split(",").map(o=>o.trim()).filter(Boolean).map(o=>o.includes(":")?o.split(":")[1].trim():"?");return[e[1],{params:t,ret:(e[3]??"None").trim()}]}const ot=r=>{const e=/def\s+\w+\(([^)]*)\)\s*(?:->\s*([^:]+))?:/.exec(r);return{args:e[1].split(",").map(o=>o.trim()).filter(Boolean).map(o=>o.includes(":")?o.split(":")[1].trim():"object"),ret:(e[2]??"None").trim()}};function lt(r,e){const t=r.split(`
`);let o=0,d=0;const i=[];for(const g of t){const P=g.length-g.trimStart().length;for(;i.length&&i[i.length-1]>=P;)i.pop(),o--;/^\s*(for|while)\b/.test(g)&&(i.push(P),o++,d=Math.max(d,o))}const c=(r.match(/[-+*/%]=?|\/\//g)??[]).length,p=[...new Set([...r.matchAll(/\b([A-Za-z_]\w*)\(/g)].map(g=>g[1]).filter(g=>!["def","if","while","for","and","or","not","in"].includes(g)))];return{size_lines:t.length,loop_depth:d,arith_density:re(Math.min(.95,c/Math.max(8,r.length/6))),calls:p.slice(0,8),imports:[],uses_globals:e}}const ct=(r,e,t,o)=>o?`[cache] hit ${r}.so (sha256 ${_e(r)}${_e(e)}…)
[cache] copied to _pythia_accel/lib/${r}.so`:`c++ -std=c++17 -O3 -shared -fPIC -I/usr/include/python3.14 -I.../pybind11/include -o ${r}.cpython-314-x86_64-linux-gnu.so ${r}.cpp pyrt.o
${r}.cpp: In function 'PYBIND11_MODULE':
${r}.cpp:42:5: note: inlined from '${e}' (-O3)
[pyrt] reused cached object pyrt.o
link ${r}.so  ... ok (${t.toFixed(1)}s)`;function pt(){var g,P,k,m,w;const r={};for(const u of Se){const l=at(u.kind==="a"||u.kind==="l"?u.annotated??u.src:u.src);l&&(r[l[0]]=l[1])}const e=new Map;for(const u of Se){const l=e.get(u.file)??[];l.push(u),e.set(u.file,l)}const t=[],o=new Map,d=new Set([...e.keys(),...Object.keys(Ae)]);for(const u of[...d].sort()){const l=Ae[u]??"";let a=l?l.replace(/\n+$/,"")+`


`:"",s=a.split(`
`).length;const D=[],A={};let x=!1;for(const _ of e.get(u)??[]){const h=/def\s+(\w+)\(/.exec(_.src)[1],S=/\(self\b/.test(_.src);let $=_.src,v=h;S&&(x||(a+=`class Body:
    def __init__(self, x, y, z, mass):
        self.x, self.y, self.z, self.mass = x, y, z, mass

`,s+=4,x=!0),v=`Body.${h}`,$="    "+$);const O=$.split(`
`).length,E=`${u}::${v}`;o.set(_,{id:E,name:h,qualname:v,line:s,end_line:s+O-1,text:_.src}),A[E]={line:s,end_line:s+O-1},D.push(E),a+=$+`


`,s+=O+3}t.push({path:u,content:a.replace(/\n+$/,`
`),fns:D,lines:A})}const i=[],c={},p={};for(const u of Se){const l=o.get(u),a=nt(l.id),s=u.kind,D=s==="v"||s==="g"||s==="d"||s==="f",A=s==="a"||s==="l"||s==="lx"||s==="fx",x=D?"verifiable":A?"fixable":"not_eligible",_=u.annotated??null,h=ot(_??u.src),S=s==="v"||s==="g"||s==="a"||s==="l"||s==="d"||s==="f";let $=null,v=[];s==="l"||s==="lx"?(v=(u.attempts??[]).map((z,H)=>({attempt:H+1,source:z.source??"api",pysub:z.pysub,error:z.error,ok:z.error===null})),s==="l"&&($=v[v.length-1].pysub)):s==="a"?$=_:S&&($=u.src);let O=null,E=null,y=null,b={},j=[];const L=`pythia_${_e(l.id+($??""))}`;if($){const{ast:z,tokens:H}=ge($);if(z){const J=be(z,r),se=Ce(J.ast,s==="v"||s==="a"||s==="l"||s==="d"||s==="f"),ue=Oe(se.pir);if(E=ue.cpp,b=ue.line_map,y=tt(L,se.pir),j=Te(se.pir),/\+=|\] = /.test($)&&/: list\[/.test($.split(`
`)[0])&&/-> None/.test($.split(`
`)[0])){const ee=$.split(`
`).findIndex(ve=>/\]\s*\+=/.test(ve))+1;j.push({line:ee||1,col:1,cls:"M1 argument mutation",detail:"The function mutates a list argument in place; the C++ side works on a copy.",mitigation:"The wrapper writes the final list state back into the caller's Python object after the call.",severity:"guarded"})}for(const ee of u.extraNotes??[])j.push({line:ee.line,col:1,cls:ee.cls,detail:ee.detail,mitigation:ee.mitigation,severity:ee.severity});j.sort((ee,ve)=>ee.line-ve.line),O={ok:!0,diagnostics:[],tokens:H,ast:z,typed_ast:J.ast,pir:se.pir,cpp:ue.cpp,fidelity:j,guard_elision:{elided:se.elided,kept:se.kept}},p[l.id]=O}}let T=[];if(s==="n")T=[{line:1,col:1,kind:"UnsupportedConstruct",msg:u.reason,phase:"eligibility"}];else if(A){const{ast:z,diagnostics:H}=ge(u.src);z?T=be(z,r).diagnostics.map(J=>({...J,phase:"eligibility"})):T=H.map(J=>({...J,phase:"eligibility"})),T.length||(T=[{line:1,col:1,kind:"TypeError",msg:u.reason??"not accepted as written",phase:"eligibility"}])}for(const z of v)if(z.error){const H=/line (\d+)/.exec(z.error);T.push({line:H?+H[1]:1,col:1,kind:"TypeError",msg:z.error.replace(/^line \d+:\s*/,""),phase:"fix"})}let C;const q=j.some(z=>z.severity!=="exact");s==="n"||s==="lx"?C="not_eligible":s==="fx"?C="fixable":s==="d"?C="declined":s==="f"?C="failed":C=q?"guarded":"verified";const Y=u.share??null,G=u.calls??null,ie={total:re(Math.min(.98,(Y??0)*3.1+Math.log10((u.speedup??u.probe??1)+1)*.07)*(x==="not_eligible"?.1:D||s==="a"||s==="l"?1:.35)),trace_share:Y,static_heuristic:re(.25+a()*.55),eligibility_factor:x==="verifiable"?1:x==="fixable"?.7:0,expected_benefit:u.speedup?xe(u.speedup*(.4+.2*a())):u.probe?.8:null,boundary_penalty:s==="d"?.91:re((u.elems??1)>1e3?.12+a()*.1:a()*.04),basis:"trace",notes:[Y!=null?`${(Y*100).toFixed(1)}% of traced runtime`:"no trace data",x==="fixable"?"discounted: needs annotation or rewrite":x==="not_eligible"?"not compilable":"compiles as written",...s==="d"?["boundary penalty dominates: marshalling cost exceeds expected saving"]:[]]},n=G==null?null:{calls:G,cum_s:re((Y??0)*14.8),self_s:re((Y??0)*14.8*.93),share:Y??0,arg_types:h.args.map(z=>z==="object"?"str":z),ret_type:h.ret,samples:Math.min(500,G),avg_arg_elems:u.elems??1,avg_ret_elems:s==="v"?1:3},I=S&&s!=="d"&&s!=="f"?u.speedup??null:null,M=Math.min(500,G??500),F=s==="f"?u.mismatch??null:null,U=S&&s!=="d"?{total:M,matched:s==="f"?Math.floor(M*.37):M,exc_matches:s==="v"?Math.floor(a()*4):0,first_mismatch:F}:null,W=xe(18+a()*240),ne=s==="d"?u.probe:I,te=S&&s!=="f"&&ne?{py_ms:W,cpp_ms:re(W/ne),speedup:xe(ne),calls_timed:Math.min(200,M),repeats:5}:null,$e=xe(4.2+a()*4.8),ye=a()<.3,Ye=S?{ok:!0,module:L,so:`_pythia_accel/lib/${L}.cpython-314-x86_64-linux-gnu.so`,cached:ye,compile_s:ye?.1:$e,log:ct(L,l.name,$e,ye)}:null,we=C==="verified"||C==="guarded",Ze=we?`--- a/${l.id.split("::")[0]}
+++ b/${l.id.split("::")[0]}
@@ -${l.line},${l.end_line-l.line+1} +${l.line},${l.end_line-l.line+2} @@
+@_pythia_accelerated("${L}", "${l.name}")
 ${u.src.split(`
`)[0]}
 ${(u.src.split(`
`)[1]??"").trimEnd()}
 …`:null,B=(z,H,J,se,ue=null)=>({key:z,title:H,state:J,summary:se,reason:ue}),De=s==="n"?`Not eligible: ${u.reason}`:s==="fx"?"Skipped: fixable, but below the rewrite threshold":s==="lx"?"No valid PySub produced after 3 attempts":null,de=(z,H,J)=>B(z,H,"skipped",J,De??J),Le=[B("original","Original Python","done",`${u.src.split(`
`).length} lines · ${l.id.split("::")[0]}:${l.line}`),n?B("observed_types","Observed types","done",`(${n.arg_types.join(", ")}) -> ${n.ret_type} · ${n.samples} samples`):B("observed_types","Observed types","skipped","no trace","No trace data was recorded for this function"),D?B("eligibility","Eligibility check","done","Typechecker accepts it as written"):s==="a"?B("eligibility","Eligibility check","failed","Missing annotations",((g=T[0])==null?void 0:g.msg)??null):s==="l"||s==="lx"||s==="fx"?B("eligibility","Eligibility check","failed",`${T.length} issue${T.length===1?"":"s"}`,((P=T[0])==null?void 0:P.msg)??u.reason??null):B("eligibility","Eligibility check","failed","Not eligible",u.reason),s==="l"?B("rewrites","LLM rewrite attempts","done",`${v.length} attempt${v.length===1?"":"s"} · ${v.filter(z=>!z.ok).length} rejected, 1 accepted`):s==="lx"?B("rewrites","LLM rewrite attempts","failed","3 attempts, none accepted",((k=v[2])==null?void 0:k.error)??null):s==="a"?B("rewrites","LLM rewrite attempts","skipped","Not needed","Auto-annotation from observed types was enough; no LLM call made."):s==="fx"||s==="n"?de("rewrites","LLM rewrite attempts",s==="n"?"Not fixable":"Below rewrite threshold"):B("rewrites","LLM rewrite attempts","skipped","Not needed","The typechecker accepted the function as written."),$?B("pysub","Final PySub","done",s==="l"?"LLM rewrite (typechecker-approved)":s==="a"?"Annotated from observed types":"Unchanged"):de("pysub","Final PySub","No PySub produced"),...O?[B("tokens","Tokens","done",`${O.tokens.length} tokens`),B("ast","AST","done","Parsed"),B("typed_ast","Typed AST","done","All expressions typed"),B("pir","PIR","done",`${j.length} fidelity note${j.length===1?"":"s"} · guards ${((m=O.guard_elision)==null?void 0:m.elided)??0} elided / ${((w=O.guard_elision)==null?void 0:w.kept)??0} kept`),B("cpp","Generated C++","done",`${E.split(`
`).length} lines`),B("wrapper","pybind11 wrapper","done",`${y.split(`
`).length} lines`),B("build","Build","done",ye?"Cache hit":`${$e.toFixed(1)}s`)]:["tokens","ast","typed_ast","pir","cpp","wrapper","build"].map(z=>de(z,{tokens:"Tokens",ast:"AST",typed_ast:"Typed AST",pir:"PIR",cpp:"Generated C++",wrapper:"pybind11 wrapper",build:"Build"}[z],"Skipped")),s==="f"?B("replay","Oracle replay","failed",`${U.matched}/${U.total} matched`,`First counterexample: ${u.mismatch.args} -> Python ${u.mismatch.python}, C++ ${u.mismatch.cpp}`):U?B("replay","Oracle replay","done",`${U.matched}/${U.total} matched`):s==="d"?B("replay","Oracle replay","skipped","Probe only","Declined by the ranker; compiled as a probe and not replayed."):de("replay","Oracle replay","Skipped"),te?B("benchmark",s==="d"?"Benchmark (probe)":"Benchmark","done",`${te.py_ms.toFixed(1)} ms -> ${te.cpp_ms.toFixed(2)} ms · ${te.speedup.toFixed(1)}x`):de("benchmark","Benchmark",s==="f"?"Not benchmarked: replay failed":"Skipped"),we?B("splice","Splice","done","Decorator applied in work copy"):B("splice","Splice","skipped","Not spliced",s==="d"?"Declined: compiled as a probe only, never spliced.":s==="f"?"Auto-rejected: replay mismatch.":De??"Skipped"),B("status","Status",C==="failed"||C==="not_eligible"?"failed":"done",C.replace("_"," "),C==="verified"||C==="guarded"?null:u.reason??null)];(C==="not_eligible"||C==="declined"||C==="fixable")&&(Le[15].state="skipped");const Fe={id:l.id,file:l.id.split("::")[0],name:l.name,qualname:l.qualname,line:l.line,end_line:l.end_line,col:0,status:C,eligibility:x,reason:C==="verified"||C==="guarded"?null:u.reason??null,decision:"pending",score:ie,share:Y,calls:G,speedup:C==="verified"||C==="guarded"?I:null,probe_speedup:s==="d"?u.probe:null,metrics:lt(u.src,/STOPWORDS|np\./.test(u.src)?["STOPWORDS"].filter(z=>u.src.includes(z)):[]),trace:n,sources:{original:u.src,annotated:_,pysub:$,cpp:E,wrapper_cpp:y},line_map_ok:s!=="l",cpp_line_map:b,rewrites:v,diagnostics:T,fidelity:j,build:Ye,replay:U,bench:te,splice:we?{applied:!0,diff:Ze}:null,journey:Le},Re={spec:u,rec:Fe,attemptsFinal:v,finalStatus:C,modname:L};i.push(Re),c[Fe.id]=Re}return{files:t,fns:i,byId:c,stagesCache:p}}const Me=(r,e)=>({id:r.id,file:r.file,name:r.name,qualname:r.qualname,line:r.line,end_line:r.end_line,col:r.col,status:e??r.status,eligibility:r.eligibility,reason:r.reason,decision:r.decision,score:r.score,share:r.share,calls:r.calls,speedup:r.speedup,probe_speedup:r.probe_speedup});function dt(r,e){const t=[],o=new Map,d=c=>{if(!c)return t;let p=o.get(c);if(!p){const g=c.split("/"),P=d(g.slice(0,-1).join("/"));p={path:c,name:g[g.length-1],type:"dir",children:[],badges:{hotspots:0,accelerated:0}},P.push(p),o.set(c,p)}return p.children};for(const c of r.files){const p=c.path.split("/").slice(0,-1).join("/"),g=d(p),P=c.fns.map(u=>r.byId[u].rec),k=P.filter(u=>u.eligibility!=="not_eligible"&&(u.share??0)>=.01).length,m=P.filter(u=>(u.status==="verified"||u.status==="guarded")&&e[u.id]!=="rejected").length;g.push({path:c.path,name:c.path.split("/").pop(),type:"file",badges:{hotspots:k,accelerated:m}});let w=p;for(;w;){const u=o.get(w);u.badges.hotspots+=k,u.badges.accelerated+=m,w=w.split("/").slice(0,-1).join("/")}}const i=c=>{c.sort((p,g)=>p.type===g.type?p.name.localeCompare(g.name):p.type==="dir"?-1:1),c.forEach(p=>p.children&&i(p.children))};return i(t),t}function Ke(r,e,t){const o=e.content.split(`
`),d=e.fns.map(P=>r.byId[P]).filter(P=>(P.finalStatus==="verified"||P.finalStatus==="guarded")&&t[P.rec.id]!=="rejected");if(!d.length)return e.content;const i=new Map;for(const P of d)i.set(P.rec.line,`@_pythia_accelerated("${P.modname}", "${P.rec.name}")`);const c=[],p=(Ae[e.path]??"").replace(/\n+$/,""),g=p?p.split(`
`).length:0;return o.forEach((P,k)=>{const m=k+1;m===g+1&&g>0&&c.push("",...rt.split(`
`).slice(0,-1));const w=i.get(m);w&&c.push(/\(self\b/.test(P)?"    "+w:w),c.push(P)}),c.join(`
`)}const me="demo0001",pe="ws000001",he="python main.py --small";function ut(r,e={}){var oe,ie;const t=[];let o=0,d=1e3;const i=(n,I,M=null,F=null,U=.05)=>{d+=U,t.push({seq:++o,ts:Math.round(d*1e3)/1e3,type:n,stage:M,caption:F,data:I})},c=(n,I,M=null,F=null,U=null)=>i("stage",{stage:n,state:I,summary:M,progress:F},n,U,.1),p=(n,I,M,F="info")=>i("log",{stream:n,level:F,text:I},M,null,.02),g=(n,I,M,F,U,W,ne=null)=>i("agent.step",{step_id:n,fn_id:I,title:M,state:F,detail:U},W,ne,.08),k=r.fns.map(n=>n.rec),m={trace_cmd:he,trace_timeout_s:60,offline:!0,llm:!0,model:"claude-sonnet-5-5",pace_ms:0,...e};i("job.start",{job_id:me,workspace_id:pe,name:"textlab",input_kind:"demo",options:m},null,"Opening the textlab demo project. The original is never modified; PYTHIA works on a copy."),c("ingest","running",null,0),p("system","workspace ws000001 created","ingest");const w=r.files.length,u=w+7,l=r.files.map(n=>n.path);for(let n=0;n<7;n++){const I=Math.round((n+1)/7*u);i("ingest.progress",{phase:"copy",files:I,bytes:I*3100+480,current:l[n%l.length],message:`Copying ${l[n%l.length]}`},"ingest",n===0?"Copying the project into an isolated workspace.":null,.12)}i("ingest.progress",{phase:"index",files:u,bytes:u*3100,current:null,message:`Indexed ${w} Python files`},"ingest",null,.1),i("ingest.done",{workspace_id:pe,name:"textlab",files:u,py_files:w,skipped:[{path:".git",reason:"ignored directory"},{path:"__pycache__",reason:"ignored directory"},{path:"data/corpus_full.txt",reason:"larger than 5 MB"},{path:".venv",reason:"ignored directory"}]},"ingest",null,.1),c("ingest","done",`${w} .py files`,1),c("scan","running",null,0,"Scanning every function and asking the typechecker which ones PYTHIA could compile.");for(const n of r.files)if(n.fns.length){g(`scan:${n.path}`,null,`Scanning \`${n.path.split("/").slice(-1)[0]}\``,"done",`${n.fns.length} function${n.fns.length===1?"":"s"} · ${n.path}`,"scan");for(const I of n.fns){const M=r.byId[I].rec,F=Me(M);F.status=M.eligibility==="verifiable"?"pending":M.eligibility==="fixable"?"fixable":"not_eligible",F.reason=M.eligibility==="verifiable"?null:M.reason??((oe=M.diagnostics[0])==null?void 0:oe.msg)??null,F.share=null,F.calls=null,F.speedup=null,F.probe_speedup=null,F.score={total:Math.round((M.score.static_heuristic??.3)*(M.eligibility==="not_eligible"?.1:1)*100)/100,trace_share:null,static_heuristic:M.score.static_heuristic,eligibility_factor:M.score.eligibility_factor,expected_benefit:null,boundary_penalty:null,basis:"static",notes:["static estimate: no trace yet"]},i("scan.function",{function:F},"scan",null,.03)}}const a=n=>k.filter(I=>I.eligibility===n).length;i("scan.done",{functions:k.length,verifiable:a("verifiable"),fixable:a("fixable"),not_eligible:a("not_eligible")},"scan",`Found ${k.length} functions: ${a("verifiable")} compile as written, ${a("fixable")} are fixable, ${a("not_eligible")} cannot be compiled.`,.1),c("scan","done",`${k.length} functions`,1),c("trace","running",null,0,`Running \`${he}\` under the tracer to find real hot spots and record real arguments.`),g("trace",null,`Tracing \`${he}\``,"running","sys.monitoring · 500 samples per function","trace");const s=k.reduce((n,I)=>n+(I.calls??0),0),D=["textlab 0.4 · small corpus (600 docs)"],A=14;for(let n=1;n<=A;n++){const I=n/A;n%3===0&&D.push(["loaded 600 documents","tokenised 4210 words","deduplicated 600 -> 412 words","k-means iteration "+n/3+" / 4","simulated 300 steps"][Math.min(4,Math.floor(n/3)-1)]),i("trace.progress",{calls:Math.round(s*I),functions_seen:Math.round(k.length*Math.min(1,I*1.4)),elapsed_s:Math.round(14.8*I*10)/10,stdout_tail:D.slice(-4).join(`
`)},"trace",n===6?`Recorded ${Math.round(s*I).toLocaleString("en-US")} calls so far.`:null,.15),n%4===0&&p("trace",D[D.length-1],"trace")}i("trace.done",{total_s:14.8,exit_code:0,timed_out:!1,calls:s,profile:k.filter(n=>n.calls).map(n=>({id:n.id,calls:n.calls,cum_s:n.trace.cum_s,share:n.share})).sort((n,I)=>I.share-n.share)},"trace",`Trace finished: ${s.toLocaleString("en-US")} calls in 14.8 s of real work.`,.1),g("trace",null,`Traced \`${he}\``,"done",`${s.toLocaleString("en-US")} calls · 14.8 s`,"trace"),c("trace","done",`${(s/1e3).toFixed(0)}k calls`,1),c("rank","running",null,0,"Ranking by trace time share, expected benefit and the cost of crossing the Python/C++ boundary.");const x=[...k].sort((n,I)=>I.score.total-n.score.total),_=x.map((n,I)=>({id:n.id,rank:I+1,score:n.score,status:n.status==="declined"?"declined":n.eligibility==="not_eligible"?"not_eligible":n.eligibility==="fixable"?"fixable":"pending",reason:n.status==="declined"?n.reason:n.eligibility==="verifiable"?null:n.reason})),h=x.find(n=>n.eligibility!=="not_eligible"),S=k.filter(n=>n.status==="declined");i("rank.done",{ranking:_},"rank",`Top hotspot: ${h.name} (${((h.share??0)*100).toFixed(1)}% of runtime).${S.length?` Declined ${S[0].name}: marshalling would cost more than it saves.`:""}`,.1),g("rank",null,"Ranked hotspots","done",`${h.name} leads with ${((h.share??0)*100).toFixed(1)}% of traced runtime`,"rank");for(const n of S)g(`declined:${n.id}`,n.id,`\`${n.name}\` → declined by the ranker`,"info",n.reason,"rank");c("rank","done",`top: ${h.name}`,1);const $=x.filter(n=>["a","l","lx","fx"].includes(r.byId[n.id].spec.kind));c("fix","running",null,0,"Some functions are almost PySub. Auto-annotation and the LLM fixer try to make them compile.");const v=[];for(const n of $){const I=r.byId[n.id],M=I.spec.kind,F=`fn:${n.id}`;if(M==="fx"){g(F,n.id,`\`${n.name}\` → skipped (below rewrite threshold)`,"info",n.reason,"fix",null);continue}if(M==="a"){g(F,n.id,`\`${n.name}\` → annotating from observed types`,"running",`(${n.trace.arg_types.join(", ")}) → ${n.trace.ret_type}`,"fix"),g(F,n.id,`\`${n.name}\` → annotated from observed types`,"running",`(${n.trace.arg_types.join(", ")}) → ${n.trace.ret_type}. No LLM call needed.`,"fix",`${n.name} only needs type annotations; the trace already observed them.`),v.push(n.id);continue}const U=((ie=n.diagnostics.find(W=>W.phase==="eligibility"))==null?void 0:ie.msg)??n.reason??"not PySub";g(F,n.id,`\`${n.name}\` → asking the LLM for a PySub rewrite`,"running",`Typechecker rejected: ${U}`,"fix",`Typechecker rejected: ${U.replace(/\.$/,"")} → asking the LLM for a PySub rewrite`),I.attemptsFinal.forEach((W,ne)=>{var te;i("fix.attempt",{id:n.id,attempt:W.attempt,source:W.source,ok:W.ok,error:W.error,pysub:W.pysub},"fix",W.ok?`Attempt ${W.attempt} passes the typechecker.`:`Attempt ${W.attempt} rejected by the typechecker: ${(te=W.error)==null?void 0:te.replace(/^line \d+:\s*/,"")}${ne<I.attemptsFinal.length-1?" Feeding the error back to the LLM.":""}`,.6),W.ok||g(F,n.id,`\`${n.name}\` → rewrite attempt ${W.attempt} rejected`,"running",W.error,"fix")}),M==="l"?(i("fix.done",{id:n.id,ok:!0,reason:null},"fix",null,.1),g(F,n.id,`\`${n.name}\` → PySub ✓`,"running",`Accepted after ${I.attemptsFinal.length} attempt${I.attemptsFinal.length===1?"":"s"}`,"fix"),v.push(n.id)):(i("fix.done",{id:n.id,ok:!1,reason:n.reason},"fix",`The fixer gave up on ${n.name}: ${n.reason}`,.1),g(F,n.id,`\`${n.name}\` → not eligible`,"failed",n.reason,"fix"))}c("fix","done",`${v.length}/${$.filter(n=>r.byId[n.id].spec.kind!=="fx").length} fixed`,1);const O=x.filter(n=>["v","g","a","l","d","f"].includes(r.byId[n.id].spec.kind));c("compile","running",null,0,`Compiling ${O.length} functions: PySub → C++17 → pybind11 extension modules.`);for(const n of O){const I=r.byId[n.id],M=n.build,F=`\`${n.name}\``,U=v.includes(n.id)?I.spec.kind==="l"?`${F} → PySub ✓`:`${F} → annotated`:`${F}`;g(`fn:${n.id}`,n.id,`${U} → compiling`,"running",null,"compile");for(const W of M.log.split(`
`))p("build",W,"compile");i("compile.done",{id:n.id,ok:!0,cached:M.cached,compile_s:M.compile_s,module:M.module,error:null,diagnostics:[]},"compile",null,.2),g(`fn:${n.id}`,n.id,`${U} → C++ ✓`,"running",`${M.module} · ${M.cached?"cache hit":M.compile_s.toFixed(1)+" s"}`,"compile")}c("compile","done",`${O.length} built`,1);const E=O.filter(n=>r.byId[n.id].spec.kind!=="d");c("verify","running",null,0,"Replaying recorded calls through CPython and the compiled module. Return values, exceptions and mutations must match exactly.");let y=0;for(const n of E){const I=r.byId[n.id],M=n.replay,F=I.spec.kind==="f"?"failed":I.finalStatus==="guarded"?"guarded":"verified";F!=="failed"&&y++;const U=v.includes(n.id)?I.spec.kind==="l"?"PySub ✓ → C++ ✓":"annotated → C++ ✓":"PySub ✓ → C++ ✓";i("verify.result",{id:n.id,status:F,total:M.total,matched:M.matched,first_mismatch:M.first_mismatch},"verify",F==="failed"?`${n.name} FAILED replay: ${M.first_mismatch.args} gave ${M.first_mismatch.python} in Python but ${M.first_mismatch.cpp} in C++. Auto-rejected.`:null,.15),g(`fn:${n.id}`,n.id,`\`${n.name}\` → ${U} → ${M.matched}/${M.total} replays match`,F==="failed"?"failed":"running",F==="failed"?`Counterexample ${M.first_mismatch.args}: Python ${M.first_mismatch.python}, C++ ${M.first_mismatch.cpp}`:F==="guarded"?`${n.fidelity.filter(W=>W.severity!=="exact").length} guarded site(s)`:null,"verify")}c("verify","done",`${y}/${E.length}`,1),c("benchmark","running",null,0,"Timing Python against C++ on the recorded inputs, then the whole program end to end.");const b=O.filter(n=>r.byId[n.id].spec.kind!=="f");for(const n of b){const I=r.byId[n.id],M=n.bench,F=I.spec.kind==="d";i("bench.result",{id:n.id,py_ms:M.py_ms,cpp_ms:M.cpp_ms,speedup:M.speedup,calls_timed:M.calls_timed,probe:F},"benchmark",F?`Probe: ${n.name} would run at ${M.speedup.toFixed(2)}× — slower than Python, so it is not spliced.`:null,.15),F?g(`fn:${n.id}`,n.id,`\`${n.name}\` → probe ${M.speedup.toFixed(2)}× (declined)`,"done","Measured slower than CPython because of marshalling; never spliced.","benchmark"):g(`fn:${n.id}`,n.id,`\`${n.name}\` → ${v.includes(n.id)?I.spec.kind==="l"?"PySub ✓ → ":"annotated → ":"PySub ✓ → "}C++ ✓ → ${n.replay.matched}/${n.replay.total} replays match → ${M.speedup.toFixed(1)}×`,"done",null,"benchmark")}const j=O.filter(n=>r.byId[n.id].spec.kind==="f");for(const n of j)g(`fn:${n.id}`,n.id,`\`${n.name}\` → replay mismatch → rejected`,"failed",n.reason,"benchmark");i("bench.e2e",{cmd:he,before_s:14.8,after_s:2.6,speedup:5.69,output_match:!0,ok:!0},"benchmark","End to end: 14.8 s → 2.6 s, 5.7× faster, and the program output is byte-identical.",.4),c("benchmark","done","5.7× e2e",1),c("splice","running",null,0,"Splicing the verified functions back into the workspace copy.");const L=k.filter(n=>n.status==="verified"||n.status==="guarded"),T=new Map;for(const n of L)T.set(n.file,[...T.get(n.file)??[],n.id]);i("splice.ready",{files:[...T.entries()].map(([n,I])=>({path:n,functions:I})),functions:L.length},"splice",`${L.length} functions spliced into ${T.size} files. Review each diff, then accept or reject.`,.2),g("splice",null,"Splice ready for review","done",`${L.length} functions in ${T.size} files`,"splice"),c("splice","done",`${L.length} functions`,1),c("export","idle");const C=n=>k.filter(I=>I.status===n).length,q=L.map(n=>n.speedup).filter(Boolean),Y=Math.exp(q.reduce((n,I)=>n+Math.log(I),0)/q.length),G={functions:k.length,verified:C("verified"),guarded:C("guarded"),fixable:C("fixable"),not_eligible:C("not_eligible"),failed:C("failed"),declined:C("declined"),e2e_speedup:5.69,geomean_speedup:Math.round(Y*10)/10};return i("job.done",{state:"done",summary:G},null,`Done. ${G.verified+G.guarded} functions verified, ${G.e2e_speedup}× faster end to end. The LLM suggested; the compiler proved.`,.2),t}const K=(r,e=60)=>new Promise(t=>setTimeout(()=>t(r),e)),ft=new URLSearchParams(window.location.search);let ht=null,mt=null;const Z=()=>ht??(ht=pt()),ae=()=>mt??(mt=ut(Z())),le={},X={offline:!0,model:"claude-sonnet-5-5",api_key_set:!1},Ue=()=>{const r=ae()[ae().length-1];return{job_id:me,workspace_id:pe,name:"textlab",state:"done",options:ae()[0].data.options,started:1e3,finished:1030,summary:r.data.summary}},gt=(r,e)=>({original:r,modified:e}),yt={env:()=>K({compiler:ft.get("nocompiler")==="1"?{found:!1,name:null,version:null,hint:"Install a C++17 compiler: on Ubuntu or WSL run `sudo apt install g++ python3-dev`; on macOS run `xcode-select --install`."}:{found:!0,name:"g++",version:"15.2.0",hint:null},pybind11:!0,python:"3.14.0",platform:"linux",wsl:!0,llm:{enabled:X.api_key_set?!0:X.offline,model:X.model,hint:X.offline?"Replaying recorded rewrites (offline cache)":"Set ANTHROPIC_API_KEY to enable the LLM fixer"},offline_available:!0,offline:X.offline},30),getSettings:()=>K({...X},20),putSettings:r=>(Object.assign(X,r),r.api_key&&(X.api_key_set=!0,delete X.api_key),K({...X},20)),startJob:()=>K({job_id:me,workspace_id:pe},120),jobs:()=>K([Ue()],20),job:()=>K(Ue(),20),events:(r,e=0)=>K({events:ae().filter(t=>t.seq>e),last_seq:ae()[ae().length-1].seq},40),cancel:()=>K(void 0,10),functions:()=>K(Z().fns.map(r=>Me(r.rec)),30),fn:(r,e,t=!1)=>{const o=Z().byId[e];if(!o)return Promise.reject(new Error(`Unknown function ${e}`));const d={...o.rec,decision:le[e]??"pending"};return t&&Z().stagesCache[e]&&(d.stages=Z().stagesCache[e]),K(d,45)},decide:(r,e,t)=>{const o=e==="all"?Z().fns.filter(d=>d.finalStatus==="verified"||d.finalStatus==="guarded").map(d=>d.rec.id):[e];for(const d of o)le[d]=t;return K({functions:Z().fns.map(d=>Me({...d.rec,decision:le[d.rec.id]??"pending"}))},40)},fileDiff:(r,e)=>{const t=Z().files.find(o=>o.path===e);return t?K(gt(t.content,Ke(Z(),t,le)),40):Promise.reject(new Error("No such file"))},exportProject:()=>K({path:"/home/vishal/pythia-out/textlab-accelerated"},500),exportZipUrl:()=>"#",report:()=>{const r=Z().fns.map(o=>o.rec),t=`# PYTHIA report: textlab

End-to-end: 14.8 s -> 2.6 s (5.7x), output identical.

| function | status | speedup |
|---|---|---|
`+r.filter(o=>o.status==="verified"||o.status==="guarded").map(o=>`| ${o.id} | ${o.status} | ${o.speedup}x |`).join(`
`);return K({markdown:t,json:{functions:r.length}},40)},recent:()=>K([{workspace_id:pe,name:"textlab (demo project)",path:"demo/textlab",job_id:me,opened:Date.now()/1e3-3600},{workspace_id:"ws000002",name:"pyrt-playground",path:"~/code/pyrt-playground",job_id:null,opened:Date.now()/1e3-86400*2}],20),tree:()=>K(dt(Z(),le),30),file:(r,e,t="work")=>{const o=Z().files.find(i=>i.path===e);if(!o)return Promise.reject(new Error(`No such file: ${e}`));const d=t==="work"?Ke(Z(),o,le):o.content;return K({path:e,content:d,language:"python",size:d.length},30)},fsList:r=>{const e={"/":["home","mnt","tmp"],"/home":["vishal"],"/home/vishal":["code","Downloads","projects"],"/home/vishal/code":["textlab","pyrt-playground","notes"],"/home/vishal/projects":["segmenter","wordbench"]},t=r&&r!=="~"?r.replace(/\/$/,"")||"/":"/home/vishal",o=e[t]??[],d=t==="/"?null:t.split("/").slice(0,-1).join("/")||"/";return K({path:t,parent:d,entries:[...o.map(i=>({name:i,type:"dir"})),...t.endsWith("textlab")?[{name:"main.py",type:"file"}]:[]]},40)},pgCompile:r=>K(Be(r),120),pgRun:r=>{var d;const e=it(r),t=Be(r);if(!t.ok)return K({ok:!1,error:((d=t.diagnostics[0])==null?void 0:d.msg)??"compile failed",python:{stdout:e.stdout,exception:e.exception,time_ms:0},cpp:{stdout:"",exception:null,time_ms:0},same:!1},200);const o=Math.max(.05,e.steps*35e-5);return K({ok:!0,python:{stdout:e.stdout,exception:e.exception,time_ms:Math.round(o*100)/100},cpp:{stdout:e.stdout,exception:e.exception,time_ms:Math.round(Math.max(.01,o/31)*100)/100},same:!0},350)},stages:r=>K(st(r),80),upload:()=>K({job_id:me,workspace_id:pe},200),subscribe(r,e,t,o){let d=!1;return queueMicrotask(()=>{for(const i of ae()){if(d)return;i.seq>e&&t(i)}o("done")}),()=>{d=!0}}};export{yt as mockApi};
