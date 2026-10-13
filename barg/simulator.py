from collections import deque, defaultdict
import random
import time


def trace(seed=42, length=5000):
    rng = random.Random(seed)
    return [rng.randrange(12) if i % 100 < 85 else rng.randrange(100) for i in range(length)]


def simulate(references, frames=8, policy='LRU', k=2):
    if frames < 1 or k < 1 or policy not in ('FIFO','LRU','LRU-K','BARG'):
        raise ValueError('Invalid simulator configuration')
    resident, fifo, history = set(), deque(), defaultdict(lambda: deque(maxlen=k))
    hits = faults = replacements = 0
    started = time.perf_counter()
    recent = deque(maxlen=32)
    for clock,page in enumerate(references):
        if page in resident:
            hits += 1
        else:
            faults += 1
            if len(resident) == frames:
                if policy == 'FIFO':
                    victim = fifo.popleft()
                elif policy == 'LRU' or (policy == 'BARG' and len(set(recent)) <= frames):
                    victim = min(resident, key=lambda p: (history[p][-1],p))
                else:
                    # Cold pages have infinite backward K-distance; oldest access breaks ties.
                    victim = min(resident, key=lambda p: (len(history[p]) >= k, history[p][0],p))
                resident.remove(victim)
                replacements += 1
            resident.add(page)
            if policy == 'FIFO':
                fifo.append(page)
        history[page].append(clock)
        recent.append(page)
    total = hits+faults
    return {'policy':policy,'source':'synthetic page-reference simulation','frames':frames,'references':total,
            'hits':hits,'faults':faults,'hit_ratio':hits/total if total else 0,'miss_ratio':faults/total if total else 0,
            'replacements':replacements,'execution_ms':(time.perf_counter()-started)*1000}
