from .hls_gen import HlsGenerator
from .catapult_fifo import CatapultConfFifo, CatapultDataFifo, CatapultHandshake, CatapultLoadableFifo
from .catapult_mac_array import CatapultMacArray
from .catapult_mem import CatapultMem
from .catapult_dma import CatapultLoad, CatapultStore
from .catapult_class import CatapultTopClass
from .catapult_config import CatapultConfig
from ..util.indented_str import IndentedString
from .hls_object import HlsArray

import os

class CatapultHlsGenerator(HlsGenerator):
	def __init__(self, config, output_path):
		super().__init__(config, FIFO_MAPPING, CLASS_MAPPING)
		self.catapult_binary = config['catapult']['binary']
		self.output_path = output_path
		self.tcl_path = f'{output_path}/build_prj.tcl'
		self.env_file = config['catapult']['env']

	def set_rtl_path(self):
		self.rtl_path = os.path.join(self.output_path, self.top_class, f'{self.top_class}.v1', 'concat_rtl.v')

	def include_libs(self):
		libstr = IndentedString()
		for lib in self.config['libraries']:
			libstr.append(f'#include <{lib}.h>')
		libstr.append('')
		return libstr

	def get_catapult_command(self, inst, command, value):
		if inst == '':
			inst_name = f'/{self.top_class}'
		else:
			inst_name = f'/{self.top_class}/{inst}'
		return f'directive set {inst_name} -{command} {value}'

	def gen_build_tcl(self):
		outstr = IndentedString()
		outstr.append(f'set VERIFY {self.config['catapult']['verify']}')
		outstr.append('options set Flows/SCVerify/USE_NCSIM true')
		outstr.append(f'project new -name {self.top_class}')
		outstr.append(f'solution file add {self.top_class}.h')
		# outstr.append('solution file add ../cpp/main.cpp')
		outstr.append('solution option set Output/OutputVHDL false')
		outstr.append('solution option set Output/OutputVerilog true')
		outstr.append('directive set -REGISTER_THRESHOLD 16384')
		outstr.append('go new')
		outstr.append('go analyze')
		outstr.append('go compile')
		outstr.append('if {$VERIFY == 1} { flow run /SCVerify/launch_make ./scverify/Verify_orig_cxx_osci.mk {} SIMTOOL=osci sim}')
		if 'path' in self.config['catapult']['libs']:
			outstr.append(f'solution options set ComponentLibs/SearchPath {self.config['catapult']['libs']['path']} -append')
		outstr.append(f'solution library add {self.config['catapult']['libs']['mem']} -- -rtlsyntool {self.config['catapult']['libs']['rtlsyntool']} -vendor {self.config['catapult']['libs']['vendor']} -technology {self.config['catapult']['libs']['technology']}')
		outstr.append(f'solution library add {self.config['catapult']['libs']['logic']}')
		outstr.append('go libraries')
		outstr.append(f'directive set -CLOCKS {{clk {{-CLOCK_PERIOD {self.config['clock_period']} -CLOCK_EDGE rising -CLOCK_HIGH_TIME {self.config['clock_period']//2} -CLOCK_OFFSET 0.000000 -CLOCK_UNCERTAINTY 0.0 -RESET_KIND sync -RESET_SYNC_NAME rst -RESET_SYNC_ACTIVE high -RESET_ASYNC_NAME arst_n -RESET_ASYNC_ACTIVE low -ENABLE_NAME {{}} -ENABLE_ACTIVE high}}}}')
		outstr.append('go assembly')
		# architecture specification for each block
		for fifo in self.fifos.values():
			if not isinstance(fifo.src, CatapultTopClass) and not isinstance(fifo.dst, CatapultTopClass):
				outstr.append(self.get_catapult_command(inst=f'{fifo.name}:cns', command='FIFO_DEPTH', value=0))
		for fifo in self.fifos.values():
			if isinstance(fifo.datatype, HlsArray):
				outstr.append(self.get_catapult_command(inst=f'{fifo.name}', command='WORD_WIDTH', value=fifo.datatype.bitwidth))
		for block in self.classes.values():
			outstr.insert(block.gen_tcl_commands(self.get_catapult_command))
		outstr.append('directive set -CLOCK_OVERHEAD 0')
		outstr.append('go architect')
		outstr.append('go allocate')
		outstr.append('go extract')
		outstr.append('if {$VERIFY == 1} { flow run /SCVerify/launch_make ./scverify/Verify_concat_sim_rtl_v_ncsim.mk {} SIMTOOL=ncsim sim}')
		outstr.append('project save')
		return outstr

	def synthesize(self):
		command = f'source {self.env_file};'
		command += f'cd {self.output_path};'
		command += f'{self.catapult_binary} -product ultra -shell -f {self.tcl_path}'
		os.system(command)
		self.postprocess_srams()

	def postprocess_srams(self):

		def count_leading_spaces(text):
   			return len(text) - len(text.lstrip())

		memories = self.get_memories()
		with open(self.rtl_path, 'r+') as f:
			orig = f.readlines()
			new = []
			relevant_module = False
			cur_mem = None
			cnt = 0
			for line in orig:
				if 'module ' in line:
					for mem in memories:
						if f'{mem.name} ' in line:
							relevant_module = True
							cur_mem = mem
							break
				if 'endmodule' in line:
					relevant_module = False
				if not relevant_module:
					new += [line]
					continue
				catapult_mem_name = cur_mem.config['catapult_mem_mapping'].split('.')[-1]
				if catapult_mem_name in line:
					cnt = 3
				if cnt > 0:
					if cnt == 1:
						leading_spaces = ' ' * count_leading_spaces(line)
						inst_name = line[:-1].split(' ')[-2]
						new_line = leading_spaces + mem.verilog_name + ' ' + inst_name + ' (\n'
						new += [new_line]
					cnt -= 1
				else:
					new += [line]
			f.seek(0)
			f.writelines(new)
			f.truncate()


FIFO_MAPPING = {
	"loadable": CatapultLoadableFifo,
	"data": CatapultDataFifo,
	"conf": CatapultConfFifo,
	"handshake": CatapultHandshake
}

CLASS_MAPPING = {
	"top": CatapultTopClass,
	"compute": CatapultMacArray,
	"mem": CatapultMem,
	"load": CatapultLoad,
	"store": CatapultStore,
	"config": CatapultConfig,
}