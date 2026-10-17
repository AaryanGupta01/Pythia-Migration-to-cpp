"""Synthetic English-like text and DNA-like sequences for the text jobs."""
from __future__ import annotations

from typing import List

from quanta.util.rng import Lcg

ONSETS = ["b", "br", "c", "ch", "d", "f", "fl", "g", "gr", "h", "j", "k", "l", "m", "n", "p", "pr", "r", "s", "st",
          "t", "tr", "v", "w"]
VOWELS = ["a", "e", "i", "o", "u", "ai", "ea", "io", "ou"]
CODAS = ["", "", "n", "r", "s", "t", "nd", "st", "ng", "rd"]


def make_word(rng: Lcg, syllables: int) -> str:
    """One pronounceable pseudo-word of `syllables` syllables."""
    parts = []
    for _ in range(syllables):
        parts.append(rng.choice(ONSETS) + rng.choice(VOWELS) + rng.choice(CODAS))
    return "".join(parts)


def make_dictionary(rng: Lcg, size: int) -> List[str]:
    """`size` distinct pseudo-words, sorted."""
    words = set()
    while len(words) < size:
        words.add(make_word(rng, 2 + rng.next_int(2)))
    return sorted(words)


def misspell(rng: Lcg, word: str) -> str:
    """Apply one to three random edits (drop, double, swap or replace a letter) to `word`."""
    chars = list(word)
    for _ in range(1 + rng.next_int(3)):
        if len(chars) < 3:
            break
        pos = rng.next_int(len(chars) - 1)
        kind = rng.next_int(4)
        if kind == 0:
            del chars[pos]
        elif kind == 1:
            chars.insert(pos, chars[pos])
        elif kind == 2:
            chars[pos], chars[pos + 1] = chars[pos + 1], chars[pos]
        else:
            chars[pos] = "abcdefghijklmnopqrstuvwxyz"[rng.next_int(26)]
    return "".join(chars)


def make_document(rng: Lcg, vocabulary: List[str], length: int) -> str:
    """A document of `length` words drawn with a skewed (roughly Zipfian) preference for early entries."""
    words = []
    for _ in range(length):
        skew = rng.next_float() * rng.next_float()
        words.append(vocabulary[int(skew * len(vocabulary))])
    return " ".join(words)


def make_dna(rng: Lcg, length: int) -> str:
    """Random sequence over the alphabet ACGT with a mild GC bias."""
    letters = "AACCGGTTGC"
    return "".join(letters[rng.next_int(len(letters))] for _ in range(length))


def make_lines(rng: Lcg, vocabulary: List[str], count: int, width: int) -> List[str]:
    """`count` lines of roughly `width` characters, as in a source text being diffed."""
    lines = []
    for _ in range(count):
        line = ""
        while len(line) < width:
            line += rng.choice(vocabulary) + " "
        lines.append(line[:width])
    return lines


def edit_line(rng: Lcg, line: str) -> str:
    """A revised version of `line`: a few characters changed, deleted or inserted."""
    chars = list(line)
    for _ in range(3 + rng.next_int(6)):
        pos = rng.next_int(len(chars))
        action = rng.next_int(3)
        if action == 0:
            chars[pos] = "xyzq"[rng.next_int(4)]
        elif action == 1:
            del chars[pos]
        else:
            chars.insert(pos, "e")
    return "".join(chars)
