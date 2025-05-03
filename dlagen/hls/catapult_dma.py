from ..util.indented_str import IndentedString
from .catapult_class import CatapultClass
from .hls_object import HlsConf, HlsVar, HlsDef

class CatapultLoad(CatapultClass):
	def __init__(self, config):
		super().__init__(config)

	def setup_definitions(self):
		self.definitions = []
		for fifo in self.outputs:
			if fifo.type == 'loadable':
				self.definitions += [
					HlsDef(name=f'DMA_NUM_{fifo.name.upper()}_PER_ACCESS',
						type='', params=f'(DMA_DATA_BITWIDTH/{fifo.datatype.type.definitions[0].def_name})'
						)
				]

	def setup_conf_list(self):
		self.conf_list = []
		self.load_multiple_times = False
		for fifo in self.outputs:
			if fifo.type == 'loadable':
				self.conf_list += fifo.conf_list
				if not fifo.load_once:
					self.load_multiple_times = True
		if self.load_multiple_times:
			self.conf_list += [HlsConf(name='LOAD_T1', type='uint8_t'), HlsConf(name='LOAD_T2', type='uint8_t')]
		self.global_conf_list = self.conf_list

	def setup_var_list(self):
		self.var_list = [
			HlsVar(name='dma_data_index', type='uint32_t'),
			HlsVar(name='dma_data_length', type='uint16_t'),
			HlsVar(name='width_cnt', type='uint16_t', params=0),
			HlsVar(name='dma_info', type='dma_info_t'),
			HlsVar(name='dma_ctrl_done', type='bool', params='false'),
			HlsVar(name='load_prev_flag', type='bool', params='false')
		]
		for fifo in self.outputs:
			if fifo.type == 'loadable':
				self.var_list = [*self.var_list, *fifo.get_var_list()]

	def gen_hls_body(self):
		loadblock_str = IndentedString()
		# load once
		for fifo in self.outputs:
			if fifo.type == 'loadable' and fifo.load_once:
				loadblock_str.insert(fifo.gen_load())
		# load multiple times
		if self.load_multiple_times:
			loadblock_str.append_fixed_indent('T1:')
			loadblock_str.append_and_indent('for (uint8_t t1 = 0; t1 < LOAD_T1; t1++) {')
			loadblock_str.append_fixed_indent('T2:')
			loadblock_str.append_and_indent('for (uint8_t t2 = 0; t2 < LOAD_T2; t2++) {')
			for idx, fifo in enumerate(self.outputs):
				if fifo.type == 'loadable' and not fifo.load_once:
					else_str = 'else ' if idx != 0 else ''
					loadblock_str.append_and_indent(f'{else_str}if ((t2 >= {fifo.name.upper()}_START_ITER) && (t2 < {fifo.name.upper()}_END_ITER)) {{')
					loadblock_str.insert(fifo.gen_load())
					loadblock_str.close_bracket(1)
			loadblock_str.close_bracket(2)
		return loadblock_str

	def gen_tcl_loop_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for fifo in self.outputs:
			if fifo.type == 'loadable':
				outstr.insert(fifo.gen_tcl_loop_commands(f'{self.class_name}/{self.func_name}', get_catapult_command_fn))
		if self.load_multiple_times:
			outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/T1', command='PIPELINE_INIT_INTERVAL', value=1))
		return outstr

	def gen_tcl_word_width_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for fifo in self.outputs:
			if fifo.type == 'loadable':
				for v in fifo.get_var_list():
					outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/{v.name}.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
		return outstr

class CatapultStore(CatapultClass):
	def __init__(self, config):
		super().__init__(config)

	def setup_definitions(self):
		self.definitions = []
		for fifo in self.inputs:
			if fifo.type == 'loadable':
				self.definitions += [
					HlsDef(name=f'DMA_NUM_{fifo.name.upper()}_PER_ACCESS',
						type='', params=f'(DMA_DATA_BITWIDTH/{fifo.datatype.type.definitions[0].def_name})'
						)
				]

	def setup_conf_list(self):
		self.conf_list = []
		self.load_multiple_times = False
		for fifo in self.inputs:
			if fifo.type == 'loadable':
				self.conf_list += fifo.conf_list
		self.conf_list += [HlsConf(name='STORE_DRAM_O_P', type='uint8_t'), HlsConf(name='STORE_SRAM_O_P', type='uint16_t')]
		self.global_conf_list = self.conf_list

	def setup_var_list(self):
		self.var_list = [
			HlsVar(name='dma_data_index', type='uint32_t'),
			HlsVar(name='dma_data_length', type='uint16_t'),
			HlsVar(name='width_cnt', type='uint16_t', params=0),
			HlsVar(name='depth_cnt', type='uint16_t', params=0),
			HlsVar(name='dma_info', type='dma_info_t'),
			HlsVar(name='dma_ctrl_done', type='bool', params='false'),
		]
		for fifo in self.inputs:
			if fifo.type == 'loadable':
				self.var_list = [*self.var_list, *fifo.get_var_list()]

	def gen_hls_body(self):
		storeblock_str = IndentedString()
		storeblock_str.append_fixed_indent('DRAM_O:')
		storeblock_str.append_and_indent('for (uint8_t dram_o = 0; dram_o < STORE_DRAM_O_P; dram_o++) {')
		for fifo in self.inputs:
			if fifo.type == 'loadable':
				storeblock_str.insert(fifo.gen_load())
		storeblock_str.close_bracket(1)
		return storeblock_str

	def gen_tcl_loop_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for fifo in self.inputs:
			if fifo.type == 'loadable':
				outstr.insert(fifo.gen_tcl_loop_commands(f'{self.class_name}/{self.func_name}', get_catapult_command_fn))
		outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/DRAM_O', command='PIPELINE_INIT_INTERVAL', value=1))
		return outstr

	def gen_tcl_word_width_commands(self, get_catapult_command_fn):
		outstr = IndentedString()
		for fifo in self.inputs:
			if fifo.type == 'loadable':
				for v in fifo.get_var_list():
					outstr.append(get_catapult_command_fn(inst=f'{self.class_name}/{self.func_name}/{v.name}.d', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
		return outstr
