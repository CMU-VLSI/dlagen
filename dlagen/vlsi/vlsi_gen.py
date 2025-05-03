from .sram_mapper import SramMapper
from .sram import TsmcSramLib
from .hammer_gen import HammerGenerator

class VlsiGenerator():
	def __init__(self, config, output_path):
		self.sram_lib = {}
		for lib in config['sram']['library']:
			self.sram_lib[lib['name']] = TsmcSramLib(lib)
		self.mapper = SramMapper(config['sram']['macro'], self.sram_lib)
		self.output_path = output_path

		self.hammer_gen = HammerGenerator(config['hammer'], output_path)

	def build(self, hls_mem, design_name, area, rtl_path):
		self.macro_dict = {}
		for m in hls_mem:
			assert len(m.mem_datatype.params) == 2, "Only 2D memory arrays are supported!"

			name = m.verilog_name
			if name not in self.macro_dict:
				self.macro_dict[name] = self.mapper.map(name, m.mem_type, m.width, m.depth, self.output_path)
		self.hammer_gen.build(self.macro_dict, design_name, area, rtl_path)

	def synthesize(self):
		self.mapper.compile(self.macro_dict.values(), self.output_path)
		self.hammer_gen.synthesize()
