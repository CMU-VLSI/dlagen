import enum
from functools import total_ordering
import os

from ..util.indented_str import IndentedString

@total_ordering
class MemType(enum.Enum):
	
	sp = 1
	r1w1 = 2
	dp = 3

	def __lt__(self, other):
		if self.__class__ is other.__class__:
			return self.value < other.value
		return NotImplemented

	def __le__(self, other):
		if self.__class__ is other.__class__:
			return self.value <= other.value
		return NotImplemented

	def __ge__(self, other):
		if self.__class__ is other.__class__:
			return self.value >= other.value
		return NotImplemented

	def __gt__(self, other):
		if self.__class__ is other.__class__:
			return self.value > other.value
		return NotImplemented

class SramLib():

	def __init__(self, config):
		self.config = config
		self.name = config['name']
		self.type = MemType[config['type']]
		self.verilog_path = f'f"{config['verilog_path']}"'
		self.module = f'f"{config['module']}"'
		self.timing_path = f'f"{config['timing_path']}"'
		self.lef_path = f'f"{config['lef_path']}"'
		self.gds_path = f'f"{config['gds_path']}"'
		self.spice_path = f'f"{config['spice_path']}"'
		self.ports = config['ports']

class TsmcSramLib(SramLib):

	def __init__(self, config):
		super().__init__(config)
		self.compiler_script = config['compiler']['script']
		self.compiler_config_format = config['compiler']['config_format']

	def compile(self, cm, width, depth, output_path):
		with open(os.path.join(output_path, 'config.txt'), 'w') as f:
			c_str = eval(self.compiler_config_format)
			f.write(f'{c_str}\n')
		command = f'cp {self.compiler_script} {output_path};'
		command += f'cd {output_path};'
		command += f'tcsh {os.path.basename(self.compiler_script)};'
		return c_str, command

class SramMacro():

	def __init__(self, lib, cm, width, depth):
		self.name = f'{lib.name}_{depth}x{width}_cm{cm}'
		self.lib = lib
		self.cm = cm
		self.width = width
		self.depth = depth
		self.verilog_path = eval(self.lib.verilog_path)
		self.module = eval(self.lib.module)
		self.timing_path = eval(self.lib.timing_path)
		self.lef_path = eval(self.lib.lef_path)
		self.gds_path = eval(self.lib.gds_path)
		self.spice_path = eval(self.lib.spice_path)

	def compile(self, output_path):
		return self.lib.compile(self.cm, self.width, self.depth, output_path)

	def gen_verilog_inst(self, inst_name, width_range=None, addr_range=None):
		outstr = IndentedString()
		outstr.append(f'{self.module} mem_{inst_name} (')
		outstr.indent()
		ports_str = ''
		for p_rtl, p_sram in self.lib.ports.items():
			if p_rtl == 'specific':
				for p in p_sram:
					ports_str += f'.{p[0]}({p[1]}), '
			elif p_rtl == 'd' and width_range:
				ports_str += f'.{p_sram}({p_rtl}[{width_range}]), '
			elif p_rtl == 'q' and (width_range or addr_range):
				ports_str += f'.{p_sram}(q_{inst_name}), '
			elif p_rtl == 'adr' and addr_range:
				ports_str += f'.{p_sram}({p_rtl}[{addr_range}]), '
			elif ('en' in p_rtl or 'we' in p_rtl) and addr_range:
				ports_str += f'.{p_sram}({p_rtl}_{inst_name}), '
			else:
				ports_str += f'.{p_sram}({p_rtl}), '
		outstr.append(ports_str[:-2])
		outstr.unindent()
		outstr.append(");")
		return outstr
