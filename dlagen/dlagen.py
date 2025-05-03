from .hls.catapult_gen import CatapultHlsGenerator
from .dse.ga import GA
from .cost_model.zigzag import ZigzagCostModel
from .vlsi.vlsi_gen import VlsiGenerator

import yaml
import os

class DLAGen():
	def __init__(self, config):
		self.config = config
		self.cost_model = ZigzagCostModel(config)
		self.dse = GA(self.cost_model, config)
		
		self.hls_gen = CatapultHlsGenerator(config['hls'], output_path=config['output'])

		self.vlsi_gen = VlsiGenerator(config['vlsi'], output_path=config['output'])

	def build(self, run_dse):
		if run_dse:
			cme, accel_arch, xyz = self.dse.explore()
			area = self.cost_model.get_area(accel_arch)

			self.config['hls'] = self.cost_model.dse2hls(self.config['hls'], cme, accel_arch, xyz)
			with open(os.path.join(self.config['output'], 'dse_config.yaml'), 'w') as f:
				yaml.dump(self.config, f, sort_keys=False)
		self.hls_gen.parse()
		self.hls_gen.generate(self.config['output'])

		self.vlsi_gen.build(self.hls_gen.get_memories(), self.hls_gen.top_class, area, self.hls_gen.rtl_path)

	def synthesize(self):
		self.hls_gen.synthesize()
		self.vlsi_gen.synthesize()
