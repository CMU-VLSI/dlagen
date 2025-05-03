class IndentedString():
	def __init__(self, indent=0):
		self.str_list = []
		self.indent_list = []
		self.fixed_indent = []
		self.cur_indent = indent

	def __str__(self):
		out = ''
		for string, indent in zip(self.str_list, self.indent_list):
			out += '\t' * indent + string + '\n'
		return out + '\n'

	def append(self, string):
		self.str_list += [string]
		self.indent_list += [self.cur_indent]
		self.fixed_indent += [False]

	def append_and_indent(self, string):
		self.append(string)
		self.indent()

	def append_fixed_indent(self, string, indent=0):
		self.str_list += [string]
		self.indent_list += [indent]
		self.fixed_indent += [True]

	def append_with_indent(self, string, indent=0):
		self.str_list += [string]
		self.indent_list += [indent]
		self.fixed_indent += [False]

	def indent(self, indent=1):
		self.cur_indent += indent

	def unindent(self, unindent=1):
		self.cur_indent -= unindent

	# def concat(self, next_str):
	# 	self.str_list += next_str.str_list
	# 	self.indent_list += next_str.indent_list
	# 	self.cur_indent = next_str.cur_indent

	def insert(self, body_str):
		for c, i, f in zip(body_str.str_list, body_str.indent_list, body_str.fixed_indent):
			self.str_list += [c]
			self.indent_list += [i if f else i+self.cur_indent]
			self.fixed_indent += [f]

	def close_bracket(self, n):
		for _ in range(n):
			self.unindent()
			self.append("}")

	def close_cpp_class(self):
		self.unindent()
		self.append('};\n')

	def parse_file(self, file):
		assert len(self.str_list) == 0 and len(self.indent_list) == 0, "File parsing is only allowed for empty IndentedString objects."
		for line in file:
			num_indent = line.count('\t')
			raw_str = line.replace('\t', '').replace('\n', '')
			self.append_with_indent(raw_str, num_indent)

