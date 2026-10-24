"""textlab -- a small, dependency-free text + numerics workbench (the PYTHIA Studio demo project).

    python main.py --small     # ~10-20 s under CPython 3.14
    python main.py             # ~4x the work

Stages (all deterministic: hand-written LCG, no clock or network in the output):
    text      fuzzy de-duplication (edit distance), BPE training (pair counts), corpus file I/O
    sim       n-body energy, Monte-Carlo pi, Game of Life
    ml        k-means, k-NN vote, row normalisation, learning-rate schedule
    features  prime checksum, Collatz stopping times, sliding-window signal energy

Where PYTHIA can help (see DEMO.md): edit_distance, simulate_energy, prime_square_sum,
assign_clusters, count_pairs, monte_carlo_pi compile as written; knn_vote, life_generations and
collatz_longest need a rewrite or annotations; numpy/closure/file I/O/class code stays Python;
window_energy compiles but is called too often on a huge list, so the ranker declines it.
"""
import argparse

from textlab.features.collatz import collatz_longest
from textlab.features.primes import prime_square_sum
from textlab.ml.embed import normalize_rows
from textlab.ml.kmeans import KMeans
from textlab.ml.knn import knn_vote
from textlab.ml.schedule import make_lr_schedule
from textlab.signal.window import energy_profile
from textlab.sim.life import life_generations
from textlab.sim.montecarlo import monte_carlo_pi
from textlab.sim.nbody import simulate_energy
from textlab.text.bpe import count_pairs
from textlab.text.corpus import CorpusBuilder, load_corpus, write_corpus
from textlab.text.distance import edit_distance
from textlab.text.vocab import Vocab
from textlab.util.parse import parse_number, summarize
from textlab.util.rng import Rng
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


def fuzzy_dedup(words, threshold):
    reps = []
    for w in sorted(set(words)):
        for r in reps:
            if abs(len(r) - len(w)) <= threshold and edit_distance(w, r) <= threshold:
                break
        else:
            reps.append(w)
    return reps


def stage_text(scale):
    rng = Rng(7)
    words = load_corpus(write_corpus(CorpusBuilder(rng).make_words(40, 5500 * scale)))
    reps = fuzzy_dedup(words, 4)
    print("text: %d words, %d clusters after fuzzy dedup" % (len(words), len(reps)))
    ids = [ord(ch) - 97 if ch != " " else 26 for ch in " ".join(words)]
    vocab = Vocab(27)
    ids = vocab.train(ids, 55 + 10 * scale)
    pairs = [c for c in count_pairs(ids, 128) if c]
    print("bpe: vocab %d, %d tokens, %d distinct pairs" % (vocab.size, len(ids), len(pairs)))
    meta = [parse_number(t) for t in ("12", "7", "", "40") * (50 * scale)]
    print("meta: %.2f" % summarize(*[m for m in meta if not isinstance(m, str)]))


@_pythia_accelerated("pythia_d474163c", "stage_sim")
def stage_sim(scale):
    rng = Rng(11)
    n = 100
    cloud = [[rng.next_float() for _ in range(n)] for _ in range(5)]
    mass = [0.5 + m for m in cloud[4]]
    energy = simulate_energy(cloud[0], cloud[1], cloud[2], cloud[3], mass, 1000 * scale, 0.01)
    print("nbody: kinetic energy %.6f" % energy)
    print("pi ~ %.5f" % monte_carlo_pi(6500000 * scale, 12345))
    grid = [[1 if rng.next_int(100) < 30 else 0 for _ in range(80)] for _ in range(80)]
    print("life: %d live cells after %d generations" % (life_generations(grid, 200 * scale), 200 * scale))


def stage_ml(scale):
    rng = Rng(3)
    centers = [[rng.next_float() * 10 for _ in range(4)] for _ in range(6)]
    points = []
    labels = []
    for i in range(3000):
        c = i % 6
        points.append([centers[c][k] + rng.next_float() - 0.5 for k in range(4)])
        labels.append(c)
    start = [points[i * 7][:] for i in range(16)]
    model = KMeans(start)
    assign = model.fit(points, 80 * scale)
    print("kmeans: sizes %s" % [assign.count(c) for c in range(16)])
    train, tl = points[:900], labels[:900]
    votes = [knn_vote(train, tl, points[900 + q], 5) for q in range(900 * scale)]
    print("knn: accuracy %.3f" % (sum(v == labels[900 + q] for q, v in enumerate(votes)) / len(votes)))
    unit = normalize_rows(model.centroids)
    print("embed: checksum %.4f" % sum(sum(abs(v) for v in row) for row in unit))
    lr = make_lr_schedule(0.5, 0.1)
    print("lr after 100 steps: %.4f" % lr(100))


def stage_features(scale):
    print("primes: %d" % prime_square_sum(300000 * scale, 1000003))
    print("collatz: %d" % collatz_longest(150000 * scale))
    rng = Rng(5)
    signal = [rng.next_float() - 0.5 for _ in range(5000)]
    peak = 0.0
    for _ in range(35 * scale):
        peak = max(peak, max(energy_profile(signal, 128)))
    print("signal: peak window energy %.4f" % peak)


def main():
    ap = argparse.ArgumentParser(description="textlab demo workload")
    ap.add_argument("--small", action="store_true", help="quick run (about a quarter of the work)")
    scale = 1 if ap.parse_args().small else 4
    stage_text(scale)
    stage_sim(scale)
    stage_ml(scale)
    stage_features(scale)
    print("done")


if __name__ == "__main__":
    main()
