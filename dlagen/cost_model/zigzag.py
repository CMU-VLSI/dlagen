from zigzag.api import get_hardware_performance_zigzag
from zigzag.utils import open_yaml

import os
import yaml
import pickle
import math

class ZigzagCostModel():
	def __init__(self, config):
		self.workload_path = config['dse']['workload']
		self.opt_target = config['dse']['target']
		self.operands = ['i', 'w', 'o']
		self.config = config
		self.base_accelerator = self.parse_base_individual()

	def parse_base_individual(self):
		accelerator = open_yaml(self.config['dse']['base_accelerator'])
		return accelerator
		
	def get_spatial_map_choices(self, dim):
		dim = self.config['dse']['dim_choices'][dim]
		return ['K', 'C', f'F{dim.upper()}', f'O{dim.upper()}']

	def parse_spatial_sizes(self, d1_idx, d2_idx, d3_idx, d4_idx):
		d1 = self.config['dse']['spatial_size_choices'][d1_idx]
		d2 = self.config['dse']['spatial_size_choices'][d2_idx]
		d3 = self.config['dse']['spatial_size_choices_f'][d3_idx]
		d4 = self.config['dse']['spatial_size_choices'][d4_idx]
		return [d1, d2, d3, d4]

	def parse_sram(self, mem_sizes, spatial_sizes, mem_dict):
		d1, d2, d3, d4 = spatial_sizes
		l1_bw = {}
		l1_bw['i'] = d2 * (d3+d4) * self.config['dse']['bitwidth']['i']
		l1_bw['w'] = d1 * d2 * d3 * self.config['dse']['bitwidth']['w']
		l1_bw['o'] = d1 * d4 * self.config['dse']['bitwidth']['o']
		for i, op in enumerate(self.operands):
			mem_name = f'l1_{op}'
			mem_dict[mem_name]['size'] = self.config['dse']['mem_size_choices'][mem_sizes[i]]
			mem_dict[mem_name]['r_bw'] = l1_bw[op]
			mem_dict[mem_name]['w_bw'] = l1_bw[op]
			mem_dict[mem_name]['r_cost'] = self.config['cost_model']['energy']['unit_sram_sp'] * l1_bw[op]
			mem_dict[mem_name]['w_cost'] = self.config['cost_model']['energy']['unit_sram_sp'] * l1_bw[op]
		return mem_dict

	def parse_hardware_individual(self, d1, d2, d3, d4, l1_i_size, l1_w_size, l1_o_size, dim):
		spatial_sizes = self.parse_spatial_sizes(d1, d2, d3, d4)
		accelerator = self.base_accelerator
		accelerator['operational_array']['sizes'] = spatial_sizes
		accelerator['memories'] = self.parse_sram([l1_i_size, l1_w_size, l1_o_size], spatial_sizes, accelerator['memories'])
		return accelerator
		
	def get_area(self, accelerator):
		d1, d2, d3, d4 = accelerator['operational_array']['sizes']
		if self.config['cost_model']['area']['mode'] == 'simple':
			area = self.config['cost_model']['area']['unit_mac'] * (d1*d2*d3*d4) + self.config['cost_model']['area']['unit_sram_sp'] * (accelerator['memories']['l1_i']['size']+accelerator['memories']['l1_w']['size'])
			o_unit_sram = self.config['cost_model']['area']['unit_sram_sp'] if self.config['dse']['dataflow'] == 'output_stationary' else self.config['cost_model']['area']['unit_sram_1r1w']
			area += accelerator['memories']['l1_o']['size'] * o_unit_sram
		else:
			raise NotImplemented
		return area

	def get_mapping(self, d1, d2, d3, d4, dim, path_name):
		D1, D2, D3, D4 = self.get_spatial_map_choices(dim)
		spatial_dims = [D1, D2, D3, D4]
		d1, d2, d3, d4 = self.parse_spatial_sizes(d1, d2, d3, d4)
		spatial_sizes = [d1, d2, d3, d4]
		mapping = [{'name': 'default', 'spatial_mapping': {'D1': [f'{D1}, {d1}'], 'D2': [f'{D2}, {d2}'], 'D3': [f'{D3}, {d3}'], 'D4': [f'{D4}, {d4}']}, 'memory_operand_links': {'O': 'O', 'W': 'I2', 'I': 'I1'}}]
		# if self.config['dse']['flexibility'] == 'fixed_tf':
		# 	pass
		if self.config['dse']['dataflow'] == 'output_stationary':
			workload = open_yaml(self.workload_path)
			for layer in workload:
				if layer['operator_type'] != 'Conv':
					continue
				loop_dims = layer['loop_dims']
				loop_sizes = layer['loop_sizes']
				tf = []
				for dim in ['FX', 'FY', 'FZ', 'C']:
					if dim not in loop_dims:
						continue
					if dim in spatial_dims and loop_sizes[loop_dims.index(dim)] <= spatial_sizes[spatial_dims.index(dim)]:
						continue
					tf += [[dim, '*']]
				for dim in ['OX', 'OY', 'OZ', 'K']:
					if dim not in loop_dims:
						continue
					if dim in spatial_dims and loop_sizes[loop_dims.index(dim)] <= spatial_sizes[spatial_dims.index(dim)]:
						continue
					tf += [[dim, '*']]
				mapping += [{'name': layer['name'], 'spatial_mapping': {'D1': [f'{D1}, {d1}'], 'D2': [f'{D2}, {d2}'], 'D3': [f'{D3}, {d3}'], 'D4': [f'{D4}, {d4}']}, 
					'temporal_ordering': tf, 
					'memory_operand_links': {'O': 'O', 'W': 'I2', 'I': 'I1'}}]
		with open(path_name, 'w') as f:
			yaml.dump(mapping, f, sort_keys=False)
		return path_name

	def get_cost_model(self, config, outputs_folder):
		idx = hash(tuple(config))
		dump_path = os.path.join(outputs_folder, f'cfg{idx}')

		pickle_filename = os.path.join(dump_path, f'{os.path.basename(self.workload_path)}-saved_list_of_cmes.pickle')
		with open(pickle_filename, 'rb') as handle:
			cme_for_all_layers = pickle.load(handle)
		return cme_for_all_layers

	def dse2hls(self, hls_config, zigzag_cme, zigzag_acc, compute_xyz):
		## temporal map
		## assuming fixed temporal dataflow
		temporal_map = zigzag_cme[-1].temporal_mapping.mapping_dic_origin
		operands = list(temporal_map.keys())
		sram_loop = {}
		dram_num_iter = {}
		compute_loop = list(reversed(temporal_map[operands[0]][0] + temporal_map[operands[0]][1] + temporal_map[operands[0]][2]))
		compute_loop_processed = [(f'{str(loop[0]).lower()}_t', loop[1]) for loop in compute_loop]
		hls_config['hw_graph']['class']['compute']['loop_order'] = compute_loop_processed
		for op in operands:
			sram_loop[str(op)] = list(reversed(temporal_map[op][0] + temporal_map[op][1]))
			dram = 1
			for loop in temporal_map[op][2]:
				dram *= loop[1]
			dram_num_iter[str(op)] = dram
		for op, loops in sram_loop.items():
			loop_order = [(f'{str(loop[0]).lower()}_t', loop[1]) for loop in loops]
			inout = 'in' if str(op) == 'O' else 'out'
			hls_config['hw_graph']['class'][f'l1_{str(op).lower()}'][inout]['loop_order'] = loop_order
			hls_config['hw_graph']['class'][f'l1_{str(op).lower()}'][inout]['compute_loop_order'] = compute_loop_processed
			mem_loop = []
			for loop in loops:
				loop_name = str(loop[0])
				if str(op) == 'O':
					if loop_name in ['OX', 'OY', 'OZ', 'K']:
						mem_loop += [f'{str(loop_name).lower()}_t']
				elif str(op) == 'I':
					if loop_name in ['OX', 'OY', 'OZ', 'FX', 'FY', 'FZ', 'C']:
						mem_loop += [f'{str(loop_name).lower()}_t']
				elif str(op) == 'W':
					if loop_name in ['FX', 'FY', 'FZ', 'C', 'K']:
						mem_loop += [f'{str(loop_name).lower()}_t']
			if str(op) == 'I':
				i_xyz = []
				for xyz in 'xyz':
					f_str = f'f{xyz}_t'
					o_str = f'o{xyz}_t'
					if f_str in mem_loop and o_str in mem_loop:
						i_xyz += xyz
						## assuming output stationary
						mem_loop.remove(f_str)
						mem_loop[mem_loop.index(o_str)] = f'i{xyz}'
						if o_str in mem_loop:
							mem_loop.remove(o_str)
				hls_config['hw_graph']['class'][f'l1_{str(op).lower()}'][inout]['xyz'] = i_xyz
			hls_config['hw_graph']['class'][f'l1_{str(op).lower()}'][inout]['mem_order'] = mem_loop

		## update mac array size
		hls_config['hw_graph']['class']['compute']['sizes'] = zigzag_acc['operational_array']['sizes']
		## update mac array dims
		hls_config['hw_graph']['class']['compute']['xyz'] = compute_xyz
		hls_config['datatype']['array']['l1_o_word']['reshape_dims'] = ['k_s', f'o{compute_xyz.lower()}_s']
		hls_config['datatype']['array']['l1_i_word']['reshape_dims'] = ['c_s', f'i{compute_xyz.lower()}']
		hls_config['datatype']['array']['l1_w_word']['reshape_dims'] = ['k_s', 'c_s', f'f{compute_xyz.lower()}_s']

		## update mem dimensions
		for n, c in hls_config['hw_graph']['class'].items():
			if c['type'] != 'mem':
				continue
			if n not in zigzag_acc['memories']:
				continue
			acc_mem = zigzag_acc['memories'][n]
			width = math.ceil(acc_mem['r_bw'] / hls_config['datatype']['base'][hls_config['datatype']['array'][c['datatype']]['type']]['params'][0])
			depth = math.ceil(acc_mem['size'] / acc_mem['r_bw'])
			hls_config['datatype']['array'][c['datatype']]['params'] = [width]
			hls_config['hw_graph']['class'][n]['depth'] = depth
		## quant_scale mem dimensions
		hls_config['datatype']['array']['l1_s_word']['params'] = [zigzag_acc['operational_array']['sizes'][0] * zigzag_acc['operational_array']['sizes'][1]]
		hls_config['hw_graph']['class']['l1_s']['out']['loop_order'] = compute_loop_processed
		hls_config['hw_graph']['class']['l1_s']['out']['compute_loop_order'] = compute_loop_processed
		mem_loop = []
		l1_s_depth = 1
		for loop in compute_loop:
			loop_name = str(loop[0])
			if loop_name in ['C', 'K']:
				mem_loop += [f'{str(loop_name).lower()}_t']
				l1_s_depth *= loop[1]
		hls_config['hw_graph']['class']['l1_s']['out']['mem_order'] = mem_loop
		hls_config['hw_graph']['class']['l1_s']['depth'] = l1_s_depth

		return hls_config

	def run_zigzag(self, workload, accelerator, mapping, opt, dump_folder, pickle_filename):
		try:
			energy, latency, cme = get_hardware_performance_zigzag(workload=workload,
																   accelerator=accelerator,
																   mapping=mapping,
																   opt=opt,
																   dump_folder=dump_folder,
																   pickle_filename=pickle_filename)
			with open(pickle_filename, 'rb') as handle:
				cme_for_all_layers = pickle.load(handle)

			util = 0
			total = 0
			mem_util = 0
			for cme in cme_for_all_layers:
				total += cme.latency_total2
				util += cme.latency_total2 * cme.mac_utilization2
				for k, v in cme.mem_utili_shared.items():
					mem_util += v[1]
			util = util / total
			mem_util /= 3*len(cme_for_all_layers)
		except:
			latency = float(self.config['dse']['inf_value'])
			energy = float(self.config['dse']['inf_value'])
			util = 0
			mem_util = 0
			cme_for_all_layers = None
		return energy, latency, util, mem_util, cme_for_all_layers


	def evaluate(self, outputs_folder, d1, d2, d3, d4, l1_i_size, l1_w_size, l1_o_size, dim):
		idx = hash(tuple([d1, d2, d3, d4, l1_i_size, l1_w_size, l1_o_size, dim]))
		dump_path = os.path.join(outputs_folder, f'cfg{idx}')
		os.makedirs(dump_path, exist_ok=True)

		accelerator = self.parse_hardware_individual(d1, d2, d3, d4, l1_i_size, l1_w_size, l1_o_size, dim)
		acc_path_name = os.path.join(dump_path, 'hardware.yaml')
		with open(acc_path_name, 'w') as f:
			yaml.dump(accelerator, f, sort_keys=False)
		pickle_filename = os.path.join(dump_path, f'{os.path.basename(self.workload_path)}-saved_list_of_cmes.pickle')
		mapping = self.get_mapping(d1, d2, d3, d4, dim, os.path.join(dump_path, 'mapping.yaml'))

		energy, latency, util, mem_util, cme_for_all_layers = self.run_zigzag(workload=self.workload_path,
															   accelerator=acc_path_name,
															   mapping=mapping,
															   opt=self.opt_target,
															   dump_folder=dump_path,
															   pickle_filename=pickle_filename)
		area = self.get_area(accelerator)

		# FIXME, disallow any single operand width to be 1
		if 1 in [d2*(d3+d4), d1*d2*d3, d1*d4]:
			return float(self.config['dse']['inf_value']), area, float(self.config['dse']['inf_value']), 0, 0

		return latency,area,energy,util,mem_util