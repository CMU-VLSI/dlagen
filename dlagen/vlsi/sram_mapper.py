from .sram import MemType
from .sram import TsmcSramLib, SramMacro

from ..util.indented_str import IndentedString

import math
import os

class SramMapper():

	def __init__(self, config, sram_libs):
		self.config = config
		self.sram_libs = sram_libs
		self.parse_macro()

	def parse_macro(self):
		self.macros = {}
		for mem_type in MemType:
			self.macros[mem_type] = {}

		for sram in self.config:
			for w in range(sram['width'][0], sram['width'][1]+sram['width'][2], sram['width'][2]):
				mem_type = self.sram_libs[sram['lib']].type
				if w not in self.macros[mem_type]:
					self.macros[mem_type][w] = {}
				for d in range(sram['depth'][0], sram['depth'][1]+sram['depth'][2], sram['depth'][2]):
					if d in self.macros[mem_type][w]:
						self.macros[mem_type][w][d] += [(self.sram_libs[sram['lib']], sram['cm'])]
					else:
						self.macros[mem_type][w][d] = [(self.sram_libs[sram['lib']], sram['cm'])]

	def get_macro_mapping(self, mem_type, width, depth):
		# greedy, start from lowest mem_type (that satisfy port requirement)
		# within each mem_type, compose width and then depth, achieving smallest area overhead
		mem_type = MemType[mem_type]
		cur_width = width
		mapping = []
		for t, macros in self.macros.items():
			if t < mem_type:
				continue

			width_list = sorted(list(macros.keys()), reverse=True)
			# dict[key=w, depth=list of depth]
			while cur_width > 0:
				for w_i, w in enumerate(width_list):
					# pick biggest from list, greedily satisfy w
					if w > cur_width:
						if w_i == len(width_list) - 1:
							w = width_list[-1]
						else:
							continue
					w_mapping = []
					cur_width -= w
					depth_list = sorted(list(macros[w].keys()), reverse=True)
					cur_depth = depth
					while cur_depth > 0:
						for d_i, d in enumerate(depth_list):
							# pick biggest from list, greedily satisfy d
							if d > cur_depth:
								if d_i == len(depth_list) - 1:
									d = depth_list[-1]
								else:
									continue
							cur_depth -= d
							w_mapping += [SramMacro(*macros[w][d][0], w, d)]
							break
					mapping += [w_mapping]
					break
		return mapping

	def gen_verilog_module(self, name, mem_type, width, depth, mapping):
		assert mem_type == 'sp', NotImplemented

		outstr = IndentedString()
		outstr.append(f'module {name}(')
		outstr.indent()
		outstr.append('adr, d, en, we, clk, q')
		outstr.unindent()
		outstr.append(");")
		outstr.indent()
		addr_width = math.ceil(math.log2(depth))
		outstr.append(f'input [{addr_width-1}:0] adr;')
		outstr.append(f'input [{width-1}:0] d;')
		outstr.append('input en;')
		outstr.append('input we;')
		outstr.append('logic enb;')
		outstr.append('logic web;')
		outstr.append('input clk;')
		outstr.append(f'output [{width-1}:0] q;')
		outstr.append("assign enb = ~en;")
		outstr.append("assign web = ~we;")

		cur_width = 0
		q_assign_str = ''
		for col_id, col in enumerate(mapping):
			cur_depth = 0
			width_range = f'{cur_width+col[0].width-1}:{cur_width}' if len(mapping) > 1 else None
			width_range_logic_instantiation = f'{col[0].width-1}:0'
			if len(col) > 1:
				outstr.append(f'logic [{width_range_logic_instantiation}] q_{col_id};')
				mux_str = IndentedString()
				mux_str.append('always_comb begin')
				mux_str.indent()
			for macro_id, macro in enumerate(col):
				inst_name = f'{col_id}_{macro_id}'
				addr_range = f'{math.ceil(math.log2(macro.depth))-1}:0' if len(col) > 1 else None
				outstr.append(f'logic [{width_range_logic_instantiation}] q_{inst_name};')
				if addr_range:
					outstr.append(f'logic en_{inst_name}, we_{inst_name}, enb_{inst_name}, web_{inst_name};')
					outstr.append(f"assign en_{inst_name} = (adr >= {cur_depth} && adr < {cur_depth+macro.depth}) ? en : 1'b0;")
					outstr.append(f"assign we_{inst_name} = (adr >= {cur_depth} && adr < {cur_depth+macro.depth}) ? we : 1'b0;")
					outstr.append(f"assign enb_{inst_name} = (adr >= {cur_depth} && adr < {cur_depth+macro.depth}) ? enb : 1'b1;")
					outstr.append(f"assign web_{inst_name} = (adr >= {cur_depth} && adr < {cur_depth+macro.depth}) ? web : 1'b1;")
					if macro_id == 0:
						if_str = f'if (adr >= {cur_depth} && adr < {cur_depth+macro.depth})'
					elif macro_id == len(col) - 1:
						if_str = 'else' 
					else:
						if_str = f'else if (adr >= {cur_depth} && adr < {cur_depth+macro.depth})'
					mux_str.append(f'{if_str}')
					mux_str.indent()
					mux_str.append(f'q_{col_id} = q_{inst_name};')
					mux_str.unindent()
				else:
					if col_id == 0:
						q_assign_str = f'q_{inst_name}' + q_assign_str
					else:
						q_assign_str = f'q_{inst_name}, ' + q_assign_str
				outstr.insert(macro.gen_verilog_inst(inst_name, width_range=width_range, addr_range=addr_range))
				cur_depth += macro.depth
			if len(col) > 1:
				mux_str.unindent()
				mux_str.append('end')
				outstr.insert(mux_str)
			cur_width += macro.width

		if q_assign_str != '':
			outstr.append(f'assign q = {{{q_assign_str}}};')

		outstr.unindent()
		outstr.append('endmodule ')

		return outstr

	def compile(self, mapping_list, output_path):
		compiled_configs = []
		for mapping in mapping_list:
			for col_id, col in enumerate(mapping):
				for macro_id, macro in enumerate(col):
					config, command = macro.compile(output_path)
					if config not in compiled_configs:
						os.system(command)
						compiled_configs += [config]

	def map(self, name, mem_type, width, depth, output_path):
		mapping = self.get_macro_mapping(mem_type, width, depth)
		with open(os.path.join(output_path, f'{name}.v'), 'w') as f:
			f.write(str(self.gen_verilog_module(name, mem_type, width, depth, mapping)))
		return mapping
		