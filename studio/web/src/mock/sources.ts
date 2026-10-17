// Source text + outcome specs for the mock "textlab" project (~60 module-level functions).
export type Kind =
  | 'v' // eligible as written, verified
  | 'g' // eligible, guarded sites remain
  | 'a' // fixable by annotation only (observed types), no LLM
  | 'l' // fixed by LLM rewrite
  | 'lx' // LLM exhausted -> not eligible
  | 'fx' // fixable, left alone (below fix threshold)
  | 'n' // not eligible (static reason)
  | 'd' // declined (boundary cost)
  | 'f' // replay mismatch

export interface Spec {
  file: string
  kind: Kind
  src: string
  share?: number
  calls?: number
  speedup?: number
  reason?: string
  annotated?: string
  attempts?: { pysub: string; error: string | null; source?: 'api' | 'cache' }[]
  probe?: number
  mismatch?: { args: string; python: string; cpp: string; kind: 'value' | 'exception' | 'mutation' }
  extraNotes?: { line: number; cls: string; detail: string; mitigation: string; severity: 'exact' | 'guarded' | 'divergent' }[]
  elems?: number
}

export const HEADERS: Record<string, string> = {
  'textlab/__init__.py': '"""textlab: a small text and clustering toolkit."""',
  'textlab/main.py': 'import argparse\nimport time\n\nfrom textlab.text.distance import fuzzy_dedupe\nfrom textlab.ml.kmeans import assign_clusters\n',
  'textlab/report.py': 'import statistics\n',
  'textlab/text/distance.py': '"""String distances used for fuzzy de-duplication."""\n',
  'textlab/text/tokenize.py': 'import re\nimport unicodedata\n\nSTOPWORDS = set(open("stopwords.txt").read().split())\n',
  'textlab/text/features.py': 'import numpy as np\n\nVOCAB_LIMIT = 50000\n',
  'textlab/ml/kmeans.py': '"""Hand-written k-means building blocks."""\n',
  'textlab/sim/nbody.py': '"""Direct-summation n-body step."""\n',
  'textlab/data/loader.py': 'import json\n',
  'textlab/utils/mathx.py': '"""Small numeric helpers."""\n',
  'textlab/utils/cache.py': 'import functools\nimport time\n',
}

export const SPECS: Spec[] = [
  // ---------------- text/distance.py ----------------
  {
    file: 'textlab/text/distance.py', kind: 'v', share: 0.205, calls: 1204, speedup: 38.2, elems: 38,
    src: `def edit_distance(a: str, b: str) -> int:
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
    return prev[m]`,
  },
  {
    file: 'textlab/text/distance.py', kind: 'v', share: 0.031, calls: 3120, speedup: 29.7, elems: 41,
    src: `def lcs_length(a: str, b: str) -> int:
    table: list[list[int]] = []
    for i in range(len(a) + 1):
        table.append([0] * (len(b) + 1))
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    return table[len(a)][len(b)]`,
  },
  {
    file: 'textlab/text/distance.py', kind: 'v', share: 0.012, calls: 9400, speedup: 21.4, elems: 24,
    src: `def hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return -1
    diff = 0
    for i in range(len(a)):
        if a[i] != b[i]:
            diff += 1
    return diff`,
  },
  {
    file: 'textlab/text/distance.py', kind: 'a', share: 0.017, calls: 5200, speedup: 17.8, elems: 30,
    src: `def similarity(a, b):
    if len(a) == 0 or len(b) == 0:
        return 0.0
    matches = 0
    for ch in a:
        if ch in b:
            matches += 1
    return 2.0 * matches / (len(a) + len(b))`,
    annotated: `def similarity(a: str, b: str) -> float:
    if len(a) == 0 or len(b) == 0:
        return 0.0
    matches = 0
    for ch in a:
        if ch in b:
            matches += 1
    return 2.0 * matches / (len(a) + len(b))`,
    reason: 'Parameters are unannotated; observed types (str, str) -> float supply the annotations.',
  },
  {
    file: 'textlab/text/distance.py', kind: 'v', share: 0.004, calls: 800, speedup: 12.1, elems: 18,
    src: `def common_prefix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return i`,
  },
  {
    file: 'textlab/text/distance.py', kind: 'v', share: 0.006, calls: 1204, speedup: 33.0, elems: 38,
    src: `def normalized_distance(a: str, b: str) -> float:
    longest = max(len(a), len(b))
    if longest == 0:
        return 0.0
    return edit_distance(a, b) / longest`,
  },
  {
    file: 'textlab/text/distance.py', kind: 'v', share: 0.052, calls: 40, speedup: 27.6, elems: 600,
    src: `def fuzzy_dedupe(words: list[str], max_dist: int) -> list[int]:
    keep: list[int] = []
    for i in range(len(words)):
        dup = False
        for k in keep:
            if edit_distance(words[i], words[k]) <= max_dist:
                dup = True
                break
        if not dup:
            keep.append(i)
    return keep`,
  },
  // ---------------- text/tokenize.py ----------------
  {
    file: 'textlab/text/tokenize.py', kind: 'v', share: 0.092, calls: 410, speedup: 24.6, elems: 4200,
    src: `def count_pairs(ids: list[int]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for i in range(len(ids) - 1):
        key = ids[i] * 65536 + ids[i + 1]
        counts[key] = counts.get(key, 0) + 1
    return counts`,
  },
  {
    file: 'textlab/text/tokenize.py', kind: 'g', share: 0.024, calls: 410, speedup: 18.3, elems: 4200,
    src: `def merge_pair(ids: list[int], a: int, b: int, new_id: int) -> list[int]:
    out: list[int] = []
    i = 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == a and ids[i + 1] == b:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out`,
    extraNotes: [{ line: 2, cls: 'D7 memory is not reclaimed', detail: 'The runtime does not free the list built inside the call; a long-lived process would grow with every merge.', mitigation: 'An arena releases all allocations made during one call after the result has been copied back to Python.', severity: 'divergent' }],
  },
  {
    file: 'textlab/text/tokenize.py', kind: 'l', share: 0.071, calls: 2210, speedup: 14.9, elems: 120,
    src: `def char_histogram(text):
    letters = [c for c in text if c.isalpha()]
    counts = {}
    for c in letters:
        counts[c] = counts.get(c, 0) + 1
    return counts`,
    annotated: `def char_histogram(text: str) -> dict[str, int]:
    letters = [c for c in text if c.isalpha()]
    counts = {}
    for c in letters:
        counts[c] = counts.get(c, 0) + 1
    return counts`,
    attempts: [
      {
        source: 'api', error: "line 6: method 'isalpha' of str is not part of PySub; call ord() and compare code points",
        pysub: `def char_histogram(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in text:
        if c.isalpha():
            counts[c] = counts.get(c, 0) + 1
    return counts`,
      },
      {
        source: 'api', error: null,
        pysub: `def char_histogram(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in text:
        o = ord(c)
        if (o >= 65 and o <= 90) or (o >= 97 and o <= 122):
            counts[c] = counts.get(c, 0) + 1
    return counts`,
      },
    ],
    reason: 'List comprehension is outside PySub; a loop rewrite is straightforward.',
  },
  {
    file: 'textlab/text/tokenize.py', kind: 'l', share: 0.038, calls: 2210, speedup: 11.2, elems: 120,
    src: `def split_words(text):
    words = []
    start = 0
    for i, ch in enumerate(text):
        if ch == " ":
            if i > start:
                words.append(text[start:i])
            start = i + 1
    if start < len(text):
        words.append(text[start:])
    return words`,
    annotated: `def split_words(text: str) -> list[str]:
    words = []
    start = 0
    for i, ch in enumerate(text):
        if ch == " ":
            if i > start:
                words.append(text[start:i])
            start = i + 1
    if start < len(text):
        words.append(text[start:])
    return words`,
    attempts: [
      {
        source: 'cache', error: null,
        pysub: `def split_words(text: str) -> list[str]:
    words: list[str] = []
    start = 0
    for i in range(len(text)):
        if text[i] == " ":
            if i > start:
                words.append(text[start:i])
            start = i + 1
    if start < len(text):
        words.append(text[start:])
    return words`,
      },
    ],
    reason: "enumerate() is not part of PySub.",
  },
  {
    file: 'textlab/text/tokenize.py', kind: 'n', share: 0.021, calls: 2210,
    reason: 'Calls re.sub: module `re` is not available in PySub (no imports).',
    src: `def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\\s+", " ", text).strip()`,
  },
  {
    file: 'textlab/text/tokenize.py', kind: 'n', share: 0.006, calls: 410,
    reason: 'Calls unicodedata.normalize: external module, non-ASCII text handling.',
    src: `def strip_accents(text):
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))`,
  },
  {
    file: 'textlab/text/tokenize.py', kind: 'n', share: 0.003, calls: 8800,
    reason: 'Reads module-level set STOPWORDS built at import time from a file (not a literal constant).',
    src: `def is_stopword(word: str) -> bool:
    return word in STOPWORDS`,
  },
  // ---------------- text/features.py ----------------
  {
    file: 'textlab/text/features.py', kind: 'g', share: 0.043, calls: 6100, speedup: 26.1, elems: 22,
    src: `def ngram_hash(s: str, n: int) -> int:
    h = 7
    for i in range(len(s) - n + 1):
        for j in range(n):
            h = (h * 31 + ord(s[i + j])) % 1000000007
    return h`,
  },
  {
    file: 'textlab/text/features.py', kind: 'v', share: 0.016, calls: 52000, speedup: 45.3, elems: 1,
    src: `def is_prime(n: int) -> bool:
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True`,
  },
  {
    file: 'textlab/text/features.py', kind: 'v', share: 0.054, calls: 6, speedup: 61.8, elems: 1,
    src: `def prime_count(limit: int) -> int:
    sieve = [True] * (limit + 1)
    count = 0
    for i in range(2, limit + 1):
        if sieve[i]:
            count += 1
            for j in range(i * i, limit + 1, i):
                sieve[j] = False
    return count`,
  },
  {
    file: 'textlab/text/features.py', kind: 'v', share: 0.011, calls: 2210, speedup: 19.5, elems: 120,
    src: `def vowel_ratio(s: str) -> float:
    if len(s) == 0:
        return 0.0
    vowels = 0
    for ch in s:
        if ch in "aeiouAEIOU":
            vowels += 1
    return vowels / len(s)`,
  },
  {
    file: 'textlab/text/features.py', kind: 'd', share: 0.034, calls: 1000000, probe: 0.62, elems: 10000,
    reason: 'Compiles and typechecks, but the ranker predicts a net loss: 1,000,000 calls each marshal a 10,000-element list (about 80 MB per second of copying) for about 2 microseconds of arithmetic saved.',
    src: `def rolling_checksum(data: list[int]) -> int:
    acc = 0
    for i in range(len(data)):
        acc = (acc * 31 + data[i]) % 65521
    return acc`,
  },
  {
    file: 'textlab/text/features.py', kind: 'v', share: 0.002, calls: 3300, speedup: 9.4, elems: 1,
    src: `def tfidf_weight(tf: int, df: int, n_docs: int) -> float:
    if df == 0:
        return 0.0
    return (1.0 + tf) * (n_docs / df)`,
  },
  {
    file: 'textlab/text/features.py', kind: 'lx', share: 0.019, calls: 410,
    src: `def build_feature_vector(doc):
    counts = {w: doc.count(w) for w in set(doc.split())}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [v for _, v in ranked[:64]]`,
    annotated: `def build_feature_vector(doc: str) -> list[int]:
    counts = {w: doc.count(w) for w in set(doc.split())}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [v for _, v in ranked[:64]]`,
    attempts: [
      { source: 'api', error: "line 2: dict comprehension is not part of PySub", pysub: `def build_feature_vector(doc: str) -> list[int]:
    counts: dict[str, int] = {}
    for w in set(doc.split()):
        counts[w] = doc.count(w)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [v for _, v in ranked[:64]]` },
      { source: 'api', error: "line 5: sorted() with a key function (lambda) is not part of PySub", pysub: `def build_feature_vector(doc: str) -> list[int]:
    counts: dict[str, int] = {}
    for w in doc.split():
        counts[w] = counts.get(w, 0) + 1
    values: list[int] = []
    for w in counts:
        values.append(counts[w])
    values.sort(key=lambda v: -v)
    return values[:64]` },
      { source: 'api', error: "line 8: lambda is not part of PySub; sort() takes no key argument", pysub: `def build_feature_vector(doc: str) -> list[int]:
    counts: dict[str, int] = {}
    for w in doc.split():
        counts[w] = counts.get(w, 0) + 1
    values: list[int] = []
    for w in counts:
        values.append(counts[w])
    values.sort(reverse=True)
    return values[:64]` },
    ],
    reason: 'LLM rewrite did not pass the typechecker after 3 attempts: sort(reverse=True) keyword arguments are not part of PySub. Left as Python.',
  },
  {
    file: 'textlab/text/features.py', kind: 'n', share: 0.008, calls: 60,
    reason: 'Calls numpy (np.zeros, np.dot): third-party array library is outside PySub.',
    src: `def tfidf_matrix(docs, vocab):
    m = np.zeros((len(docs), len(vocab)))
    for i, d in enumerate(docs):
        for j, w in enumerate(vocab):
            m[i, j] = d.count(w)
    return m @ m.T`,
  },
  {
    file: 'textlab/text/features.py', kind: 'fx', share: 0.003, calls: 60,
    reason: 'Fixable (sorted with a key function), but only 0.3% of runtime: below the rewrite threshold, so no LLM call was spent.',
    src: `def top_k_terms(counts, k):
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [w for w, _ in ranked[:k]]`,
  },
  // ---------------- ml/kmeans.py ----------------
  {
    file: 'textlab/ml/kmeans.py', kind: 'v', share: 0.028, calls: 480000, speedup: 31.4, elems: 8,
    src: `def dist2(p: list[float], q: list[float]) -> float:
    total = 0.0
    for i in range(len(p)):
        d = p[i] - q[i]
        total += d * d
    return total`,
  },
  {
    file: 'textlab/ml/kmeans.py', kind: 'v', share: 0.142, calls: 60, speedup: 42.7, elems: 8000,
    src: `def assign_clusters(points: list[list[float]], cents: list[list[float]]) -> list[int]:
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
    return labels`,
  },
  {
    file: 'textlab/ml/kmeans.py', kind: 'v', share: 0.047, calls: 60, speedup: 27.9, elems: 8000,
    src: `def update_centroids(points: list[list[float]], labels: list[int], k: int) -> list[list[float]]:
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
    return sums`,
  },
  {
    file: 'textlab/ml/kmeans.py', kind: 'v', share: 0.009, calls: 60, speedup: 36.8, elems: 8000,
    src: `def inertia(points: list[list[float]], cents: list[list[float]], labels: list[int]) -> float:
    total = 0.0
    for i in range(len(points)):
        total += dist2(points[i], cents[labels[i]])
    return total`,
  },
  {
    file: 'textlab/ml/kmeans.py', kind: 'g', share: 0.001, calls: 1, speedup: 6.2, elems: 8000,
    src: `def init_centroids(points: list[list[float]], k: int, seed: int) -> list[list[float]]:
    state = seed
    chosen: list[list[float]] = []
    for c in range(k):
        state = (state * 1103515245 + 12345) % 2147483648
        chosen.append(points[state % len(points)])
    return chosen`,
  },
  // ---------------- sim/nbody.py ----------------
  {
    file: 'textlab/sim/nbody.py', kind: 'v', share: 0.171, calls: 300, speedup: 54.0, elems: 96,
    src: `def step(pos: list[float], vel: list[float], mass: list[float], dt: float) -> None:
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
        pos[i] += vel[i] * dt`,
  },
  {
    file: 'textlab/sim/nbody.py', kind: 'v', share: 0.014, calls: 30, speedup: 40.2, elems: 96,
    src: `def energy(pos: list[float], vel: list[float], mass: list[float]) -> float:
    n = len(mass)
    e = 0.0
    for i in range(n):
        v2 = vel[3 * i] * vel[3 * i] + vel[3 * i + 1] * vel[3 * i + 1] + vel[3 * i + 2] * vel[3 * i + 2]
        e += 0.5 * mass[i] * v2
    return e`,
  },
  {
    file: 'textlab/sim/nbody.py', kind: 'v', share: 0.002, calls: 30, speedup: 15.3, elems: 96,
    src: `def center_of_mass(pos: list[float], mass: list[float]) -> list[float]:
    total = 0.0
    c = [0.0, 0.0, 0.0]
    for i in range(len(mass)):
        total += mass[i]
        for k in range(3):
            c[k] += pos[3 * i + k] * mass[i]
    for k in range(3):
        c[k] = c[k] / total
    return c`,
  },
  {
    file: 'textlab/sim/nbody.py', kind: 'n', share: 0.001, calls: 8,
    reason: 'Method of class Body: v1 only compiles module-level functions.',
    src: `def kinetic(self):
        return 0.5 * self.mass * (self.vx ** 2 + self.vy ** 2 + self.vz ** 2)`,
  },
  // ---------------- data/loader.py ----------------
  {
    file: 'textlab/data/loader.py', kind: 'n', share: 0.018, calls: 1,
    reason: 'Performs file I/O (open, read): outside PySub.',
    src: `def read_corpus(path):
    with open(path) as fh:
        return [line.strip() for line in fh if line.strip()]`,
  },
  {
    file: 'textlab/data/loader.py', kind: 'a', share: 0.005, calls: 4100, speedup: 8.7, elems: 80,
    src: `def parse_line(line):
    parts = line.split(",")
    return [p.strip() for p in parts]`,
    annotated: `def parse_line(line: str) -> list[str]:
    parts = line.split(",")
    return [p.strip() for p in parts]`,
    reason: 'List comprehension with method call: left as Python.',
  },
  {
    file: 'textlab/data/loader.py', kind: 'n', share: 0.001, calls: 1,
    reason: 'Imports json and reads a file.',
    src: `def load_labels(path):
    with open(path) as fh:
        return json.load(fh)`,
  },
  // ---------------- utils/mathx.py ----------------
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.003, calls: 120000, speedup: 14.1, elems: 1, src: `def clamp(x: int, lo: int, hi: int) -> int:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.002, calls: 9000, speedup: 17.2, elems: 1, src: `def gcd(a: int, b: int) -> int:
    while b != 0:
        t = a % b
        a = b
        b = t
    return a` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.002, calls: 2000, speedup: 22.4, elems: 1, src: `def collatz_steps(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 7000, speedup: 10.8, elems: 1, src: `def digit_sum(n: int) -> int:
    total = 0
    while n > 0:
        total += n % 10
        n = n // 10
    return total` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 7000, speedup: 11.9, elems: 1, src: `def popcount(n: int) -> int:
    count = 0
    while n > 0:
        count += n & 1
        n = n >> 1
    return count` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 400, speedup: 25.5, elems: 1, src: `def fib(n: int) -> int:
    a = 0
    b = 1
    for i in range(n):
        t = a + b
        a = b
        b = t
    return a` },
  { file: 'textlab/utils/mathx.py', kind: 'g', share: 0.001, calls: 300, speedup: 19.0, elems: 1, src: `def power_mod(base: int, exp: int, mod: int) -> int:
    result = 1
    base = base % mod
    while exp > 0:
        if exp % 2 == 1:
            result = result * base % mod
        exp = exp // 2
        base = base * base % mod
    return result` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 500, speedup: 13.3, elems: 1, src: `def isqrt(n: int) -> int:
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
    return lo` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.002, calls: 1800, speedup: 20.7, elems: 240, src: `def mean(xs: list[float]) -> float:
    if len(xs) == 0:
        return 0.0
    total = 0.0
    for x in xs:
        total += x
    return total / len(xs)` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.002, calls: 1800, speedup: 19.8, elems: 240, src: `def variance(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    m = mean(xs)
    acc = 0.0
    for x in xs:
        acc += (x - m) * (x - m)
    return acc / n` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 15000, speedup: 8.9, elems: 1, src: `def abs_diff(a: int, b: int) -> int:
    if a > b:
        return a - b
    return b - a` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 15000, speedup: 8.1, elems: 1, src: `def sign(x: float) -> int:
    if x > 0.0:
        return 1
    if x < 0.0:
        return -1
    return 0` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 3000, speedup: 9.9, elems: 1, src: `def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t` },
  { file: 'textlab/utils/mathx.py', kind: 'v', share: 0.001, calls: 800, speedup: 16.5, elems: 1, src: `def is_even(n: int) -> bool:
    return n % 2 == 0` },
  {
    file: 'textlab/utils/mathx.py', kind: 'f', share: 0.004, calls: 3600, elems: 1,
    mismatch: { args: '(2.5,)', python: '2', cpp: '3', kind: 'value' },
    src: `def round_half_even(x: float) -> int:
    return int(round(x))`,
    reason: 'Replay mismatch: Python round() is round-half-to-even; the generated C++ rounds half away from zero. First counterexample: round_half_even(2.5) -> Python 2, C++ 3.',
  },
  {
    file: 'textlab/utils/mathx.py', kind: 'fx', share: 0.002, calls: 120,
    reason: 'Fixable (sorted() is outside PySub), but only 0.2% of runtime: below the rewrite threshold.',
    src: `def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2`,
  },
  // ---------------- utils/cache.py ----------------
  {
    file: 'textlab/utils/cache.py', kind: 'n', share: 0.003, calls: 12,
    reason: 'Defines a closure: inner function `wrapper` captures `cache` from the enclosing scope.',
    src: `def memoize(fn):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    return wrapper`,
  },
  {
    file: 'textlab/utils/cache.py', kind: 'n', share: 0.001, calls: 40,
    reason: 'Nested function and dynamic typing (returns a callable).',
    src: `def timed(label):
    def deco(fn):
        def inner(*a, **k):
            t0 = time.perf_counter()
            r = fn(*a, **k)
            print(label, time.perf_counter() - t0)
            return r
        return inner
    return deco`,
  },
  // ---------------- report.py / main.py ----------------
  {
    file: 'textlab/report.py', kind: 'n', share: 0.002, calls: 1,
    reason: 'Uses f-strings and str.join over a generator.',
    src: `def format_table(rows):
    width = max(len(r[0]) for r in rows)
    return "\\n".join(f"{name:<{width}}  {val:8.2f}" for name, val in rows)`,
  },
  {
    file: 'textlab/report.py', kind: 'n', share: 0.001, calls: 1,
    reason: 'Calls statistics.mean/stdev: module `statistics` is not available in PySub.',
    src: `def summarize(values):
    return statistics.mean(values), statistics.stdev(values)`,
  },
  {
    file: 'textlab/main.py', kind: 'n', share: 0.004, calls: 1,
    reason: 'Calls argparse.ArgumentParser: module `argparse` is not part of PySub.',
    src: `def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true")
    return ap.parse_args()`,
  },
  {
    file: 'textlab/main.py', kind: 'n', share: 0.012, calls: 1,
    reason: 'Orchestrates other modules, prints, and reads files (I/O and calls into non-PySub code).',
    src: `def run_pipeline(small):
    corpus = read_corpus("data/corpus.txt")
    words = [w for line in corpus for w in split_words(normalize(line))]
    keep = fuzzy_dedupe(words[: 600 if small else 4000], 2)
    print("kept", len(keep), "of", len(words))
    return keep`,
  },
  {
    file: 'textlab/main.py', kind: 'n', share: 0.003, calls: 1,
    reason: 'Entry point: prints, times execution with time.perf_counter, calls argparse.',
    src: `def main():
    args = parse_args()
    t0 = time.perf_counter()
    run_pipeline(args.small)
    print("done in", round(time.perf_counter() - t0, 2), "s")`,
  },
]
