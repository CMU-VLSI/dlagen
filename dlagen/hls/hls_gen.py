from ..util.indented_str import IndentedString
from .hls_object import HlsDatatype, HlsArray, HlsStruct
from abc import ABC
import os

class HlsGenerator(ABC):
	def __init__(self, config, fifo_mapping, class_mapping):
		self.config = config
		self.fifo_mapping = fifo_mapping
		self.class_mapping = class_mapping

	def parse(self):
		self.parse_datatypes()
		self.parse_hw_graph()
		self.set_rtl_path()

	def parse_datatypes(self):
		self.datatypes = {}
		for n, base in self.config['datatype']['base'].items():
			base['name'] = n
			self.datatypes[n] = HlsDatatype(base)
		for n, array in self.config['datatype']['array'].items():
			array['name'] = n
			array['type'] = self.datatypes[array['type']]
			self.datatypes[n] = HlsArray(array)
		for n, struct in self.config['datatype']['struct'].items():
			struct['name'] = n
			self.datatypes[n] = HlsStruct(struct)
	
	def parse_hw_graph(self):
		self.class_configs = {}
		self.top_class = None
		for n, node in self.config['hw_graph']['class'].items():
			node['name'] = n
			node['inputs'] = []
			node['outputs'] = []
			node['conf_fifo'] = []
			self.class_configs[n] = node
			if node['type'] == 'top':
				self.top_class = n		

		assert self.top_class, "The hardware graph must specify a top-level class."

		self.fifos = {}
		for n, fifo in self.config['hw_graph']['fifo'].items():
			fifo['name'] = n
			if 'datatype' in fifo:
				fifo['datatype'] = self.datatypes[fifo['datatype']]
			self.fifos[n] = self.construct_fifo(fifo)
			if fifo['type'] == 'conf':
				self.class_configs[fifo['dst']]['conf_fifo'] += [self.fifos[n]]
				if self.class_configs[fifo['dst']]['type'] == 'config':
					global_conf_name = n
			else:
				self.class_configs[fifo['dst']]['inputs'] += [self.fifos[n]]
			self.class_configs[fifo['src']]['outputs'] += [self.fifos[n]]

		self.graph = {}
		self.classes = {}
		for n, node in self.class_configs.items():
			if 'datatype' in node:
				node['datatype'] = self.datatypes[node['datatype']]
			self.classes[n] = self.construct_class(node)

		for n, fifo in self.config['hw_graph']['fifo'].items():
			self.fifos[n].src = self.classes[fifo['src']]
			self.fifos[n].dst = self.classes[fifo['dst']]
			# fill global conf
			if fifo['type'] == 'conf':
				self.fifos[global_conf_name].conf_list += self.fifos[n].global_conf_list

		self.graph['nodes'] = self.classes
		self.graph['edges'] = self.fifos
		self.classes[self.top_class].hwgraph = self.graph

	def get_memories(self):
		mems = []
		for n, c in self.classes.items():
			if c.config['type'] == 'mem':
				mems += [c]
		return mems

	def construct_fifo(self, fifo_config):
		return self.fifo_mapping[fifo_config['type']](fifo_config)

	def construct_class(self, class_config):
		return self.class_mapping[class_config['type']](class_config)

	def include_libs(self):
		return IndentedString()

	def gen_definition(self):
		hls_str = IndentedString()
		# define datatypes
		for d in self.datatypes.values():
			hls_str.insert(d.gen_definition())
		hls_str.append('')
		# define parameters from conf fifos and classes
		for c in self.classes.values():
			hls_str.insert(c.gen_definition())
		hls_str.append('')
		for f in self.fifos.values():
			if f.type == 'conf':
				hls_str.insert(f.gen_definition())
		hls_str.append('')
		return hls_str

	def gen_hls(self):
		hls_str = IndentedString()
		hls_str.insert(self.include_libs())
		hls_str.insert(self.gen_definition())
		for c in self.classes.values():
			if c.config['type'] != 'top':
				hls_str.insert(c.gen_hls())
		hls_str.insert(self.classes[self.top_class].gen_hls())
		return hls_str

	def gen_build_tcl(self):
		return IndentedString()

	def generate(self, location):
		with open(os.path.join(location, f'{self.top_class}.h'), 'w') as f:
			f.write(str(self.gen_hls()))
		with open(os.path.join(location, 'build_prj.tcl'), 'w') as f:
			f.write(str(self.gen_build_tcl()))