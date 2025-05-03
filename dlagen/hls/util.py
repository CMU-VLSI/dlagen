from collections import Counter, defaultdict
import itertools
import re

def get_addr_from_loop_list(loops, fixed_bounds=False):
	loops = loops[::-1]
	addr = ''
	if len(loops) == 0:
		return '0'
	for i in range(len(loops)):
		op = loops[i]
		for j in range(i):
			postfix = '' if fixed_bounds else '_P'
			op += f"*{loops[j].upper()}{postfix}"
		addr += op
		if i < len(loops) - 1:
			addr += "+"
	return addr

def re_match(mystr, pattern):
	return len(re.findall(pattern, mystr)) > 0

def re_match_pattern_list(mystr, pattern_list):
	res = False
	for pattern in pattern_list:
		res = res or re_match(mystr, pattern)
	return res

def re_match_str_list(mystr_list, pattern):
	res = False
	for mystr in mystr_list:
		res = res or re_match(mystr, pattern)
	return res

def re_num_match_str_list(mystr_list, pattern):
	cnt = 0
	for mystr in mystr_list:
		if re_match(mystr, pattern):
			cnt += 1
	return cnt

def update_loop_order_subset_from_unique_loop_order(subset, unique_loop_order):
	unique_subset = make_unique(subset)
	unique_names = [loop[0] for loop in unique_loop_order]

	visited = []

	tiled_variables = {}
	for name in subset:
		if name in visited:
			continue
		visited += [name]

		num_tile_levels_loop = re_num_match_str_list(unique_names, f'{name}_{r'\d+'}')
		num_tile_levels_subset = re_num_match_str_list(unique_subset, f'{name}_{r'\d+'}')
		if num_tile_levels_subset == 0 and num_tile_levels_loop > 0:
			idx = unique_subset.index(f'{name}')
			unique_subset[idx] = f'{name}_{num_tile_levels_loop-1}'

			tiled_variables[name] = get_tiled_variable_definition(name, [f'{name}_{num_tile_levels_loop-1}'])
		else:
			tile_list = []
			for i in reversed(range(num_tile_levels_subset)):
				idx = unique_subset.index(f'{name}_{i}')
				unique_subset[idx] = f'{name}_{i+num_tile_levels_loop-num_tile_levels_subset}'
				tile_list += [f'{name}_{i+num_tile_levels_loop-num_tile_levels_subset}']

			if len(tile_list) > 0:
				tiled_variables[name] = get_tiled_variable_definition(name, tile_list)

	return unique_subset, tiled_variables

def get_tiled_variable_definition(var_name, unique_tile_list):
	addr_str = get_addr_from_loop_list(unique_tile_list)
	return f'uint16_t {var_name} = {addr_str};'

def make_unique_loop_order(loop_order):
	names = [loop[0] for loop in loop_order]
	unique_names = make_unique(names)
	for name in names:
		num_tile_levels = re_num_match_str_list(unique_names, f'{name}_{r'\d+'}')
	return [(unique_names[i], loop_order[i][1]) for i in range(len(loop_order))]

def make_unique(seq):
	counts = Counter(seq)
	suffix_counter = defaultdict(lambda: itertools.count(1))
	return [elem if counts[elem] == 1 else elem + f'_{next(suffix_counter[elem])-1}' for elem in seq]

def define_i_xyz(xyz, postfix):
	return f'i{xyz} = f{xyz}_{postfix} + STRIDE_P * o{xyz}_{postfix};'
