import numpy as np
import random
import math
from scipy.ndimage import convolve

class ScarcityAethermorSim:
    def __init__(self,
                 grid_size=60,
                 steps=150,
                 base_harvest=0.8,
                 compute_cost=0.15,
                 reproduction_cost_factor=0.5,
                 energy_threshold=3.5,
                 base_ambient_input=0.3,
                 knowledge_energy_boost=0.1,
                 signal_creation_threshold=2.0,
                 decay_factor=0.015,
                 energy_cap=15.0,
                 signal_cap=8.0,
                 knowledge_cap=5.0,
                 logistic_k_max=10.0,
                 cycle_length=24,
                 sleep_threshold=2.0,
                 wake_threshold=3.0,
                 sleep_cost_factor=0.5,
                 seed=42,
                 visualize=False):
        random.seed(seed)
        np.random.seed(seed)

        self.GRID = grid_size
        self.STEPS = steps
        self.BASE_HARVEST = base_harvest
        self.COMPUTE_COST = compute_cost
        self.REPRODUCTION_COST_FACTOR = reproduction_cost_factor
        self.ENERGY_THRESHOLD = energy_threshold
        self.BASE_AMBIENT_INPUT = base_ambient_input
        self.KNOWLEDGE_ENERGY_BOOST = knowledge_energy_boost
        self.SIGNAL_CREATION_THRESHOLD = signal_creation_threshold
        self.DECAY_FACTOR = decay_factor

        self.ENERGY_CAP = energy_cap
        self.SIGNAL_CAP = signal_cap
        self.KNOWLEDGE_CAP = knowledge_cap
        self.LOGISTIC_K_MAX = logistic_k_max

        self.CYCLE_LENGTH = cycle_length
        self.SLEEP_THRESHOLD = sleep_threshold
        self.WAKE_THRESHOLD = wake_threshold
        self.SLEEP_COST_FACTOR = sleep_cost_factor

        self.energy_field = np.ones((self.GRID, self.GRID)) * 3.0
        self.intel_field  = np.zeros((self.GRID, self.GRID))
        self.signal_field = np.zeros((self.GRID, self.GRID))

        self.nodes = {(self.GRID//2, self.GRID//2): {'energy': 6.0, 'knowledge': 1.5, 'logic': 1, 'awake': True}}

        self._nbrs = [(dx,dy) for dx in (-1,0,1) for dy in (-1,0,1) if not (dx==0 and dy==0)]
        self.laplacian = np.array([[0,1,0],[1,-4,1],[0,1,0]])

        import pandas as pd
        self.metrics = pd.DataFrame(columns=['step','nodes','awake_nodes','harvested','cost','net','avg_energy','total_knowledge'])

    def neighbors(self, x, y):
        for dx, dy in self._nbrs:
            nx, ny = x+dx, y+dy
            if 0 <= nx < self.GRID and 0 <= ny < self.GRID:
                yield (nx, ny)

    def _diffuse_and_decay(self, ambient_input):
        for field, cap in [(self.energy_field, self.ENERGY_CAP),
                           (self.signal_field, self.SIGNAL_CAP)]:
            diff = convolve(field, self.laplacian, mode='constant', cval=0.0)
            field += 0.12 * diff
            field *= (1 - self.DECAY_FACTOR)
            field += ambient_input
            np.clip(field, 0, cap, out=field)

    def run(self, visualize=False):
        for step in range(self.STEPS):
            frac = 0.5 + 0.5 * math.sin(2 * math.pi * step / max(1, self.CYCLE_LENGTH))
            ambient_input = self.BASE_AMBIENT_INPUT * frac

            new_nodes = {}
            dead = []
            step_harvested = 0.0
            step_cost = 0.0

            for (x, y), p in list(self.nodes.items()):
                if p['awake'] and p['energy'] < self.SLEEP_THRESHOLD:
                    p['awake'] = False
                elif not p['awake'] and p['energy'] > self.WAKE_THRESHOLD:
                    p['awake'] = True

                local_mean = np.mean([self.energy_field[i,j] for i,j in self.neighbors(x,y)])
                gained = (local_mean * self.BASE_HARVEST + ambient_input + p['knowledge'] * self.KNOWLEDGE_ENERGY_BOOST)
                p['energy'] += gained
                step_harvested += gained

                cost = self.COMPUTE_COST * (self.SLEEP_COST_FACTOR if not p['awake'] else 1.0)
                p['energy'] -= cost
                step_cost += cost

                if p['awake']:
                    growth = 0.05 * p['energy'] * (1 - p['knowledge']/self.LOGISTIC_K_MAX)
                    p['knowledge'] += growth

                p['energy'] = min(p['energy'], self.ENERGY_CAP)
                p['knowledge'] = min(p['knowledge'], self.KNOWLEDGE_CAP)

                if p['awake']:
                    self.signal_field[x,y] += p['logic'] * 0.9
                    self.energy_field[x,y] += p['knowledge'] * 0.15

                if p['energy'] <= 0:
                    dead.append((x,y))
                    self.energy_field[x,y] += 5.0
                    continue

                if p['awake'] and self.signal_field[x,y] > self.SIGNAL_CREATION_THRESHOLD and random.random() < 0.25:
                    i,j = random.choice(list(self.neighbors(x,y)))
                    if (i,j) not in self.nodes and (i,j) not in new_nodes:
                        new_nodes[(i,j)] = {'energy':4.0,'knowledge':p['knowledge']*0.6,'logic':random.randint(0,1),'awake':True}
                        self.energy_field[i,j] += 2.0

                if p['awake'] and p['energy'] > self.ENERGY_THRESHOLD:
                    i,j = random.choice(list(self.neighbors(x,y)))
                    if (i,j) not in self.nodes and (i,j) not in new_nodes:
                        child_e = p['energy'] * self.REPRODUCTION_COST_FACTOR
                        child_k = p['knowledge'] * self.REPRODUCTION_COST_FACTOR
                        p['energy'] *= (1 - self.REPRODUCTION_COST_FACTOR)
                        p['knowledge'] *= (1 - self.REPRODUCTION_COST_FACTOR)
                        new_nodes[(i,j)] = {'energy':child_e,'knowledge':child_k,'logic':random.randint(0,1),'awake':True}
                        step_cost += child_e

            for dn in dead:
                self.nodes.pop(dn, None)

            self.nodes.update(new_nodes)
            self._diffuse_and_decay(ambient_input)

            for (x,y), p in self.nodes.items():
                self.intel_field[x,y] += p['knowledge'] * 0.07

            # np is already imported at the top of the file
            awake_count = sum(1 for p in self.nodes.values() if p['awake'])
            self.metrics.loc[step] = {
                'step': step,
                'nodes': len(self.nodes),
                'awake_nodes': awake_count,
                'harvested': step_harvested,
                'cost': step_cost,
                'net': step_harvested - step_cost,
                'avg_energy': np.mean([pp['energy'] for pp in self.nodes.values()]) if self.nodes else 0,
                'total_knowledge': np.sum([pp['knowledge'] for pp in self.nodes.values()])
            }

        return self.metrics
