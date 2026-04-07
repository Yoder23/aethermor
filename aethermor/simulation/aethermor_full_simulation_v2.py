import json
import os
import math
import numpy as np
import random
from scipy.ndimage import convolve


class AethermorSimV2:
    """
    Aethermor Simulation v2 (upgraded core):

    - Loads calibrated parameters if available.
    - Records full field histories for 3D animation and regression tests.
    - Temperature-dependent harvesting/healing, entropy/decay, sleep/wake, reproduction.
    - New hooks for:
        * Morphogenesis / modular structure (module_id, cluster_id).
        * Material-twin ROI healing (faulted, repair_priority, actuation_field).
        * Metabolic clusters & thermal load (heat_field, local_workload).
        * Thermodynamic core (info_bits, landauer_J via external ai_core).

    Design constraints:
    - Keep existing tests & dashboards working:
        * energy_field diffusion + entropy still follow the original PDE used in tests.
        * metrics still contain at least: step, alive, avg_energy, total_knowledge.
    - Advanced behaviour is layered ON TOP via nodes, heat_field, actuation_field,
      and optional external controllers, without breaking old expectations.
    """

    def __init__(self,
                 grid_shape=(60, 60, 10),
                 steps=150,
                 calibrated_params_file='calibrated_params.json',
                 specialization_roles=('energy', 'compute', 'repair'),
                 seed=42):
        # RNG seeds
        random.seed(seed)
        np.random.seed(seed)

        # Default params
        params = {
            'base_harvest':       1.0,
            'compute_cost':       0.15,
            'repro_cost':         0.5,
            'ambient_input':      0.3,
            'sleep_threshold':    2.0,
            'wake_threshold':     3.0,
            'decay_factor':       0.015,
            'healing_time':       5,
            'healing_energy':     0.2,
            'entropy_factor':     0.01,
            'temp_coeff_harvest': 0.001,
            'temp_coeff_heal':    0.002,
            # new-ish knobs (sane defaults)
            'role_energy_boost':  0.25,
            'role_compute_boost': 0.25,
            'repair_boost':       0.5,
            'heat_per_compute':   0.02,
            'actuation_gain':     0.5,
            'bits_per_knowledge': 1e4,
        }

        # Load calibrated params if present
        if os.path.isfile(calibrated_params_file):
            try:
                with open(calibrated_params_file) as f:
                    user_params = json.load(f)
                params.update(user_params)
            except (json.JSONDecodeError, ValueError):
                # fall back to defaults if bad JSON
                pass

        # Unpack
        self.base_harvest       = float(params['base_harvest'])
        self.compute_cost       = float(params['compute_cost'])
        self.repro_cost_factor  = float(params['repro_cost'])
        self.ambient_base       = float(params['ambient_input'])
        self.sleep_threshold    = float(params['sleep_threshold'])
        self.wake_threshold     = float(params['wake_threshold'])
        self.decay_factor       = float(params['decay_factor'])
        self.healing_time       = int(params['healing_time'])
        self.healing_energy     = float(params['healing_energy'])
        self.entropy_factor     = float(params['entropy_factor'])
        self.temp_coeff_harvest = float(params['temp_coeff_harvest'])
        self.temp_coeff_heal    = float(params['temp_coeff_heal'])

        # New knobs
        self.role_energy_boost  = float(params.get('role_energy_boost', 0.25))
        self.role_compute_boost = float(params.get('role_compute_boost', 0.25))
        self.repair_boost       = float(params.get('repair_boost', 0.5))
        self.heat_per_compute   = float(params.get('heat_per_compute', 0.02))
        self.actuation_gain     = float(params.get('actuation_gain', 0.5))
        self.bits_per_knowledge = float(params.get('bits_per_knowledge', 1e4))

        # Config
        self.grid_shape = tuple(grid_shape)
        self.steps = int(steps)
        self.roles = tuple(specialization_roles)

        # Core fields
        self.energy_field = np.ones(self.grid_shape) * 3.0
        self.signal_field = np.zeros(self.grid_shape)
        self.intelligence_field  = np.zeros(self.grid_shape)
        self.temp_field   = np.ones(self.grid_shape) * 300.0

        # Extra fields for advanced behaviour:
        # - heat_field: thermal load from compute activity (for metabolic cluster).
        # - actuation_field: localized boosts (for material twin ROI healing).
        self.heat_field      = np.zeros(self.grid_shape)
        self.actuation_field = np.zeros(self.grid_shape)

        # Histories
        self.energy_field_history = []
        self.signal_field_history = []
        self.intelligence_field_history  = []
        self.temp_field_history   = []

        # Nodes
        self.nodes = {}
        xmax, ymax, zmax = self.grid_shape

        # Predefine simple spatial clusters for modules/metabolic clusters:
        #  - cluster_id: 0..3 based on XY quadrants
        #  - module_id: initialized ~ cluster_id, then can be re-written by morphogenesis
        for x in range(xmax):
            for y in range(ymax):
                for z in range(zmax):
                    # Quadrant-based clusters in XY
                    cx = 0 if x < xmax // 2 else 1
                    cy = 0 if y < ymax // 2 else 1
                    cluster_id = cx * 2 + cy  # 0..3

                    role = random.choice(self.roles)

                    self.nodes[(x, y, z)] = {
                        'energy':          3.0,
                        'knowledge':       0.5,
                        'role':            role,
                        'awake':           True,
                        'healing_cd':      0,
                        'buffer':          0.0,
                        # new / extended attributes
                        'module_id':       cluster_id,  # start 1:1 with cluster
                        'cluster_id':      cluster_id,
                        'faulted':         False,       # material twin & morphogenesis use this
                        'repair_priority': 0.0,        # material twin controller can set this
                        'local_workload':  0.0,        # metabolic cluster can read/shape this
                    }

        # 3D Laplacian for diffusion
        self.laplacian = np.zeros((3, 3, 3))
        self.laplacian[1, 1, 0] = self.laplacian[1, 1, 2] = 1
        self.laplacian[1, 0, 1] = self.laplacian[1, 2, 1] = 1
        self.laplacian[0, 1, 1] = self.laplacian[2, 1, 1] = 1
        self.laplacian[1, 1, 1] = -6

        # Metrics over time
        self.metrics = []

        # Thermodynamic core hook (optional external controller, e.g. ThermodynamicAICore)
        # Benchmarks may assign self.ai_core externally; we just call it if present.
        self.ai_core = None

    # -------------------------------------------------------------------------
    # Neighbourhood helpers
    # -------------------------------------------------------------------------

    def neighbors(self, pos):
        x, y, z = pos
        X, Y, Z = self.grid_shape
        for dx, dy, dz in [(-1, 0, 0), (1, 0, 0),
                           (0, -1, 0), (0, 1, 0),
                           (0, 0, -1), (0, 0, 1)]:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < X and 0 <= ny < Y and 0 <= nz < Z:
                yield (nx, ny, nz)

    # -------------------------------------------------------------------------
    # Internal advanced helpers
    # -------------------------------------------------------------------------

    def _update_modules_from_signal(self):
        """
        Simple morphogenesis-inspired modularity:
        - Compute local mean signal per cluster.
        - Softly reassign module_id toward the cluster with strongest signal.
        This gives benchmarks something real to measure (num_modules, gini).
        """
        # Aggregate signal per cluster
        cluster_signals = {}
        cluster_counts = {}
        for pos, p in self.nodes.items():
            x, y, z = pos
            cid = p['cluster_id']
            cluster_signals[cid] = cluster_signals.get(cid, 0.0) + float(self.signal_field[x, y, z])
            cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

        if not cluster_signals:
            return

        # Normalize by counts
        for cid in cluster_signals:
            if cluster_counts[cid] > 0:
                cluster_signals[cid] /= cluster_counts[cid]

        # Find max-signal cluster, use as "module attractor"
        # This is deliberately simple but gives structure differentiation.
        max_cid = max(cluster_signals, key=cluster_signals.get)

        # Reassign some nodes toward that module if they are active
        for pos, p in self.nodes.items():
            if not p['awake']:
                continue
            # nodes with higher knowledge more likely to join high-signal module
            if p['knowledge'] > 1.0 and random.random() < 0.1:
                p['module_id'] = max_cid

    def _material_healing_boost(self, pos, node):
        """
        Extra healing boost used by material-twin style controllers.

        Controllers are expected to:
        - Mark nodes as faulted=True in a region of interest.
        - Increase repair_priority in that ROI over time.

        This function translates those node-level hints into extra healing
        and localized actuation_field energy.
        """
        if not node.get('faulted', False):
            return

        priority = float(node.get('repair_priority', 0.0))
        if priority <= 0.0:
            return

        # Extra local actuation into energy_field via actuation_field
        self.actuation_field[pos] += self.actuation_gain * priority

        # Direct node energy bump (local "healing" budget)
        node['energy'] += self.healing_energy * priority

    def _compute_module_stats(self):
        """
        Compute simple modularity stats for benchmarks:
        - num_modules: number of distinct modules with at least one awake node.
        - module_gini: Gini coefficient over module population sizes.
        """
        module_counts = {}
        for p in self.nodes.values():
            mid = p.get('module_id', -1)
            if mid < 0:
                continue
            module_counts[mid] = module_counts.get(mid, 0) + 1

        if not module_counts:
            return {'num_modules': 0, 'module_gini': 0.0}

        counts = np.array(sorted(module_counts.values()), dtype=float)
        num_modules = len(counts)

        # Gini coefficient
        # G = sum_i sum_j |x_i - x_j| / (2 n^2 mean)
        diffs = np.abs(counts[:, None] - counts[None, :])
        denom = 2.0 * (num_modules ** 2) * counts.mean()
        module_gini = float(diffs.sum() / denom) if denom > 0 else 0.0

        return {'num_modules': num_modules, 'module_gini': module_gini}

    # -------------------------------------------------------------------------
    # One simulation step
    # -------------------------------------------------------------------------

    def step(self, t):
        """
        Advance the simulation by one time step t.

        Order:
        1) Ambient + diffusion / decay for fields (energy, signal, temp, heat).
        2) Node-level updates: harvest, compute, knowledge, signals, healing, sleep/wake, reproduction.
        3) Morphogenesis hook: update module structure from signal.
        4) Material-twin hook: convert repair_priority into local actuation & healing.
        5) Thermodynamic core hook: accumulate info/energy stats if ai_core is attached.
        6) Metrics & history.
        """
        # Sinusoidal ambient input in [0, ambient_base]
        ambient = self.ambient_base * (0.5 + 0.5 * math.sin(2 * math.pi * t / max(1, self.steps)))

        # ------------------------------------------------------------------
        # 1) Diffusion and losses (kept compatible with old tests)
        # ------------------------------------------------------------------
        # energy_field follows the original PDE + entropy
        self.energy_field += convolve(self.energy_field, self.laplacian, mode='constant', cval=0.0) * 0.1
        self.energy_field = np.clip(self.energy_field * (1 - self.entropy_factor), 0.0, None)

        # signal_field diffuses and decays
        self.signal_field += convolve(self.signal_field, self.laplacian, mode='constant', cval=0.0) * 0.1
        self.signal_field = np.clip(self.signal_field * (1 - self.decay_factor), 0.0, None)

        # temp_field diffuses around baseline 300K
        self.temp_field += convolve(self.temp_field, self.laplacian, mode='constant', cval=300.0) * 0.05

        # heat_field diffuses and decays
        self.heat_field += convolve(self.heat_field, self.laplacian, mode='constant', cval=0.0) * 0.1
        self.heat_field *= (1 - self.decay_factor)

        # actuation_field decays (but is injected via material twin each step)
        self.actuation_field *= (1 - self.decay_factor)

        # Combine temp + heat into effective temperature
        effective_temp = self.temp_field + self.heat_field

        # ------------------------------------------------------------------
        # 2) Node updates
        # ------------------------------------------------------------------
        harvested_total = 0.0
        compute_total   = 0.0
        info_bits_step  = 0.0   # for thermodynamic core (optional)
        landauer_J_step = 0.0
        activity_mask = np.zeros(self.grid_shape, dtype=float)

        # Reset per-step workload for metabolic cluster observers
        for p in self.nodes.values():
            p['local_workload'] = 0.0

        for pos, p in self.nodes.items():
            x, y, z = pos
            temp = float(effective_temp[x, y, z])

            # ROLE-BASED modifiers
            role = p.get('role', 'compute')
            role_energy_mult = 1.0
            role_compute_mult = 1.0

            if role == 'energy':
                role_energy_mult += self.role_energy_boost
            elif role == 'compute':
                role_compute_mult += self.role_compute_boost
            elif role == 'repair':
                # repair nodes pay more compute but get better healing later
                role_compute_mult += 0.5 * self.role_compute_boost

            # Harvest (temperature dependent)
            temp_factor_h = max(0.0, 1.0 - self.temp_coeff_harvest * (temp - 300.0))
            harvest = self.base_harvest * ambient * temp_factor_h * role_energy_mult
            p['energy'] += harvest
            p['buffer'] += harvest
            harvested_total += harvest

            # Compute cost
            cost = self.compute_cost * role_compute_mult * (0.5 if not p['awake'] else 1.0)
            p['energy'] -= cost
            compute_total += cost

            # Thermal load from compute
            self.heat_field[pos] += self.heat_per_compute * cost
            p['local_workload'] += cost

            # Knowledge growth
            knowledge_before = float(p['knowledge'])
            if p['awake']:
                p['knowledge'] += 0.02 * max(p['energy'], 0.0)
            knowledge_delta = max(0.0, float(p['knowledge']) - knowledge_before)

            # Signals (intelligence density radiates out)
            self.signal_field[pos] += max(0.0, p['knowledge']) * 0.05

            # Healing (base behaviour)
            if p['energy'] < self.sleep_threshold and p['healing_cd'] == 0:
                heal_amt = min(p['buffer'], self.healing_energy)
                p['buffer'] -= heal_amt

                temp_factor_heal = max(0.0, 1.0 - self.temp_coeff_heal * (temp - 300.0))
                heal_effect = heal_amt * temp_factor_heal

                # Role-based repair boost
                if role == 'repair':
                    heal_effect *= (1.0 + self.repair_boost)

                p['energy'] += heal_effect
                p['healing_cd'] = self.healing_time

            if p['healing_cd'] > 0:
                p['healing_cd'] -= 1

            # Sleep/Wake logic (tests rely on this)
            if p['energy'] < self.sleep_threshold:
                p['awake'] = False
            elif p['energy'] > self.wake_threshold:
                p['awake'] = True

            if p['awake']:
                activity_mask[pos] = 1.0

            # Reproduction (simple neighbor seeding, used in tests & GA)
            if p['energy'] > 1.5 and p['awake']:
                for nbr in self.neighbors(pos):
                    if self.nodes[nbr]['energy'] <= 0.0:
                        self.nodes[nbr].update({
                            'energy':    p['energy'] / 2,
                            'knowledge': p['knowledge'] / 2,
                            'role':      p['role'],
                            'awake':     True,
                            'healing_cd': 0,
                            'buffer':    0.0,
                        })
                        p['energy'] /= 2
                        break

            # Clamp energy, buffer (safety)
            p['energy'] = max(0.0, p['energy'])
            p['buffer'] = max(0.0, p['buffer'])

            # --- Material-twin style healing boost ---
            # External MaterialAdapter is expected to mark:
            #   p['faulted'] = True in ROI
            #   p['repair_priority'] increased over time
            # This converts into extra actuation + node-level healing
            self._material_healing_boost(pos, p)

            # Information accounting proxy: positive knowledge increments only.
            if p['awake'] and knowledge_delta > 0.0:
                info_bits_step += self.bits_per_knowledge * knowledge_delta

        # Landauer cost estimate (upper bound)
        # (k_B * T * ln2) * bits; we use mean temperature.
        k_B = 1.380649e-23
        T_mean = float(effective_temp.mean())
        landauer_per_bit = k_B * T_mean * math.log(2.0)
        landauer_J_step = landauer_per_bit * info_bits_step

        # ------------------------------------------------------------------
        # 3) Morphogenesis-inspired module update
        # ------------------------------------------------------------------
        self._update_modules_from_signal()

        # ------------------------------------------------------------------
        # 4) Inject actuation_field into energy_field (for material twin)
        #     (kept separate from PDE part so old tests are still valid)
        # ------------------------------------------------------------------
        self.energy_field += self.actuation_field

        # Clip again for safety
        self.energy_field = np.clip(self.energy_field, 0.0, None)

        # ------------------------------------------------------------------
        # 5) Thermodynamic AI core hook
        # ------------------------------------------------------------------
        if hasattr(self, "ai_core") and self.ai_core is not None:
            # Give full state so ai_core can accumulate detailed stats.
            self.ai_core.step_accumulate(
                T_field=effective_temp,
                activity_mask=activity_mask,
                nodes=self.nodes,
                energy_field=self.energy_field,
                info_bits_step=info_bits_step,
                landauer_J_step=landauer_J_step,
            )

        # ------------------------------------------------------------------
        # 6) Record histories & metrics
        # ------------------------------------------------------------------
        self.energy_field_history.append(self.energy_field.copy())
        self.signal_field_history.append(self.signal_field.copy())
        self.intelligence_field_history.append(self.intelligence_field.copy())
        self.temp_field_history.append(effective_temp.copy())

        alive = sum(1 for p in self.nodes.values() if p['energy'] > 0)
        avg_e = float(np.mean([p['energy'] for p in self.nodes.values()]))
        tot_k = float(np.sum([p['knowledge'] for p in self.nodes.values()]))

        mstats = self._compute_module_stats()

        # If an external ai_core is attached, let it supply per-step metrics.
        ai_core_metrics = {}
        if hasattr(self, "ai_core") and self.ai_core is not None:
            ai_core_metrics = self.ai_core.metrics()

        self.metrics.append({
            'step':            t,
            'alive':           alive,
            'avg_energy':      avg_e,
            'total_knowledge': tot_k,
            'harvested_energy_step': float(harvested_total),
            'compute_energy_step': float(compute_total),
            # new high-level stats:
            'num_modules':     mstats.get('num_modules', 0),
            'module_gini':     mstats.get('module_gini', 0.0),
            'mean_temp':       float(effective_temp.mean()),
            'max_temp':        float(effective_temp.max()),
            # thermodynamic-core-facing stats (if available):
            'info_bits_step':  float(info_bits_step),
            'landauer_J_step': float(landauer_J_step),
            'info_bits':       float(ai_core_metrics.get('info_bits', info_bits_step)),
            'landauer_J':      float(ai_core_metrics.get('landauer_J', landauer_J_step)),
        })

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def run(self):
        for t in range(self.steps):
            self.step(t)
        return self


if __name__ == '__main__':
    sim = AethermorSimV2()
    sim.run()
    import pickle
    out_path = os.getenv("AETHERMOR_SIM_OUT", "aethermor_sim_v2.pkl")
    out_path = os.path.basename(out_path)  # prevent directory traversal
    try:
        with open(out_path, 'wb') as f:
            pickle.dump(sim, f)
        print(f"Simulation complete. Pickle saved: {out_path}")
    except PermissionError:
        if os.path.isfile(out_path):
            print(f"Simulation complete. Existing pickle retained: {out_path}")
        else:
            raise
