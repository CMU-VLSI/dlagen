import os
import yaml
import math
import shutil

class HammerGenerator():
	def __init__(self, config, output_path):
		self.technology = config['technology']
		self.output_path = output_path
		self.base_syn_yaml = os.path.join(config['base_configs'], 'hammer-syn.yml')
		self.base_par_yaml = os.path.join(config['base_configs'], 'hammer-par.yml')
		self.base_env_yaml = os.path.join(config['base_configs'], 'hammer-env.yml')
		self.base_tool_yaml = os.path.join(config['base_configs'], 'hammer-tool.yml')

		self.out_syn_yaml = os.path.join(self.output_path, 'hammer-syn.yml')
		self.out_par_yaml = os.path.join(self.output_path, 'hammer-par.yml')
		self.out_env_yaml = os.path.join(self.output_path, 'hammer-env.yml')
		self.out_tool_yaml = os.path.join(self.output_path, 'hammer-tool.yml')

	def setup_synthesis(self, macros, design_name, rtl_path):
		with open(self.base_syn_yaml) as f:
			syn_config = yaml.safe_load(f)

			syn_config['vlsi.core.technology'] = f'hammer.technology.{self.technology}'
			syn_config['synthesis.inputs']['top_module'] = design_name
			input_files = [rtl_path]
			mem_lib_list = []
			included_names = []
			for name, mapping in macros.items():
				input_files += [os.path.join(self.output_path, f'{name}.v')]
				for col_id, col in enumerate(mapping):
					for macro_id, macro in enumerate(col):
						if macro.name in included_names:
							continue
						mem_lib_list += [{'library': {
							'name': macro.name,
							'nldm_liberty_file': os.path.join(self.output_path, macro.timing_path),
							'gds_file': os.path.join(self.output_path, macro.gds_path),
							'lef_file': os.path.join(self.output_path, macro.lef_path),
							'spice_file': os.path.join(self.output_path, macro.spice_path),
							'verilog_sim': os.path.join(self.output_path, macro.verilog_path),
							'corner': {
								'pmos': 'typical',
								'nmos': 'typical',
								'temperature': '25 C'
							},
							'supplies': {
								'VDD': '0.8 V',
								'GND': '0 V'
							},
							'provides': [{'lib_type': 'stdcell', 'vt': 'RVT'}]
						}}]
						included_names += [macro.name]
			syn_config['synthesis.inputs']['input_files'] = input_files
			syn_config['vlsi.technology.extra_libraries'] = mem_lib_list
			with open(self.out_syn_yaml, 'w') as wf:
				yaml.dump(syn_config, wf, sort_keys=False)

	def setup_par(self, design_name, area):
		area = area * 1e6 / 0.85
		with open(self.base_par_yaml) as f:
			par_config = yaml.safe_load(f)

			par_config['vlsi.inputs.placement_constraints'] = [
				{
					'path': design_name,
					'type': 'toplevel',
					'x': 0,
					'y': 0,
					'width': math.ceil(math.sqrt(area)),
					'height': math.ceil(math.sqrt(area)),
					'margins': {
						'left': 0,
						'right': 0,
						'top': 0,
						'bottom': 0
					}
				}
			]

			with open(self.out_par_yaml, 'w') as wf:
				yaml.dump(par_config, wf, sort_keys=False)


	def build(self, macros, design_name, area, rtl_path):
		shutil.copy(self.base_env_yaml, self.out_env_yaml)
		shutil.copy(self.base_tool_yaml, self.out_tool_yaml)
		self.setup_synthesis(macros, design_name, rtl_path)
		self.setup_par(design_name, area)

	def synthesize(self):
		build_dir = os.path.join(self.output_path, f'build-{self.technology}')
		syn_output = os.path.join(build_dir, 'syn-rundir', 'syn-output.json')
		par_input = os.path.join(build_dir, 'par-input.json')
		command = f'cd {self.output_path};'
		command += f'hammer-vlsi -e {self.out_env_yaml} -p {self.out_tool_yaml} -p {self.out_syn_yaml} -p {self.out_par_yaml} --obj_dir {build_dir} syn;'
		command += f'hammer-vlsi -e {self.out_env_yaml} -p {self.out_tool_yaml} -p {self.out_syn_yaml} -p {self.out_par_yaml} -p {syn_output} -o {par_input} --obj_dir {build_dir} syn-to-par;'
		command += f'hammer-vlsi -e {self.out_env_yaml} -p {self.out_tool_yaml} -p {self.out_syn_yaml} -p {self.out_par_yaml} -p {par_input} --obj_dir {build_dir} par;'
		os.system(command)
