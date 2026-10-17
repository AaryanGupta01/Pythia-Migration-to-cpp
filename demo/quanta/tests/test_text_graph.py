"""Text, graph and sparse-structure code."""
import unittest

from quanta.graph.shortest import NO_EDGE, dijkstra_dense, eccentricity_sum, floyd_warshall
from quanta.graph.sparse import Graph, random_graph
from quanta.graph.traverse import bfs_levels, reachable_count
from quanta.text.corpus import make_dictionary, make_dna, misspell
from quanta.text.distance import hamming, lcs_length, levenshtein
from quanta.text.index import InvertedIndex, tokenize
from quanta.text.kmers import gc_content, kmer_counts, longest_run
from quanta.text.spell import SpellChecker
from quanta.util.rng import Lcg


def codes(text):
    return [ord(c) for c in text]


class Distances(unittest.TestCase):
    def test_levenshtein(self):
        self.assertEqual(levenshtein(codes("kitten"), codes("sitting")), 3)
        self.assertEqual(levenshtein([], codes("abc")), 3)
        self.assertEqual(levenshtein(codes("same"), codes("same")), 0)

    def test_lcs_and_hamming(self):
        self.assertEqual(lcs_length(codes("AGGTAB"), codes("GXTXAYB")), 4)
        self.assertEqual(hamming("karolin", "kathrin"), 3)
        self.assertEqual(hamming("ab", "abcd"), 2)

    def test_spell_checker_finds_nearest_word(self):
        checker = SpellChecker(["apple", "maple", "orange"])
        self.assertEqual(checker.suggest("appel"), "apple")
        self.assertEqual(checker.suggest("zzzzzzzz"), "zzzzzzzz")

    def test_misspell_stays_close(self):
        rng = Lcg(3)
        words = make_dictionary(rng, 30)
        for word in words:
            self.assertLessEqual(levenshtein(codes(word), codes(misspell(rng, word))), 6)


class Kmers(unittest.TestCase):
    def test_kmer_counts(self):
        self.assertEqual(kmer_counts("ACGACG", 3), {"ACG": 2, "CGA": 1, "GAC": 1})
        self.assertEqual(kmer_counts("AC", 3), {})

    def test_gc_and_runs(self):
        self.assertEqual(gc_content("GGCC"), 1.0)
        self.assertEqual(gc_content(""), 0.0)
        self.assertEqual(longest_run("AAACCGGGGT"), 4)

    def test_dna_alphabet(self):
        self.assertEqual(set(make_dna(Lcg(1), 500)), set("ACGT"))


class Index(unittest.TestCase):
    def test_tokenize_drops_stop_words(self):
        self.assertEqual(tokenize("The cat and a Hat"), ["cat", "hat"])

    def test_search_ranks_matching_documents_first(self):
        idx = InvertedIndex()
        idx.add("red apples and green apples")
        idx.add("blue boats")
        idx.add("apples")
        self.assertEqual(idx.search("apples", 3), [0, 2])
        self.assertEqual(idx.search("nothing"), [])


class DenseGraphs(unittest.TestCase):
    def matrix(self):
        n = NO_EDGE
        return [[0, 4, n, 1], [4, 0, 2, n], [n, 2, 0, 5], [1, n, 5, 0]]

    def test_floyd_warshall(self):
        d = floyd_warshall(self.matrix())
        self.assertEqual(d[0], [0, 4, 6, 1])
        self.assertEqual(d[3][2], 5)

    def test_dijkstra_matches_floyd_warshall(self):
        m = self.matrix()
        d = floyd_warshall(m)
        for s in range(4):
            self.assertEqual(dijkstra_dense(m, s), d[s])

    def test_eccentricity_sum(self):
        self.assertEqual(eccentricity_sum(self.matrix()), 6 + 5 + 6 + 5)

    def test_input_matrix_is_not_modified(self):
        m = self.matrix()
        snapshot = [row[:] for row in m]
        floyd_warshall(m)
        self.assertEqual(m, snapshot)


class SparseGraphs(unittest.TestCase):
    def test_random_graph_is_connected_and_consistent(self):
        g = random_graph(Lcg(5), 80, 2)
        self.assertEqual(len(g.components()), 1)
        m = g.to_matrix(NO_EDGE)
        dist = g.shortest_paths(0)
        self.assertEqual([dist[v] for v in range(80)], dijkstra_dense(m, 0))

    def test_bfs_levels(self):
        adjacency = [[1], [0, 2], [1], []]
        self.assertEqual(bfs_levels(adjacency, 0), [0, 1, 2, -1])
        self.assertEqual(reachable_count(adjacency, 3), 1)

    def test_lighter_parallel_edge_wins(self):
        g = Graph(2)
        g.add_edge(0, 1, 9)
        g.add_edge(0, 1, 4)
        g.add_edge(1, 0, 7)
        self.assertEqual(g.adj[0][1], 4)
        self.assertEqual(g.edge_count, 1)


class Generator(unittest.TestCase):
    def test_lcg_is_deterministic(self):
        a, b = Lcg(42), Lcg(42)
        self.assertEqual([a.next_int(100) for _ in range(8)], [b.next_int(100) for _ in range(8)])
        self.assertEqual(Lcg(1).next_int(1000), 838)

    def test_shuffle_is_a_permutation(self):
        items = list(range(30))
        Lcg(9).shuffle(items)
        self.assertEqual(sorted(items), list(range(30)))
        self.assertNotEqual(items, list(range(30)))


if __name__ == "__main__":
    unittest.main()
