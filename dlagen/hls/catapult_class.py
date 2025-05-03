from ..util.indented_str import IndentedString
from .catapult_fifo import CatapultHandshake, CatapultConfFifo
from .hls_object import HlsVar, HlsDef, HlsArray

class CatapultClass():
	def __init__(self, config):
		self.inputs = config['inputs']
		self.outputs = config['outputs']
		self.name = config['name']
		self.config = config

		self.conf_fifo = config['conf_fifo']

		self.class_name = self.name
		self.inst_name = f'{self.name}_inst'

		self.top_channel_list = self.inputs + self.outputs + self.conf_fifo
		self.setup_conf_list()
		if not isinstance(self, CatapultParentClass) and not isinstance(self, CatapultTopClass): ## for parent class, conf will be set by sublasses
			self.conf_fifo[0].conf_list = self.conf_list
			self.conf_fifo[0].global_conf_list = self.global_conf_list
		self.setup_var_list()
		self.setup_definitions()

		if not isinstance(self, CatapultSubClass):
			self.func_name = 'run'
			self.func_type = 'interface'
			self.func_call_str = f'{self.inst_name}.{self.func_name}('

		self.cluster = config['catapult_cluster'] if 'catapult_cluster' in config else False

	def gen_hls(self, gen_header=True):
		outstr = IndentedString()
		if gen_header:
			outstr.insert(self.gen_hls_class_header())
			outstr.indent()
		outstr.insert(self.gen_hls_top_func_interface())
		outstr.indent()
		outstr.insert(self.gen_hls_read_conf())
		outstr.insert(self.gen_hls_init_var())
		outstr.insert(self.gen_hls_body())
		outstr.insert(self.gen_hls_assert_handshake())
		outstr.close_bracket(1)
		if gen_header:
			outstr.close_cpp_class()
		return outstr

	def gen_definition(self):
		outstr = IndentedString()
		for d in self.definitions:
			if isinstance(d, HlsDef):
				outstr.append(str(d))
			elif isinstance(d, HlsArray):
				outstr.insert(d.gen_definition())
		return outstr

	def gen_tcl_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		if isinstance(self, CatapultTopClass):
			inst_name = ''
		else: 
			inst_name = self.class_name
		# cluster
		if self.cluster:
			outstr.append(get_catapult_command_fn(inst=inst_name, command='CLUSTER', value='{multadd addtree square mult}'))
		# word width
		for fifo in self.top_channel_list:
			if isinstance(fifo.datatype, HlsArray):
				outstr.append(get_catapult_command_fn(inst=f'{inst_name}/{fifo.name}', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
		outstr.insert(self.gen_tcl_word_width_commands(get_catapult_command_fn))
		outstr.insert(self.gen_tcl_mem_mapping_commands(get_catapult_command_fn))
		outstr.insert(self.gen_tcl_loop_commands(get_catapult_command_fn))
		return outstr

	def gen_tcl_word_width_commands(self, get_catapult_command_fn):
		return IndentedString()

	def gen_tcl_mem_mapping_commands(self, get_catapult_command_fn):
		return IndentedString()

	def gen_tcl_loop_commands(self, get_catapult_command_fn):
		return IndentedString()

	def gen_hls_class_header(self):
		outstr = IndentedString()
		outstr.append(f'class {self.class_name} {{')
		outstr.indent()
		outstr.insert(self.gen_hls_custom_functions())
		outstr.insert(self.gen_hls_sub_functions())
		outstr.unindent()
		outstr.append_and_indent('public:')
		outstr.append(f'{self.class_name} () {{}}')
		outstr.append('')
		return outstr

	def gen_hls_custom_functions(self):
		outstr = IndentedString()
		if not 'custom_functions' in self.config:
			return outstr
		for fn in self.config['custom_functions']:
			fn_str = IndentedString()
			with open(fn, 'r') as f:
				fn_str.parse_file(f)
			outstr.insert(fn_str)
		return outstr

	def gen_hls_sub_functions(self):
		return IndentedString()

	def setup_conf_list(self):
		self.conf_list = []
		self.global_conf_list = []

	def setup_var_list(self):
		self.var_list = []

	def setup_definitions(self):
		self.definitions = []

	def gen_hls_assert_handshake(self):
		outstr = IndentedString()
		for fifo in self.top_channel_list:
			if isinstance(fifo, CatapultHandshake):
				outstr.append(f'{fifo.name}.sync_out();')
		return outstr

	def gen_hls_func_interface(self, func_name, hls_design_type, channel_list):
		# assert len(channel_list) > 0, "Cannot instantiate a function with no i/o channels."
		func_intf = IndentedString()
		if hls_design_type is not None:
			func_intf.append(f'#pragma hls_design {hls_design_type}')
		func_intf.append(f'void {func_name} (')
		func_intf.indent()
		for idx, channel in enumerate(channel_list):
			if isinstance(channel, CatapultHandshake):
				datatype = channel.datatype
			elif isinstance(channel, CatapultConfFifo):
				datatype = channel.datatype
			else:
				datatype = channel.datatype.name
			name = channel.name
			if idx == len(channel_list) - 1:
				end_str = '){'
			else:
				end_str = ','
			if not datatype == 'ac_sync':
				datatype = f'ac_channel<{datatype}>'
			func_intf.append(f'{datatype} &{name}{end_str}')
		func_intf.append('')
		return func_intf

	def gen_hls_top_func_interface(self):
		return self.gen_hls_func_interface(self.func_name, self.func_type, self.top_channel_list)

	def gen_hls_read_conf(self):
		conf_read_str = IndentedString()
		assert len(self.conf_fifo) == 1, "Non-parent or top class can only have 1 config fifo!"
		conf_read_str.append(f'{self.conf_fifo[0].datatype} conf_tmp = {self.conf_fifo[0].name}.read();')
		for conf in self.conf_list:
			conf_read_str.append(str(conf))
		conf_read_str.append('')
		return conf_read_str

	def gen_hls_init_var(self):
		init_var_str = IndentedString()
		for var in self.var_list:
			init_var_str.append(str(var))
		init_var_str.append('')
		return init_var_str

	def gen_hls_body(self):
		return IndentedString()

	##### COMMON HELPER FUNCTIONS #####

	def append_for_loop_head(self, loop_name, name_prefix, datatype, indent_str):
		indent_str.append_fixed_indent(f'{name_prefix.upper()}_{loop_name.upper()}:')
		indent_str.append_and_indent(f'for ({datatype} {loop_name} = 0; {loop_name} < {loop_name.upper()}; {loop_name}++) {{')

	def gen_merged_loop(self, loop_name, first_loop, loop_order, loop_body):
		outstr = IndentedString()
		total_max = 1
		for loop in loop_order:
			name = loop[0]
			max_iter = loop[1]
			total_max *= max_iter
			datatype = 'uint8_t ' if max_iter < 2**8 else 'uint16_t '
			datatype = datatype if first_loop else ''
			outstr.append(f'{datatype}{name} = 0;')
		outstr.append_fixed_indent(f'{loop_name}:')
		datatype = 'uint16_t' if total_max < 2**16 else 'uint32_t'
		outstr.append_and_indent(f'for ({datatype} sram = 0; sram < {total_max}; sram++) {{')
		outstr.insert(loop_body)
		reversed_list = loop_order[::-1]
		for i in range(len(reversed_list)):
			if i == 0:
				outstr.append(f'{reversed_list[i][0]}++;')
			if i == len(reversed_list) - 1:
				outstr.append(f'if ({reversed_list[i][0]} == {reversed_list[i][0].upper()}_P) break;')
			else:
				outstr.append_and_indent(f'if ({reversed_list[i][0]} == {reversed_list[i][0].upper()}_P) {{')
				outstr.append(f'{reversed_list[i][0]} = 0;')
				outstr.append(f'{reversed_list[i+1][0]}++;')
				outstr.close_bracket(1)
		outstr.close_bracket(1)
		return outstr

	def gen_func_call(self):
		func_call = IndentedString()
		func_call_str = self.func_call_str
		for idx, channel in enumerate(self.top_channel_list):
			name = channel.name
			func_call_str += name
			if idx == len(self.top_channel_list) - 1:
				func_call_str += ');'
			else:
				func_call_str += ', '
		func_call.append(func_call_str)
		return func_call

	def append_if_else(self, if_str, if_body, else_body, indent_str):
		indent_str.append_and_indent(f'if ({if_str}) {{')
		if type(if_body) is str:
			indent_str.append(if_body)
		else:
			indent_str.insert(if_body)
		if else_body:
			indent_str.unindent()
			indent_str.append_and_indent('} else {')
			if type(else_body) is str:
				indent_str.append(else_body)
			else:
				indent_str.insert(else_body)
			indent_str.close_bracket(1)
		else:
			indent_str.close_bracket(1)
	
class CatapultParentClass(CatapultClass):
	def __init__(self, config):
		super().__init__(config)

	def setup_private_var_list(self):
		self.private_var_list = []

	def gen_hls(self):
		outstr = IndentedString()
		outstr.insert(self.gen_hls_class_header())
		outstr.indent()
		outstr.insert(self.gen_hls_top_func_interface())
		outstr.indent()
		outstr.insert(self.gen_hls_body())
		outstr.close_bracket(1)
		outstr.unindent(1)
		outstr.insert(self.gen_init_private_vars())
		outstr.append('};')
		return outstr

	def gen_init_private_vars(self):
		self.setup_private_var_list()
		var_str = IndentedString()
		if len(self.private_var_list) > 0:
			var_str.append('private:')
			var_str.indent()
		for var in self.private_var_list:
			var_str.append(str(var))
		var_str.append('')
		return var_str

class CatapultSubClass(CatapultClass):
	def __init__(self, config, func_name):
		self.func_name = func_name
		self.func_type = ''
		self.func_call_str = f'{self.func_name}('
		super().__init__(config)

	def gen_hls(self):
		outstr = IndentedString()
		outstr.insert(self.gen_hls_top_func_interface())
		outstr.indent()
		outstr.insert(self.gen_hls_read_conf())
		outstr.insert(self.gen_hls_init_var())
		outstr.insert(self.gen_hls_body())
		outstr.close_bracket(1)
		return outstr

class CatapultTopClass(CatapultParentClass):
	def __init__(self, config):
		super().__init__(config)
		self.func_name = 'CCS_BLOCK(run)'

	@property
	def hwgraph(self):
		return self._hwgraph

	@hwgraph.setter
	def hwgraph(self, hwgraph):
		self._hwgraph = hwgraph
		self.classes = hwgraph['nodes']
		self.fifos = hwgraph['edges']
		top = [c for c in self.classes.values() if isinstance(c, CatapultTopClass)]
		assert len(top) == 1, "Only one top module is allowed!"
		self.top = top

	def setup_private_var_list(self):
		self.private_var_list = []
		for c in self.classes.values():
			if c.name != self.top[0].name:
				self.private_var_list += [HlsVar(name=c.inst_name, type=c.class_name)]

		for f in self.fifos.values():
			if isinstance(f.src, CatapultTopClass) or isinstance(f.dst, CatapultTopClass):
				continue
			self.private_var_list += [HlsVar(name=f.name, type=f.channel_name)]
	
	def gen_hls_body(self):
		outstr = IndentedString()
		# BFS
		visited = {}
		for n in self.hwgraph['nodes'].keys():
			visited[n] = n == self.top[0].name
		visiting = self.top
		while True:
			to_visit = []
			for n in visiting:
				for e in n.outputs:
					if isinstance(e, CatapultHandshake):
						continue
					if n.config['type'] == 'config' and isinstance(e, CatapultConfFifo):
						continue
					name = e.dst.name
					if not visited[name]:
						visited[name] = True
						to_visit += [self.classes[e.dst.name]]
			for c in to_visit:
				outstr.insert(c.gen_func_call())
			visiting = to_visit
			if all(visited.values()):
				break
		return outstr

	def gen_hls_class_header(self):
		outstr = IndentedString()
		outstr.append('#pragma hls_design top')
		outstr.append(f'class {self.class_name} {{')
		outstr.indent()
		outstr.insert(self.gen_hls_custom_functions())
		outstr.insert(self.gen_hls_sub_functions())
		outstr.unindent()
		outstr.append_and_indent('public:')
		outstr.append(f'{self.class_name} () {{}}')
		outstr.append('')
		return outstr