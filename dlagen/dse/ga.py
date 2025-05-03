from .ga_stage import GA_Stage
import numpy as np
import os

class DSE():
	def __init__(self, cost_model, config):
		self.cost_model = cost_model
		self.constraints = config['dse']['constraints']
		self.outputs_folder = os.path.join(config['output'], 'dse')
		self.config = config['dse']

		self.max_area = self.constraints['area']
		self.max_latency = float(self.constraints['latency'])

class GA(DSE):
	def __init__(self, cost_model, config):
		super().__init__(cost_model, config)
		self.inf_value = float(self.config['inf_value'])

	def add_stage(self, weights, evaluate_fn):
		self.cur_stage = GA_Stage(weights, evaluate_fn, self.config)

	def evaluate_latency_constrained(self, individual):
		latency,area,energy,util,mem_util = self.cost_model.evaluate(self.outputs_folder, *individual)
		if area > self.max_area:
			latency = self.inf_value
		return (latency,)

	def setup_stage1(self):
		self.add_stage((-1.0,), self.evaluate_latency_constrained)

	def evaluate_util_constrained(self, individual):
		latency,area,energy,util,mem_util = self.cost_model.evaluate(self.outputs_folder, *individual)
		if area > self.max_area or latency > self.max_latency:
			util = 0
		return (util,)

	def setup_stage2(self):
		self.add_stage((1.0,), self.evaluate_util_constrained)

	def evaluate_mem_util_constrained(self, individual):
		latency,area,energy,util,mem_util = self.cost_model.evaluate(self.outputs_folder, *individual)
		if area > self.max_area or latency > self.max_latency:
			mem_util = 0
		return (mem_util,)

	def setup_stage3(self):
		self.add_stage((1.0,), self.evaluate_mem_util_constrained)

	def evaluate_energy_constrained(self, individual):
		latency,area,energy,util,mem_util = self.cost_model.evaluate(self.outputs_folder, *individual)
		if area > self.max_area or latency > self.max_latency:
			energy = self.inf_value
		return (energy,)

	def setup_stage4(self):
		self.add_stage((-1.0,), self.evaluate_energy_constrained)

	def explore(self):
		if 'stage1' in self.config:
			self.setup_stage1()
			pop_final, hof, log = self.cur_stage.explore(self.config['stage1']['population'], self.config['stage1']['num_gen'], self.config['num_core'])
		if 'stage2' in self.config:
			# self.max_latency = log[-1]["min"] * 1.15
			self.setup_stage2()
			pop_final, hof, log = self.cur_stage.explore(self.config['stage2']['population'], self.config['stage2']['num_gen'], self.config['num_core'], new_pop=hof)
		if 'stage3' in self.config:
			self.setup_stage3()
			pop_final, hof, log = self.cur_stage.explore(self.config['stage3']['population'], self.config['stage3']['num_gen'], self.config['num_core'], new_pop=hof)
		if 'stage4' in self.config:
			self.setup_stage4()
			pop_final, hof, log = self.cur_stage.explore(self.config['stage4']['population'], self.config['stage4']['num_gen'], self.config['num_core'], new_pop=hof)

		pop_final = np.array(pop_final)
		min_index = np.argmin(pop_final[:, 0])
		mins = pop_final[min_index].tolist()

		print('Found architecture with QoR: ', self.cost_model.evaluate(self.outputs_folder, *mins))

		return self.cost_model.get_cost_model(mins, self.outputs_folder), self.cost_model.parse_hardware_individual(*mins), self.config['dim_choices'][mins[-1]]