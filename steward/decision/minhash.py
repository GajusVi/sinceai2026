import hashlib
import random
import struct
from typing import List, Set


class MinHashCalculator:
    """
    MinHash signature calculator for document similarity.

    Uses deterministic hash functions for reproducibility.
    """

    def __init__(self, num_permutations: int = 128, shingle_size: int = 5, seed: int = 42):
        self.num_permutations = num_permutations
        self.shingle_size = shingle_size
        self.seed = seed

        self.prime = 2**31 - 1
        self.max_hash = 2**32 - 1
        self._init_hash_functions()

    def _init_hash_functions(self) -> None:
        rng = random.Random(self.seed)
        self.hash_params = [(rng.randint(1, self.prime - 1), rng.randint(0, self.prime - 1)) for _ in range(self.num_permutations)]

    def _generate_shingles(self, text: str) -> Set[str]:
        words = text.lower().split()
        if len(words) < self.shingle_size:
            return {" ".join(words)} if words else set()

        return {" ".join(words[i : i + self.shingle_size]) for i in range(len(words) - self.shingle_size + 1)}

    def _hash_shingle(self, shingle: str) -> int:
        hash_bytes = hashlib.sha256(shingle.encode("utf-8")).digest()
        return struct.unpack("<I", hash_bytes[:4])[0]

    def compute_signature(self, text: str) -> List[int]:
        shingles = self._generate_shingles(text)
        if not shingles:
            return [self.max_hash] * self.num_permutations

        signature = [self.max_hash] * self.num_permutations
        for shingle in shingles:
            shingle_hash = self._hash_shingle(shingle)
            for i, (a, b) in enumerate(self.hash_params):
                perm_hash = (a * shingle_hash + b) % self.prime
                if perm_hash < signature[i]:
                    signature[i] = perm_hash

        return signature

    def estimate_jaccard(self, sig1: List[int], sig2: List[int]) -> float:
        if len(sig1) != len(sig2) or len(sig1) == 0:
            return 0.0
        matches = sum(1 for i in range(len(sig1)) if sig1[i] == sig2[i])
        return matches / len(sig1)
