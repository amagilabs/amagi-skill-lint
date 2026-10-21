"""Score how much two trigger descriptions overlap.

TF-IDF over the description words, cosine similarity per pair. Words that
every skill description uses ("use", "when", "user", "file") are stop words,
so a high score means two descriptions share the specific words that decide
which one Claude picks.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

STOP = set(
    """
    a about above after again against all also am an and any are as at be because been before being below
    between both but by can could did do does doing done down during each either else etc even ever every
    few for from further get gets getting give given go goes going had has have having he her here hers him
    his how however i if in into is it its itself just less like make makes making many may me might more
    most much must my need needs never no nor not now of off often on once one only or other our ours out
    over own per please rather really same say says see seen several shall she should since so some such
    than that the their theirs them then there these they this those through thus to too under until up
    upon us use used uses using very via want wants was way we well were what whatever when whenever where
    whether which while who whom whose why will with within without would yet you your yours
    user users asks ask asked asking request requests requested claude agent agents subagent skill skills
    tool tools task tasks help helps helping work works working thing things something anything everything
    new based specific specialized expert specialist including include includes etc e g eg ie i e
    trigger triggers triggered invoke invoked mention mentions mentioned need needed proactively whenever
    """.split()
)

WORD_RE = re.compile(r"[a-z0-9]+")


def _stem(w: str) -> str:
    for suf in ("ing", "ers", "er", "ies", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def tokens(text: str, surface: Dict[str, str] = None) -> List[str]:
    out = []
    for w in WORD_RE.findall(text.lower()):
        if w in STOP or len(w) < 3 or w.isdigit():
            continue
        stem = _stem(w)
        if surface is not None:
            surface.setdefault(stem, w)
        out.append(stem)
    return out


@dataclass
class Pair:
    a: int
    b: int
    score: float
    shared: List[str]


def similar_pairs(texts: Sequence[str], threshold: float, max_shared: int = 5) -> List[Pair]:
    surface: Dict[str, str] = {}
    docs = [Counter(tokens(t, surface)) for t in texts]
    n = len(docs)
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    idf = {w: math.log((n + 1) / (c + 1)) + 1.0 for w, c in df.items()}
    vecs: List[Dict[str, float]] = []
    norms: List[float] = []
    for d in docs:
        v = {w: (1 + math.log(c)) * idf[w] for w, c in d.items()}
        vecs.append(v)
        norms.append(math.sqrt(sum(x * x for x in v.values())) or 1.0)
    pairs: List[Pair] = []
    for i in range(n):
        for j in range(i + 1, n):
            vi, vj = vecs[i], vecs[j]
            if len(vi) > len(vj):
                small, big = vj, vi
            else:
                small, big = vi, vj
            contrib: List[Tuple[float, str]] = [(small[w] * big[w], w) for w in small if w in big]
            if not contrib:
                continue
            score = sum(c for c, _ in contrib) / (norms[i] * norms[j])
            if score >= threshold:
                contrib.sort(reverse=True)
                pairs.append(Pair(i, j, round(score, 2), [surface.get(w, w) for _, w in contrib[:max_shared]]))
    pairs.sort(key=lambda p: -p.score)
    return pairs
