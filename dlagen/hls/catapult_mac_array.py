from ..util.indented_str import IndentedString
from .catapult_class import CatapultClass
from .hls_object import HlsConf, HlsVar, HlsDef
from .util import define_i_xyz, update_loop_order_subset_from_unique_loop_order, get_addr_from_loop_list, make_unique_loop_order

class CatapultMacArray(CatapultClass):
	def __init__(self, config):
		self.xyz = config['xyz']
		self.all_xyz = config['all_xyz']
		dims_options = {'x': ['k', 'c', 'fx', 'ox'], 'y': ['k', 'c', 'fy', 'oy'], 'z': ['k', 'c', 'fz', 'oz']}
		self.defs = []
		self.sizes = config['sizes']
		self.dims = dims_options[self.xyz]

		self.loop_order = config['loop_order']
		updated_names, self.tile_variable_definitions = update_loop_order_subset_from_unique_loop_order([loop[0] for loop in self.loop_order], make_unique_loop_order(self.loop_order))
		self.loop_order = [(updated_names[i], self.loop_order[i][1]) for i in range(len(self.loop_order))]

		self.rf_accum_loops = {}
		self.rf_accum_loops['s'] = [f'f{self.xyz}_s', f'o{self.xyz}_s']
		self.rf_accum_loops['t'] = []
		for loop in self.loop_order[::-1]:
			if 'o' in loop[0]:
				break
			else:
				self.rf_accum_loops['t'] += [loop[0]]
		self.residual = config['residual'] is not None
		self.scale_dim = config['scale_dim']
		self.set_rf_acc_if_conditions()

		super().__init__(config)

		if self.residual:
			self.res_in = [fifo for fifo in self.inputs if fifo.name == config['residual']][0]

	def setup_definitions(self):
		self.definitions = []
		for d, s in zip(self.dims, self.sizes):
			self.definitions += [HlsDef(name=d.upper(), type='S', params=s)]
		self.definitions += [HlsDef(name=f'I{self.xyz.upper()}', type='', params=self.sizes[2]+self.sizes[3])]

	def setup_conf_list(self):
		self.conf_list = [HlsConf(name='STRIDE_P', type='ac_int<2, false>'), 
			HlsConf(name='PADDING_P', type='ac_int<2, false>'), 
			HlsConf(name='RES_ADD_P', type='bool')]
		for loop in self.loop_order:
			self.conf_list += [HlsConf(name=f'{loop[0].upper()}_P', type='uint8_t' if loop[1] < 2**8 else 'uint16_t')]
		self.global_conf_list = self.conf_list

	def setup_var_list(self):
		self.var_list = []
		for i, xyz in enumerate(self.all_xyz):
			self.var_list += [HlsVar(name=f'i{xyz}', type='uint16_t')]
		self.var_list += [HlsVar(name=f'rf_o [O{self.xyz.upper()}_S*K_S]', type='p_t')]

	def get_rf_o_index(self):
		return get_addr_from_loop_list(['k_s', f'o{self.xyz}_s'], fixed_bounds=True)

	def set_rf_acc_if_conditions(self):
		self.rf_accum_end_if_str = {}
		self.rf_accum_start_if_str = {}
		def helper(st):
			self.rf_accum_end_if_str[st] = ''
			self.rf_accum_start_if_str[st] = ''
			for i, loop in enumerate(self.rf_accum_loops[st]):
				postfix = '' if st == 's' else '_P'
				self.rf_accum_end_if_str[st] += f'({loop} == {loop.upper()}{postfix} - 1)'
				self.rf_accum_start_if_str[st] += f'({loop} == 0)'
				if i != len(self.rf_accum_loops[st]) - 1:
					self.rf_accum_end_if_str[st] += ' && '
					self.rf_accum_start_if_str[st] += ' && '
		helper('s')
		helper('t')

	def read_from_fifo(self):
		outstr = IndentedString()
		for fifo in self.inputs:
			if fifo.name == self.config['residual']:
				continue
			outstr.append(f'{fifo.datatype.name} {fifo.name}_r = {fifo.name}.read();')
		for fifo in self.outputs:
			outstr.append(f'{fifo.datatype.name} {fifo.name}_w;')
		return outstr

	def write_to_fifo(self):
		outstr = IndentedString()
		if_body = IndentedString()
		for fifo in self.outputs:
			if_body.append(f'{fifo.name}.write({fifo.name}_w);')
		self.append_if_else(if_str=self.rf_accum_end_if_str['t'], if_body=if_body, else_body=None, indent_str=outstr)
		return outstr

	def get_single_word(self):
		outstr = IndentedString()
		for fifo in self.inputs:
			if fifo.name == self.config['residual']:
				continue
			outstr.append(f'{fifo.datatype.type.name} cur_{fifo.datatype.type.raw_name} = {fifo.name}_r[{get_addr_from_loop_list(fifo.datatype.reshape_dims, fixed_bounds=True)}];')
		return outstr

	def mult(self):
		outstr = IndentedString()
		outstr.append('p_t cur_o = mul_fp4(cur_i, cur_w);')
		return outstr

	def accum(self):
		outstr = IndentedString()
		scale_str = ' << cur_s' if 'c' in self.scale_dim else ''
		if_body = f'rf_o[{self.get_rf_o_index()}] = cur_o{scale_str};'
		else_body = f'rf_o[{self.get_rf_o_index()}] += cur_o{scale_str};'
		self.append_if_else(if_str=f'{self.rf_accum_start_if_str["t"]} && {self.rf_accum_start_if_str["s"]}', if_body=if_body, else_body=else_body, indent_str=outstr)
		return outstr

	def read_residual_connection(self):
		outstr = IndentedString()
		outstr.append(f'{self.res_in.datatype.name} {self.res_in.name}_r;')
		outstr.append_and_indent(f'if ({self.rf_accum_end_if_str["t"]}) {{')
		outstr.append(f'if (RES_ADD_P) {self.res_in.name}_r = {self.res_in.name}.read();')
		outstr.close_bracket(1)
		return outstr

	def read_from_rf(self):
		outstr = IndentedString()
		for fifo in self.outputs:
			outstr.append(f'p_t data = rf_o[{self.get_rf_o_index()}];')
		return outstr

	def relu(self):
		outstr = IndentedString()
		self.append_if_else(if_str='data < 0', if_body='data = 0;', else_body=None, indent_str=outstr)
		return outstr

	def activation_function(self):
		return self.relu()
	
	def requantize(self):
		outstr = IndentedString()
		outstr.append('data = data >> 1;')
		outstr.append('o_t fp4_data = int5_to_fp4(data.to_ac_int());')
		return outstr

	def residual_add(self):
		outstr = IndentedString()
		ifbody = IndentedString()
		ifbody.append(f'o_t res_data = {self.res_in.name}_r[{self.get_rf_o_index()}];')
		ifbody.append('fp4_data = res_data + fp4_data;')
		self.append_if_else(if_str='RES_ADD_P', if_body=ifbody, else_body=None, indent_str=outstr)
		return outstr

	def set_single_word(self):
		outstr = IndentedString()
		for mem in self.outputs:
			outstr.append(f'{mem.name}_w[{self.get_rf_o_index()}] = fp4_data;')
		return outstr

	def post_process(self):
		outstr = IndentedString()
		ifstr = f'{self.rf_accum_end_if_str["t"]} && {self.rf_accum_end_if_str["s"]}'
		if_body = IndentedString()
		if_body.insert(self.read_from_rf())
		if_body.insert(self.activation_function())
		if_body.insert(self.requantize())
		if_body.insert(self.residual_add())
		if_body.insert(self.set_single_word())
		self.append_if_else(if_str=ifstr, if_body=if_body, else_body=None, indent_str=outstr)
		return outstr

	def gen_merged_loop_body(self):
		outstr = IndentedString()
		outstr.insert(self.read_from_fifo())
		if self.residual:
			outstr.insert(self.read_residual_connection())
		# spatial loops
		for loop in self.dims:
			self.append_for_loop_head(f'{loop}_s', 'COMPUTE', 'uint8_t', outstr)
		for t in self.tile_variable_definitions.values():
			outstr.append(t)
		outstr.append(define_i_xyz(xyz=self.xyz, postfix='s'))
		outstr.insert(self.get_single_word())
		outstr.insert(self.mult())
		outstr.insert(self.accum())
		outstr.insert(self.post_process())
		outstr.close_bracket(len(self.dims))
		outstr.insert(self.write_to_fifo())
		return outstr

	def gen_hls_body(self):
		outstr = IndentedString()
		outstr.insert(self.gen_merged_loop(loop_name=self.name.upper(), first_loop=True, loop_order=self.loop_order, loop_body=self.gen_merged_loop_body()))
		return outstr

	def gen_tcl_mem_mapping_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/rf_o:rsc', command='MAP_TO_MODULE', value='{[Register]}'))
		return outstr

	def gen_tcl_loop_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for loop, size in zip(self.dims, self.sizes):
			if size > 1:
				outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/COMPUTE_{loop.upper()}_S', command='UNROLL', value='yes'))
		outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/{self.name.upper()}', command='PIPELINE_INIT_INTERVAL', value=1))
		return outstr

	def gen_tcl_word_width_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for fifo in self.inputs:
			if fifo.type == 'data' or fifo.type == 'loadable':
				outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/COMPUTE:{fifo.name}_r.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
		for fifo in self.outputs:
			if fifo.type == 'data' or fifo.type == 'loadable':
				outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/COMPUTE:{fifo.name}_w.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
		return outstr
