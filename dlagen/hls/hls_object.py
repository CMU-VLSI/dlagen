from abc import ABC
from ..util.indented_str import IndentedString

class HlsObject(ABC):
	def __init__(self, name=None, type=None, params=None):
		self.name = name
		self.type = type
		self.params = params

class HlsConf(HlsObject):
	def __init__(self, name=None, type=None, params=None):
		super().__init__(name, type, params)

	def __str__(self):
		return f'{self.type} {self.name} = conf_tmp.{self.name};'

class HlsVar(HlsObject):
	def __init__(self, name=None, type=None, params=None):
		super().__init__(name, type, params)

	def __str__(self):
		if self.params:
			end = f' = {self.params};'
		else:
			end = ';'
		return f'{self.type} {self.name}{end}'

class HlsDef(HlsObject):
	def __init__(self, name=None, type=None, params=None):
		super().__init__(name, type, params)
		if self.type == '':
			delim = ''
		else:
			delim = '_'
		self.def_name = f'{self.name}{delim}{self.type}'

	def __str__(self):
		return f'#define {self.def_name} {self.params}'

class HlsDatatype(HlsObject):
	def __init__(self, config):
		super().__init__(f'{config['name']}_t', config['type'], config['params'])

		self.raw_name = config['name']

		if self.type == 'ac_int':
			assert len(self.params) == 2
			self.definitions = [HlsDef(config['name'].upper(), 'BITWIDTH', self.params[0])]
		elif self.type == 'ac_fixed':
			assert len(self.params) == 3
			self.definitions = [HlsDef(config['name'].upper(), 'BITWIDTH', self.params[0])]
			self.definitions += [HlsDef(config['name'].upper(), 'BITWIDTH_W', self.params[0])]
			self.definitions += [HlsDef(config['name'].upper(), 'BITWIDTH_I', self.params[1])]
		else:
			raise Exception('Hls Datatype not supported')

	def gen_definition(self):
		def_str = IndentedString()
		for d in self.definitions:
			def_str.append(str(d))
		param_str = ''
		for p in self.params:
			param_str += f'{p}, '
		def_str.append(f'typedef {self.type}<{param_str[:-2]}> {self.name};')
		return def_str

class HlsStruct(HlsObject):
	def __init__(self, config):
		super().__init__(f'{config['name']}_t', None, config['params'])

	def gen_definition(self):
		def_str = IndentedString()

		def_str.append(f'struct {self.name} {{')
		def_str.indent()
		for field in self.params:
			def_str.append(f'{field[1]} {field[0]};')
		def_str.unindent()
		def_str.append('};')
		return def_str

class HlsArray(HlsObject):
	def __init__(self, config):
		super().__init__(f'{config['name']}_t', config['type'], config['params'])
		self.reshape_dims = config['reshape_dims'] if 'reshape_dims' in config else None

		assert len(self.params) < 3, "Maximum array dimensions supported is 2!"
		self.definitions = [HlsDef(config['name'].upper(), 'WIDTH', self.params[-1])]
		self.bitwidth = self.type.params[0] * self.params[-1]
		if len(self.params) > 1:
			self.definitions += [HlsDef(config['name'].upper(), 'DEPTH', self.params[-2])]

	def gen_definition(self):
		def_str = IndentedString()
		for d in self.definitions:
			def_str.append(str(d))
		param_str = f'{self.type.name}, '
		for p in self.params:
			param_str += f'{p}, '
		def_str.append(f'typedef ac_array<{param_str[:-2]}> {self.name};')
		return def_str