from ..util.indented_str import IndentedString
from .hls_object import HlsConf, HlsDef, HlsStruct, HlsVar

class CatapultFifo():
	def __init__(self, config):
		self.name = config['name']
		self.type = config['type']

	@property
	def src(self):
		return self._src

	@src.setter
	def src(self, src):
		self._src = src

	@property
	def dst(self):
		return self._dst

	@dst.setter
	def dst(self, dst):
		self._dst = dst

class CatapultConfFifo(CatapultFifo):
	def __init__(self, config):
		super().__init__(config)
		self.datatype = f'{self.name}_t'
		self.channel_name = f'ac_channel<{self.datatype}>'

	@property
	def conf_list(self):
		return self._conf_list
	
	@conf_list.setter
	def conf_list(self, conf_list):
		self._conf_list = conf_list

	@property
	def global_conf_list(self):
		return self._global_conf_list
	
	@global_conf_list.setter
	def global_conf_list(self, global_conf_list):
		self._global_conf_list = global_conf_list

	def gen_definition(self):
		conf_def_struct = HlsStruct({
				'name': self.name,
				'params': [[conf.name, conf.type] for conf in self.conf_list]
			})
		outstr = IndentedString()
		outstr.insert(conf_def_struct.gen_definition())
		return outstr

class CatapultDataFifo(CatapultFifo):
	def __init__(self, config):
		super().__init__(config)
		self.datatype = config['datatype']
		self.channel_name = f'ac_channel<{self.datatype.name}>'

class CatapultMemFifo(CatapultDataFifo):
	def __init__(self, config):
		super().__init__(config)

class CatapultLoadableFifo(CatapultDataFifo):
	def __init__(self, config):
		super().__init__(config)
		self.load_once = config['load_once'] if 'load_once' in config else False
		self.output = config['output'] if 'output' in config else False

		self.setup_conf_list()

	def setup_conf_list(self):
		self.conf_list = [
			HlsConf(name=f'DMA_LENGTH_{self.name.upper()}', type='uint16_t'),
			HlsConf(name=f'DMA_{self.name.upper()}_START_ADDR', type='uint32_t')
		]
		if not self.load_once and not self.output:
			self.conf_list += [
				HlsConf(name=f'{self.name.upper()}_START_ITER', type='uint8_t'),
				HlsConf(name=f'{self.name.upper()}_END_ITER', type='uint8_t')
			]

	def get_var_list(self):
		prev_or_next_str = 'next' if self.output else 'prev'
		return [HlsVar(name=f'{self.name}_word', type=self.datatype.name), 
			HlsVar(name=f'{self.name}_word_{prev_or_next_str}', type=self.datatype.name)]

	def gen_load(self):
		if self.output:
			mem = self.src
		else:
			mem = self.dst
		outstr = IndentedString()
		outstr.append(f'dma_data_length = DMA_LENGTH_{self.name.upper()};')
		if self.load_once:
			index_str = ''
		else:
			if self.output:
				iter_str = 'dram_o'
			else:
				iter_str = f't1 * ({self.name.upper()}_END_ITER - {self.name.upper()}_START_ITER) + t2 - {self.name.upper()}_START_ITER'
			index_str = f' + ({iter_str}) * dma_data_length'
		outstr.append(f'dma_data_index = DMA_{self.name.upper()}_START_ADDR{index_str};') 
		outstr.append('dma_info = {dma_data_index, dma_data_length};')
		outstr.append('dma_ctrl_done = false;')
		outstr.append_fixed_indent(f'CTRL_{self.name.upper()}:')
		rw_str = 'write' if self.output else 'read'
		outstr.append(f'do {{ dma_ctrl_done = dma_{rw_str}_ctrl.nb_write(dma_info); }} while (!dma_ctrl_done);')
		if self.output:
			outstr.append(f'{self.name}_word = {self.name}.read();')
		outstr.append_and_indent('if (dma_ctrl_done) {')
		outstr.append_fixed_indent(f'{self.name.upper()}:')
		outstr.append_and_indent('for (uint16_t i = 0; i < dma_data_length; i++) {')
		if not self.output:
			outstr.append_fixed_indent('#ifndef __SYNTHESIS__')
			outstr.append('while (!dma_read_chnl.available(1)) {};')
			outstr.append_fixed_indent('#endif')
		data_ac_assign_str = '' if self.output else ' = dma_read_chnl.read()'
		outstr.append(f'dma_data_t data_ac{data_ac_assign_str};')
		outstr.append_fixed_indent(f'UNROLL_{self.name.upper()}:')
		outstr.append_and_indent(f'for (uint8_t k = 0; k < DMA_NUM_{self.name.upper()}_PER_ACCESS; k++) {{')
		if self.output:
			outstr.append(f'{self.datatype.type.name} data;')
			outstr.append_and_indent(f'if ((width_cnt+k) < {self.datatype.params[0]}) {{')
			outstr.append(f'data = {self.name}_word[width_cnt+k];')
			outstr.unindent()
			outstr.append_and_indent('} else {')
			outstr.append(f'data = {self.name}_word_next[width_cnt+k];')
			outstr.close_bracket(1)
			outstr.append(f'data_ac.set_slc({self.datatype.type.definitions[0].def_name}*k, data);')
			outstr.close_bracket(1)
			outstr.append(f'width_cnt += DMA_NUM_{self.name.upper()}_PER_ACCESS;')
			outstr.append_and_indent(f'if (width_cnt >= {self.datatype.params[0]}) {{')
			outstr.append(f'{self.name}_word = {self.name}_word_next;')
			outstr.append(f'width_cnt -= {self.datatype.params[0]};')
			outstr.close_bracket(1)
			outstr.append_and_indent(f'if (width_cnt + DMA_NUM_{self.name.upper()}_PER_ACCESS >= {self.datatype.params[0]}) {{')
			outstr.append('depth_cnt += 1;')
			outstr.append(f'if (depth_cnt < STORE_SRAM_O_P) {self.name}_word_next = {self.name}.read();')
			outstr.close_bracket(1)
			outstr.append('dma_write_chnl.write(data_ac);')
			outstr.close_bracket(2)
			outstr.append('width_cnt = 0;')
			outstr.append('depth_cnt = 0;')
		else:
			outstr.append(f'{self.name}_word[width_cnt] = data_ac.template slc<{self.datatype.type.definitions[0].def_name}>(k*{self.datatype.type.definitions[0].def_name});')
			outstr.append('width_cnt += 1;')
			outstr.append_and_indent(f'if (width_cnt == {self.datatype.definitions[0].def_name}) {{')
			outstr.append(f'{self.name}_word_prev = {self.name}_word;')
			outstr.append('width_cnt = 0;')
			outstr.append('load_prev_flag = true;')
			outstr.close_bracket(2)
			outstr.append_and_indent('if (load_prev_flag) {')
			outstr.append(f'{self.name}.write({self.name}_word_prev);')
			outstr.append('load_prev_flag = false;')
			outstr.close_bracket(3)
			outstr.append('width_cnt = 0;')
		return outstr

	def gen_tcl_loop_commands(self, class_name, get_catapult_command_fn):
		outstr = IndentedString()
		outstr.append(get_catapult_command_fn(inst=f'{class_name}/{self.name.upper()}', command='PIPELINE_INIT_INTERVAL', value=1))
		outstr.append(get_catapult_command_fn(inst=f'{class_name}/UNROLL_{self.name.upper()}', command='UNROLL', value='yes'))
		return outstr

class CatapultHandshake(CatapultFifo):
	def __init__(self, config):
		super().__init__(config)
		self.datatype = 'ac_sync'