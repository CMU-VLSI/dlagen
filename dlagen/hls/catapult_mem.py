from ..util.indented_str import IndentedString
from .catapult_class import CatapultClass, CatapultSubClass, CatapultParentClass
from .hls_object import HlsConf, HlsVar, HlsArray
from .catapult_fifo import CatapultFifo, CatapultDataFifo, CatapultMemFifo
from .util import define_i_xyz, make_unique_loop_order, get_addr_from_loop_list, update_loop_order_subset_from_unique_loop_order

class CatapultMemBlock(CatapultSubClass):
	def __init__(self, config, output, func_name, ping_pong, word_datatype, mem_datatype):
		self.addressible = config['addressible']
		self.programmable = config['programmable']
		self.ping_pong = ping_pong
		self.num_incr = config['num_incr'] if 'num_incr' in config else 0
		self.num_repeat = config['num_repeat'] if 'num_repeat' in config else 0

		if self.addressible and not self.programmable:
			compute_loop_order = make_unique_loop_order(config['compute_loop_order'])
			self.loop_order = config['loop_order']
			updated_names, self.tile_variable_definitions = update_loop_order_subset_from_unique_loop_order([loop[0] for loop in self.loop_order], compute_loop_order)
			self.loop_order = [(updated_names[i], self.loop_order[i][1]) for i in range(len(self.loop_order))]
			self.mem_order, _ = update_loop_order_subset_from_unique_loop_order(config['mem_order'], compute_loop_order)

		super().__init__(config, func_name)
		self.output = output
		self.word_datatype = word_datatype
		self.mem_datatype = mem_datatype

		self.mem_tmp_name = f'{func_name}_mem_tmp'

		if self.output:
			self.channel_name = [fifo.name for fifo in self.outputs if isinstance(fifo, CatapultDataFifo) or isinstance(fifo, CatapultLoadableFifo)][0]
		else:
			self.channel_name = [fifo.name for fifo in self.inputs if isinstance(fifo, CatapultDataFifo) or isinstance(fifo, CatapultLoadableFifo)][0]

	def gen_programmable_mem_loops(self, loop_name_prefix, num_repeat, num_incr, first_loop, loop_body):
		outstr = IndentedString()
		var_init_str = 'uint16_t address'
		addr_str = 'address = '
		for i in range(num_incr):
			var_init_str += f', start{i}'
			addr_str += f'start{i}'
			if i != num_incr - 1:
				addr_str += ' + '
		var_init_str += ';'
		addr_str += ';'
		if first_loop:
			outstr.append(var_init_str)
		cnt_repeat = 1
		cnt_incr = 0
		loop_list = []
		while True:
			if cnt_incr < num_incr:
				loop_list += [(cnt_incr, 'incr')]
				cnt_incr += 1
			if cnt_repeat < num_repeat+1:
				loop_list += [(cnt_repeat, 'repeat')]
				cnt_repeat += 1
			if cnt_repeat >= num_repeat and cnt_incr >= num_incr:
				break
		reversed_list = loop_list[::-1]
		for loop in loop_list:
			self.append_for_loop_head(f't{loop[0]}_{loop[1]}', loop_name_prefix, 'uint16_t', outstr)
			if loop[1] == 'repeat':
				outstr.append(f'start{loop[0]} = OFFSET{loop[0]};')
		outstr.append(addr_str)
		outstr.insert(loop_body)
		for loop in reversed_list:
			if loop[1] == 'incr':
				outstr.append(f'start{loop[0]} += T{loop[0]}_STRIDE;')
			outstr.close_bracket(1)
		return outstr

	def gen_addressible_intf_body(self, programmable):
		outstr = IndentedString()
		if programmable:
			addr_str = 'address'
		else:
			addr_str = get_addr_from_loop_list(self.mem_order)
		for t in self.tile_variable_definitions.values():
			outstr.append(t)
		if 'xyz' in self.config:
			for cur_xyz in self.config['xyz']:
				outstr.append(define_i_xyz(xyz=cur_xyz, postfix='t'))
		if self.output:
			outstr.append(f'{self.word_datatype.name} data = {self.mem_tmp_name}[{addr_str}];')
			outstr.append(f'{self.channel_name}.write(data);')
		else:
			outstr.append(f'{self.word_datatype.name} data = {self.channel_name}.read();')
			outstr.append(f'{self.mem_tmp_name}[{addr_str}] = data;')
		return outstr

	def gen_sequential_intf_body(self, pp_idx):
		outstr = IndentedString()
		outstr.append_fixed_indent(f'{self.name.upper()}_SRAM_{pp_idx}:')
		outstr.append_and_indent('for (uint16_t sram = 0; sram < SRAM_T_P; sram++) {')
		if self.output:
			outstr.append(f'{self.word_datatype.name} data = {self.mem_tmp_name}[sram];')
			outstr.append(f'{self.channel_name}.write(data);')
		else:
			outstr.append(f'{self.word_datatype.name} data = {self.channel_name}.read();')
			outstr.append(f'{self.mem_tmp_name}[sram] = data;')
		outstr.close_bracket(1)
		return outstr

	def gen_mem_intf(self, addressible):
		outstr = IndentedString()
		outstr.append_fixed_indent(f'{self.name.upper()}_DRAM:')
		outstr.append_and_indent('for (uint8_t dram = 0; dram < DRAM_T_P; dram++) {')
		mem_str = 'ping_tmp, pong_tmp' if self.ping_pong and self.programmable and addressible else self.mem_tmp_name
		outstr.append(f'{self.mem_datatype.name} {mem_str};')
		if self.programmable and addressible:
			self.append_for_loop_head(loop_name='t0_repeat', name_prefix=f'{self.name.upper()}_SRAM', datatype='uint16_t', indent_str=outstr)
			outstr.append('start0 = OFFSET0;')
		pp = 2 if self.ping_pong else 1
		for i in range(pp):
			if not self.ping_pong:
				mem_name = 'mem'
			else:
				if i == 0:
					mem_name = 'ping'
				else:
					mem_name = 'pong'
			if self.output:
				if addressible and self.programmable:
					outstr.append(f'if (t0_repeat == 0) {mem_name}_tmp = {mem_name}.read();')
				else:
					outstr.append(f'{self.mem_tmp_name} = {mem_name}.read();')
			if addressible:
				if self.programmable:
					outstr.insert(self.gen_programmable_mem_loops(loop_name_prefix=f'{self.name.upper()}_SRAM_{i}', num_repeat=self.num_repeat-1, num_incr=self.num_incr, first_loop=(i==0), loop_body=self.gen_addressible_intf_body(self.programmable)))
				else:
					outstr.insert(self.gen_merged_loop(loop_name=f'{self.name.upper()}_SRAM_{i}', first_loop=(i==0), loop_order=self.loop_order, loop_body=self.gen_addressible_intf_body(self.programmable)))
			else:
				outstr.insert(self.gen_sequential_intf_body(pp_idx=i))
			if not self.output:
				outstr.append(f'{mem_name}.write({self.mem_tmp_name});')
		outstr.close_bracket(2 if self.programmable else 1)
		return outstr

	def get_sequential_intf_conf(self):
		conf_list = [
			HlsConf(name='SRAM_T_P', type='uint16_t'),
			HlsConf(name='DRAM_T_P', type='uint8_t')
		]
		global_conf_list = [HlsConf(name=f'{self.name.upper()}_{self.func_name.upper()}_{c.name}', type=c.type) for c in conf_list]
		return conf_list, global_conf_list

	def get_addressible_intf_conf(self):
		conf_list = [HlsConf(name='DRAM_T_P', type='uint8_t')]
		if self.programmable:
			for i in range(self.num_incr):
				conf_list += [HlsConf(name=f'T{i}_INCR', type='uint16_t')]
				conf_list += [HlsConf(name=f'T{i}_STRIDE', type='uint16_t')]
				conf_list += [HlsConf(name=f'OFFSET{i}', type='uint16_t')]
			for i in range(self.num_repeat):
				conf_list += [HlsConf(name=f'T{i}_REPEAT', type='uint16_t')]
			global_conf_list = [HlsConf(name=f'{self.name.upper()}_{self.func_name.upper()}_{c.name}', type=c.type) for c in conf_list]
		else:
			## the order matters here because of catapult_config.py, which is not a very good design...
			if 'xyz' in self.config:
				for cur_xyz in self.config['xyz']:
					conf_list += [HlsConf(name=f'I{cur_xyz.upper()}_P', type='uint16_t')]
				conf_list += [HlsConf(name='STRIDE_P', type='ac_int<2, false>')]
			for loop in self.loop_order:
				conf_list += [HlsConf(name=f'{loop[0].upper()}_P', type='uint8_t' if loop[1] < 2**8 else 'uint16_t')]
			global_conf_list = [HlsConf(name=f'{self.name.upper()}_{self.func_name.upper()}_DRAM_T_P', type='uint8_t')]
			if 'xyz' in self.config:
				for cur_xyz in self.config['xyz']:
					global_conf_list += [HlsConf(name=f'I{cur_xyz.upper()}_P', type='uint16_t')]
		return conf_list, global_conf_list

	def setup_conf_list(self):
		if self.addressible:
			self.conf_list, self.global_conf_list = self.get_addressible_intf_conf()
		else:
			self.conf_list, self.global_conf_list = self.get_sequential_intf_conf()

	def setup_var_list(self):
		self.var_list = []
		if 'xyz' in self.config:
			for cur_xyz in self.config['xyz']:
				self.var_list += [HlsVar(name=f'i{cur_xyz}', type='uint16_t')]

	def gen_hls_body(self):
		return self.gen_mem_intf(self.addressible)

	def gen_tcl_word_width_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		mem_tmp_cnt = 0
		for fifo in self.top_channel_list:
			if isinstance(fifo.datatype, HlsArray):
				outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.class_name}::{self.func_name}/{fifo.name}', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
				if len(fifo.datatype.params) == 2:
					if self.ping_pong:
						if self.programmable and self.addressible:
							outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.class_name}::{self.func_name}/{self.name.upper()}_DRAM:{fifo.name}_tmp.d.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
						elif mem_tmp_cnt == 0:
							outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.class_name}::{self.func_name}/{self.name.upper()}_DRAM:{self.mem_tmp_name}.d.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
							mem_tmp_cnt += 1
					else:
						outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.class_name}::{self.func_name}/{self.name.upper()}_DRAM:{self.mem_tmp_name}.d.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
				elif not self.output:
					outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.class_name}::{self.func_name}/{self.name.upper()}_SRAM_0:data.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
					if self.ping_pong:
						outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.class_name}::{self.func_name}/{self.name.upper()}_SRAM_1:data.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
					
		return outstr

	def gen_tcl_loop_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.class_name}::{self.func_name}/core/{self.name.upper()}_DRAM', command='PIPELINE_INIT_INTERVAL', value=1))
		return outstr

class CatapultMem(CatapultParentClass):
	def __init__(self, config):
		super().__init__(config)
		config['in']['conf_fifo'] = [i for i in self.conf_fifo if i.name == config['in']['conf_fifo']]
		config['out']['conf_fifo'] = [i for i in self.conf_fifo if i.name == config['out']['conf_fifo']]
		self.word_datatype = config['datatype']
		self.ping_pong = config['ping_pong']
		self.depth = config['depth'] // 2 if self.ping_pong else config['depth']
		self.mem_type = self.config['mem_type']
		self.mem_datatype = HlsArray({'name': self.name, 'type': self.word_datatype.type, 'params': [self.depth, self.word_datatype.params[0]]})
		
		self.width = self.word_datatype.params[0] * self.word_datatype.type.params[0]
		self.verilog_name = f'{self.mem_type}ram{self.depth}x{self.width}'

		self.definitions = [self.mem_datatype]

		if self.ping_pong:
			self.mem_channels = [CatapultMemFifo({'name': 'ping', 'type': 'data', 'datatype': self.mem_datatype}), 
				CatapultMemFifo({'name': 'pong', 'type': 'data', 'datatype': self.mem_datatype})]
		else:
			self.mem_channels = [CatapultMemFifo({'name': 'mem', 'type': 'data', 'datatype': self.mem_datatype})]
		config['in']['inputs'] = config['inputs']
		config['in']['outputs'] = self.mem_channels
		config['in']['name'] = config['name']
		config['out']['inputs'] = self.mem_channels
		config['out']['outputs'] = config['outputs']
		config['out']['name'] = config['name']
		self.inblock = CatapultMemBlock(config['in'], output=False, func_name='in', ping_pong=self.ping_pong,
			word_datatype=self.word_datatype, mem_datatype=self.mem_datatype)
		self.outblock = CatapultMemBlock(config['out'], output=True, func_name='out', ping_pong=self.ping_pong,
			word_datatype=self.word_datatype, mem_datatype=self.mem_datatype)

	def setup_private_var_list(self):
		self.private_var_list = []
		for mem in self.mem_channels:
			self.private_var_list += [HlsVar(name=mem.name, type=mem.channel_name)]

	def gen_hls_sub_functions(self):
		outstr = IndentedString()
		outstr.insert(self.inblock.gen_hls())
		outstr.insert(self.outblock.gen_hls())
		return outstr

	def gen_hls_body(self):
		outstr = IndentedString()
		outstr.insert(self.inblock.gen_func_call())
		outstr.insert(self.outblock.gen_func_call())
		return outstr

	def gen_tcl_word_width_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for fifo in self.mem_channels:
			outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{fifo.name}', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
		outstr.insert(self.inblock.gen_tcl_word_width_commands(get_catapult_command_fn))
		outstr.insert(self.outblock.gen_tcl_word_width_commands(get_catapult_command_fn))
		return outstr

	def gen_tcl_mem_mapping_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for fifo in self.mem_channels:
			outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{fifo.name}:cns', command='MAP_TO_MODULE', value=self.config['catapult_mem_mapping']))
			outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{fifo.name}:cns', command='STAGE_REPLICATION', value=1))
		return outstr

	def gen_tcl_loop_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		outstr.insert(self.inblock.gen_tcl_loop_commands(get_catapult_command_fn))
		outstr.insert(self.outblock.gen_tcl_loop_commands(get_catapult_command_fn))
		return outstr