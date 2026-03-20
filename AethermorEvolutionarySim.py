import random
import os
import numpy as np
import pandas as pd
from deap import base, creator, tools
from scarcity_aethermor import ScarcityAethermorSim

def evaluate_individual(individual, sim_steps=50, grid_size=30):
    (base_harvest, compute_cost, reproduction_cost,
     ambient_input, sleep_thresh, wake_thresh) = individual

    sim = ScarcityAethermorSim(
        grid_size=grid_size,
        steps=sim_steps,
        base_harvest=base_harvest,
        compute_cost=compute_cost,
        reproduction_cost_factor=reproduction_cost,
        base_ambient_input=ambient_input,
        sleep_threshold=sleep_thresh,
        wake_threshold=wake_thresh
    )
    metrics = sim.run(visualize=False)
    final = metrics.iloc[-1]
    net_score = float(final['net'])
    knowledge_score = float(final['total_knowledge'])
    return net_score, knowledge_score

def _toolbox():
    creator.create("FitnessMax", base.Fitness, weights=(1.0, 1.0))
    creator.create("Individual", list, fitness=creator.FitnessMax)
    toolbox = base.Toolbox()
    param_ranges = [
        (0.5, 1.0),   # base_harvest
        (0.05, 0.3),  # compute_cost
        (0.2, 0.8),   # reproduction_cost_factor
        (0.1, 1.0),   # ambient_input_rate
        (1.0, 3.0),   # sleep_threshold
        (2.5, 5.0),   # wake_threshold
    ]
    def init_ind():
        return creator.Individual([random.uniform(a, b) for a, b in param_ranges])

    toolbox.register("individual", init_ind)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", evaluate_individual)
    toolbox.register("mate", tools.cxBlend, alpha=0.5)
    toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.1, indpb=0.2)
    toolbox.register("select", tools.selNSGA2)
    return toolbox

def main(gen_size=10, generations=5):
    tb = _toolbox()
    pop = tb.population(n=gen_size)
    fitnesses = list(map(tb.evaluate, pop))
    for ind, fit in zip(pop, fitnesses):
        ind.fitness.values = fit

    for gen in range(1, generations+1):
        offspring = tb.select(pop, len(pop))
        offspring = list(map(tb.clone, offspring))
        for c1, c2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < 0.9:
                tb.mate(c1, c2)
                if hasattr(c1.fitness, 'values'): del c1.fitness.values
                if hasattr(c2.fitness, 'values'): del c2.fitness.values
        for m in offspring:
            if random.random() < 0.2:
                tb.mutate(m)
                if hasattr(m.fitness, 'values'): del m.fitness.values
        invalids = [ind for ind in offspring if not ind.fitness.valid]
        for ind, fit in zip(invalids, map(tb.evaluate, invalids)):
            ind.fitness.values = fit
        pop[:] = offspring
        top = tools.selBest(pop, 1)[0]
        print(f"Gen {gen}: Best net={top.fitness.values[0]:.3f}, know={top.fitness.values[1]:.3f}")

    fronts = tools.sortNondominated(pop, k=len(pop))
    pareto = fronts[0]

    df = pd.DataFrame(pareto, columns=[
        'base_harvest','compute_cost','repro_cost','ambient_input','sleep_thresh','wake_thresh'
    ])
    out_csv = os.getenv("AETHERMOR_PARETO_OUT", "aethermor_pareto_params.csv")
    try:
        df.to_csv(out_csv, index=False)
        print(f"Evolution complete. Pareto front saved: {out_csv}")
    except PermissionError:
        # In restricted environments, keep algorithm output usable even if the
        # canonical CSV path is locked.
        print(f"Evolution complete, but could not write {out_csv} (permission denied).")
    return pareto

if __name__ == '__main__':
    main()
