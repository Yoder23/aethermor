from simulation.AethermorEvolutionarySim import main as ga_main

def test_ga_optimizer_runs():
    pareto = ga_main(gen_size=4, generations=2)
    assert len(pareto) >= 1
    for ind in pareto:
        assert all(isinstance(x, float) for x in ind)
