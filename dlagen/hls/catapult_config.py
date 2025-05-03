from ..util.indented_str import IndentedString
from .catapult_class import CatapultClass
from .hls_object import HlsConf, HlsVar

class CatapultConfig(CatapultClass):
	def __init__(self, config):
		super().__init__(config)

	def gen_hls_body(self):
		hls_str = IndentedString()
		for fifo in self.outputs:
			conf_list = fifo.conf_list
			global_conf_list = fifo.global_conf_list
			for i in range(len(conf_list)):
				c = conf_list[i]
				if i < len(global_conf_list):
					g_c = global_conf_list[i]
				else:
					g_c = c
				hls_str.append(f'{fifo.name}_tmp.{c.name} = {g_c.name};')
			hls_str.append(f'{fifo.name}.write({fifo.name}_tmp);\n')
		return hls_str

	def setup_var_list(self):
		self.var_list = []
		for fifo in self.outputs:
			self.var_list += [HlsVar(name=f'{fifo.name}_tmp', type=fifo.datatype)]
