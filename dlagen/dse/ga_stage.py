from deap import algorithms, base, creator, tools
from .ga_utils import *

import multiprocessing

from functools import partial

class DSE_Stage():
	def __init__(self):
		pass

	def explore(self):
		pass

class GA_Stage(DSE_Stage):
	def __init__(self, weights, evaluate_fn, config):
		super().__init__()
		self.weights = weights
		self.evaluate_fn = evaluate_fn
		self.config = config

	def explore(self, population, num_gen, num_core, new_pop=None):
		creator.create("FitnessMulti", base.Fitness, weights=self.weights)
		creator.create("Individual", list, fitness=creator.FitnessMulti)

		max_list = [len(self.config['spatial_size_choices'])-1]*2 + [len(self.config['spatial_size_choices_f'])-1] + [len(self.config['spatial_size_choices'])-1] + [len(self.config['mem_size_choices'])-1]*3 + [len(self.config['dim_choices'])-1]

		toolbox = base.Toolbox()
		toolbox.register("individual", partial(initIndividual, max_list=max_list), creator.Individual)
		toolbox.register("population", tools.initRepeat, list, toolbox.individual)

		toolbox.register("mate", tools.cxTwoPoint)
		toolbox.register("mutate", partial(mutate_single_config, max_list=max_list))
		toolbox.register("evaluate", self.evaluate_fn)
		toolbox.register("select", tools.selNSGA2)

		pop = toolbox.population(n=population)
		hof = tools.ParetoFront()
		stats = tools.Statistics(lambda ind: ind.fitness.values)

		if new_pop:
			for i in range(min(len(new_pop),len(pop))):
			    pop[i] = creator.Individual(new_pop[i])

		stats.register("avg", get_avg)
		stats.register("std", get_std)
		stats.register("min", get_min)
		stats.register("max", get_max)
		stats.register("report_min", report_min)
		stats.register("report_max", report_max)
		pool = multiprocessing.Pool(num_core)
		toolbox.register("map", pool.map)
		pop_final, log = algorithms.eaMuPlusLambda(pop, toolbox, mu=population//2, lambda_=population, cxpb=0.7, mutpb=0.3, ngen=num_gen, stats=stats, halloffame=hof)

		pool.close()
		return pop_final, hof, log
		