"""Numerical kernels: known answers and basic invariants."""
import unittest

from quanta.cluster.kernels import assign_points, inertia, update_centroids
from quanta.combinatorics.permutations import count_derangements, fannkuch, next_permutation
from quanta.combinatorics.queens import count_queens
from quanta.graph.closure import count_triangles, degree_histogram, transitive_closure
from quanta.linalg.decomp import determinant, power_iteration
from quanta.linalg.dense import gauss_solve, matmul, transpose
from quanta.numtheory.totient import count_coprime_pairs, perfect_numbers, totient_sieve, totient_sum
from quanta.opt.chain import matrix_chain_cost, max_subarray, partition_count, rod_cutting
from quanta.signal.spectrum import cos_series, dft_power, dominant_bin, median_filter, sin_series
from quanta.sim.automata import density, rule_automaton
from quanta.stats.correlation import kendall_tau, rank_transform, spearman_rho
from quanta.text.substrings import longest_common_substring, longest_palindrome, run_length_encode
from quanta.linalg.spectral import spectral_norm
from quanta.numtheory.collatz import collatz_steps, longest_collatz, peak_value
from quanta.numtheory.digits import count_palindromes, digit_sum, digital_root_total
from quanta.numtheory.primes import (is_probable_prime, prime_gap_record, prime_square_sum, sieve_primes,
                                     twin_prime_count)
from quanta.opt.anneal import acceptance_probability
from quanta.opt.dp import coin_ways, grid_min_path, knapsack_01, longest_increasing_subsequence
from quanta.opt.routes import tour_length
from quanta.signal.filters import convolve, exp_smooth, fir_filter, hann_taps, moving_average
from quanta.sim.fractal import escape_area, mandelbrot_row
from quanta.sim.life import life_population, life_step
from quanta.sim.montecarlo import estimate_pi, integrate_poly, walk_endpoints
from quanta.sim.nbody import advance, total_energy
from quanta.sim.system import System
from quanta.stats.descriptive import autocorrelation, clip_fraction, histogram, rolling_std, weighted_moments
from quanta.stats.drift import tail_variance


class Combinatorics(unittest.TestCase):
    def test_fannkuch_known_values(self):
        self.assertEqual(fannkuch(5), 7)
        self.assertEqual(fannkuch(7), 16)

    def test_queens_solution_counts(self):
        self.assertEqual([count_queens(n) for n in range(4, 9)], [2, 10, 4, 40, 92])

    def test_derangements(self):
        self.assertEqual([count_derangements(n) for n in range(1, 7)], [0, 1, 2, 9, 44, 265])

    def test_next_permutation_walks_all_orderings(self):
        items = [0, 1, 2, 3]
        seen = 1
        while next_permutation(items):
            seen += 1
        self.assertEqual(seen, 24)
        self.assertEqual(items, [3, 2, 1, 0])


class NumberTheory(unittest.TestCase):
    def test_sieve(self):
        self.assertEqual(sieve_primes(30), [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])
        self.assertEqual(len(sieve_primes(10000)), 1229)

    def test_twin_primes_and_gaps(self):
        self.assertEqual(twin_prime_count(100), 8)
        self.assertEqual(prime_gap_record(100), 8)

    def test_trial_division_agrees_with_sieve(self):
        primes = set(sieve_primes(500))
        self.assertTrue(all(is_probable_prime(n) == (n in primes) for n in range(500)))

    def test_prime_square_sum(self):
        self.assertEqual(prime_square_sum(4, 1000), 2 * 2 + 3 * 3 + 5 * 5 + 7 * 7)

    def test_collatz(self):
        self.assertEqual(collatz_steps(27), 111)
        self.assertEqual(longest_collatz(30), 27)
        self.assertEqual(peak_value(27), 9232)

    def test_digit_puzzles(self):
        self.assertEqual(digit_sum(98765), 35)
        self.assertEqual(digital_root_total(20), sum(1 + (n - 1) % 9 for n in range(1, 20)))
        self.assertEqual(count_palindromes(200), 28)


class LinearAlgebra(unittest.TestCase):
    def test_matmul_identity_and_transpose(self):
        a = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        eye = [[1.0, 0.0], [0.0, 1.0]]
        self.assertEqual(matmul(a, eye), a)
        self.assertEqual(transpose(a), [[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]])

    def test_gauss_solve(self):
        a = [[2.0, 1.0], [1.0, 3.0]]
        x = gauss_solve(a, [3.0, 5.0])
        self.assertAlmostEqual(x[0], 0.8)
        self.assertAlmostEqual(x[1], 1.4)

    def test_singular_matrix_raises(self):
        with self.assertRaises(ValueError):
            gauss_solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])

    def test_spectral_norm_converges(self):
        self.assertAlmostEqual(spectral_norm(100, 10), 1.274219991, places=6)


class Simulation(unittest.TestCase):
    def test_nbody_conserves_energy(self):
        s = System.outer_planets()
        e0 = s.energy()
        s.advance(0.01, 2000)
        self.assertAlmostEqual(s.energy(), e0, places=5)
        self.assertEqual(total_energy(s.x, s.y, s.z, s.vx, s.vy, s.vz, s.mass), s.energy())

    def test_advance_moves_bodies_in_place(self):
        s = System.outer_planets()
        before = list(s.x)
        advance(s.x, s.y, s.z, s.vx, s.vy, s.vz, s.mass, 0.01, 10)
        self.assertNotEqual(before, s.x)

    def test_mandelbrot_row_through_the_origin(self):
        row = mandelbrot_row(60, 120, 120, 50)
        self.assertEqual(len(row), 120)
        self.assertEqual(max(row), 50)
        self.assertEqual(row[0], 1)
        self.assertGreater(escape_area(40, 30, 40), 0)

    def test_monte_carlo(self):
        self.assertAlmostEqual(estimate_pi(20000, 7), 3.14, delta=0.1)
        self.assertAlmostEqual(integrate_poly([0.0, 0.0, 3.0], 0.0, 1.0, 20000, 3), 1.0, delta=0.05)
        ends = walk_endpoints(50, 10, 5)
        self.assertEqual(len(ends), 50)
        self.assertTrue(all(abs(e) <= 10 and e % 2 == 0 for e in ends))

    def test_life_blinker(self):
        grid = [[0, 0, 0], [1, 1, 1], [0, 0, 0]]
        self.assertEqual(life_step(grid), [[0, 1, 0], [0, 1, 0], [0, 1, 0]])
        self.assertEqual(life_population(grid, 5), 3)


class Optimisation(unittest.TestCase):
    def test_knapsack(self):
        self.assertEqual(knapsack_01([1, 3, 4, 5], [1, 4, 5, 7], 7), 9)

    def test_coin_ways(self):
        self.assertEqual(coin_ways([1, 2, 5], 11), 11)

    def test_increasing_subsequence(self):
        self.assertEqual(longest_increasing_subsequence([10, 9, 2, 5, 3, 7, 101, 18]), 4)
        self.assertEqual(longest_increasing_subsequence([]), 0)

    def test_grid_min_path(self):
        self.assertEqual(grid_min_path([[1, 3, 1], [1, 5, 1], [4, 2, 1]]), 5)

    def test_tour_length_of_a_square(self):
        self.assertAlmostEqual(tour_length([0.0, 1.0, 1.0, 0.0], [0.0, 0.0, 1.0, 1.0], [0, 1, 2, 3]), 4.0)

    def test_acceptance_probability(self):
        self.assertAlmostEqual(acceptance_probability(0.0, 1.0), 1.0)
        self.assertAlmostEqual(acceptance_probability(1.0, 1.0), 0.3678794, places=5)
        self.assertEqual(acceptance_probability(100.0, 1.0), 0.0)

    def test_kmeans_kernels(self):
        pts = [[0.0, 0.0], [0.2, 0.0], [5.0, 5.0], [5.2, 5.0]]
        cents = [[0.0, 0.0], [5.0, 5.0]]
        labels = assign_points(pts, cents)
        self.assertEqual(labels, [0, 0, 1, 1])
        moved = update_centroids(pts, labels, cents)
        self.assertEqual(moved, [[0.1, 0.0], [5.1, 5.0]])
        self.assertAlmostEqual(inertia(pts, labels, moved), 4 * 0.01, places=9)


class Signals(unittest.TestCase):
    def test_fir_with_identity_tap(self):
        self.assertEqual(fir_filter([1.0, 2.0, 3.0], [1.0]), [1.0, 2.0, 3.0])
        self.assertEqual(fir_filter([1.0, 2.0, 3.0], [0.5, 0.5]), [0.5, 1.5, 2.5])

    def test_convolution(self):
        self.assertEqual(convolve([1.0, 2.0, 3.0], [0.0, 1.0, 0.5]), [0.0, 1.0, 2.5, 4.0, 1.5])

    def test_smoothers(self):
        self.assertAlmostEqual(sum(hann_taps(9)), 1.0)
        self.assertEqual(moving_average([2.0, 4.0, 6.0, 8.0], 2), [2.0, 3.0, 5.0, 7.0])
        self.assertEqual(exp_smooth([1.0, 3.0, 5.0], 0.5), [1.0, 2.0, 3.5])
        self.assertEqual(exp_smooth([], 0.5), [])


class MoreKernels(unittest.TestCase):
    def test_totient(self):
        self.assertEqual(totient_sieve(10), [0, 1, 1, 2, 2, 4, 2, 6, 4, 6, 4])
        self.assertEqual(totient_sum(10), 32)
        self.assertEqual(count_coprime_pairs(6), 11)
        self.assertEqual(perfect_numbers(500), [6, 28, 496])

    def test_spectrum(self):
        self.assertAlmostEqual(sin_series(1.0), 0.8414709848, places=9)
        self.assertAlmostEqual(cos_series(7.0), 0.7539022543, places=9)
        wave = [sin_series(2 * 3.141592653589793 * 5 * t / 64) for t in range(64)]
        self.assertEqual(dominant_bin(dft_power(wave)), 5)

    def test_median_filter_removes_spike(self):
        self.assertEqual(median_filter([1.0, 1.0, 9.0, 1.0, 1.0], 3), [1.0, 1.0, 1.0, 1.0, 1.0])

    def test_graph_closure_and_triangles(self):
        tri = [[0, 1, 1, 0], [1, 0, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0]]
        self.assertEqual(count_triangles(tri), 1)
        self.assertEqual(degree_histogram(tri), [1, 0, 3, 0, 0])
        chain = [[0, 1, 0], [0, 0, 1], [0, 0, 0]]
        self.assertEqual(transitive_closure(chain), [[1, 1, 1], [0, 1, 1], [0, 0, 1]])

    def test_automaton(self):
        row = [0, 0, 0, 1, 0, 0, 0]
        self.assertEqual(rule_automaton(row, 90, 1), [0, 0, 1, 0, 1, 0, 0])
        self.assertEqual(rule_automaton(row, 204, 5), row)
        self.assertAlmostEqual(density(row), 1 / 7)

    def test_rank_statistics(self):
        self.assertEqual(kendall_tau([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)
        self.assertEqual(kendall_tau([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]), -1.0)
        self.assertEqual(rank_transform([10.0, 20.0, 20.0, 5.0]), [2.0, 3.5, 3.5, 1.0])
        self.assertAlmostEqual(spearman_rho([1.0, 2.0, 3.0, 4.0], [1.0, 4.0, 9.0, 16.0]), 1.0)

    def test_chain_dp(self):
        self.assertEqual(matrix_chain_cost([10, 30, 5, 60]), 4500)
        self.assertEqual(partition_count(10), 42)
        self.assertEqual(rod_cutting([1, 5, 8, 9, 10, 17, 17, 20], 8), 22)
        self.assertEqual(max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]), 6)

    def test_linear_algebra_extras(self):
        self.assertAlmostEqual(determinant([[2.0, 0.0], [0.0, 3.0]]), 6.0)
        self.assertAlmostEqual(determinant([[0.0, 1.0], [1.0, 0.0]]), -1.0)
        self.assertEqual(determinant([[1.0, 2.0], [2.0, 4.0]]), 0.0)
        self.assertAlmostEqual(power_iteration([[2.0, 0.0], [0.0, 1.0]], 30), 2.0, places=6)

    def test_substrings(self):
        self.assertEqual(longest_common_substring("xabcdy", "zabcdw"), 4)
        self.assertEqual(longest_palindrome("forgeeksskeegfor"), 10)
        self.assertEqual(run_length_encode("aaabcc"), "a3b1c2")
        self.assertEqual(run_length_encode(""), "")


class Statistics(unittest.TestCase):
    def test_histogram_ignores_out_of_range(self):
        self.assertEqual(histogram([0.1, 0.4, 0.6, 0.9, 1.0, -1.0], 2, 0.0, 1.0), [2, 2])

    def test_rolling_std_of_constant_series_is_zero(self):
        self.assertEqual(rolling_std([2.0] * 6, 3), [0.0] * 6)

    def test_autocorrelation_of_alternating_series(self):
        self.assertLess(autocorrelation([1.0, -1.0] * 20, 1), -0.9)

    def test_weighted_moments(self):
        mean, var, skew = weighted_moments([1.0, 2.0, 3.0], [1.0, 1.0, 1.0])
        self.assertAlmostEqual(mean, 2.0)
        self.assertAlmostEqual(var, 2.0 / 3.0)
        self.assertAlmostEqual(skew, 0.0)

    def test_clip_fraction(self):
        self.assertEqual(clip_fraction([0.0, 2.0, -2.0, 0.5], -1.0, 1.0), 0.5)
        self.assertEqual(clip_fraction([], -1.0, 1.0), 0.0)

    def test_tail_variance(self):
        self.assertAlmostEqual(tail_variance([100.0, 1.0, 3.0], 2), 1.0)


if __name__ == "__main__":
    unittest.main()
