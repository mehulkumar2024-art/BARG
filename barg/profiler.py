from collections import Counter, deque
from math import log2, sqrt
from statistics import mean, pstdev


class EWMA:
    def __init__(self, alpha=.3):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha, self.value = alpha, None

    def update(self, observation):
        previous = self.value
        self.value = observation if previous is None else self.alpha * observation + (1-self.alpha) * previous
        return previous, self.value


class Ngrams:
    def __init__(self, size=2048):
        self.sequence = deque(maxlen=size)

    def update(self, values):
        self.sequence.extend(values)

    def distribution(self, n):
        seq = list(self.sequence)
        counts = Counter(tuple(seq[i:i+n]) for i in range(len(seq)-n+1))
        total = sum(counts.values())
        return {k: v/total for k, v in counts.items()} if total else {}


def divergence(p, q):
    """Jensen-Shannon divergence, base two: bounded [0, 1]."""
    if not p or not q:
        return 0.0
    result = 0.0
    for k in p.keys() | q.keys():
        a, b = p.get(k, 0), q.get(k, 0)
        m = (a+b)/2
        result += .5 * ((a*log2(a/m) if a else 0) + (b*log2(b/m) if b else 0))
    return max(0., min(1., result))


def zscore(value, values):
    if len(values) < 2:
        return 0.
    return abs(value-mean(values))/max(pstdev(values), abs(mean(values))*.1, .01)


def fairness(values):
    return sum(values)**2/(len(values)*sum(v*v for v in values)) if values and any(values) else 1.


class Profile:
    def __init__(self, settings):
        self.ewma = EWMA(settings.alpha)
        self.ngrams = Ngrams()
        self.baseline = {}
        self.features = {k: [] for k in ("burst_ms", "faults", "io_bytes")}
        self.windows = 0
        self.state = "NORMAL"
        self.high = self.low = 0
        self.history = deque(maxlen=120)

    def update(self, sample, settings):
        self.windows += 1
        self.ewma.alpha = settings.alpha
        prediction, estimate = self.ewma.update(sample.burst_ms)
        self.ngrams.update(sample.syscalls)
        training = self.windows <= settings.training_windows
        current = {n: self.ngrams.distribution(n) for n in (1, 2, 3)}
        components = {k: min(1., zscore(getattr(sample, k), v)/6) for k, v in self.features.items()}
        components["syscalls"] = sum(divergence(current[n], self.baseline.get(n, {})) for n in (1,2,3))/3
        score = .25*components["burst_ms"]+.2*components["faults"]+.15*components["io_bytes"]+.4*components["syscalls"]
        if training:
            for k, v in self.features.items():
                v.append(getattr(sample, k))
            self.baseline = current
            score = 0.
        else:
            self.high = self.high+1 if score >= settings.threshold else 0
            self.low = self.low+1 if score < settings.threshold*.6 else 0
            if self.high >= 3:
                self.state = "ANOMALOUS"
            elif self.state == "ANOMALOUS" and self.low >= 3:
                self.state = "RECOVERING"
            elif self.low >= 6:
                self.state = "NORMAL"
            elif self.state in ("NORMAL", "WARNING"):
                self.state = "WARNING" if score >= settings.threshold else "NORMAL"
        row = {**sample.model_dump(exclude={"syscalls"}), "score": score, "components": components,
               "status": self.state, "training": training, "confidence": min(1., self.windows/settings.training_windows),
               "prediction": prediction, "ewma": estimate, "classification": "CPU-bound" if estimate > 4 else "latency-sensitive",
               "distribution": {str(k[0]):v for k,v in current[1].items()},
               "unseen_trigrams": sum(v for k,v in current[3].items() if k not in self.baseline.get(3, {}))}
        self.history.append(row)
        return row
