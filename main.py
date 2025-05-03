import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import logging
from tqdm import tqdm
from functools import partialmethod
import yaml
import random
import tempfile
import argparse
from dlagen.dlagen import DLAGen

tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)
logging.disable(logging.CRITICAL)


# Create the parser
parser = argparse.ArgumentParser(description="DLAGen Launcher")

parser.add_argument("step", choices=["build", "synthesize"], help="Synthesize will both build and compile.")
parser.add_argument("--seed", type=int, default=777, help='Random seed for reproducibility.')
parser.add_argument('--config', type=str, default='configs/example.yaml', help='Path to the DLAGen configuration file.')
parser.add_argument("--skip_dse", action="store_true", default=False, help='Skip DSE and use the HLS/VLSI configuration in the input yaml file for compilation')

# Parse arguments
args = parser.parse_args()

random.seed(args.seed)

with open(args.config) as f:
	config = yaml.full_load(f)
	dlagen = DLAGen(config)
	if args.step in ['build', 'synthesize']:
		dlagen.build(run_dse=not args.skip_dse)
	if args.step == 'synthesize':
		dlagen.synthesize()