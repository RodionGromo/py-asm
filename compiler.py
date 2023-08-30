import math, random

class Command:
	def __init__(self, command, args):
		self.command = command
		self.args = []
		# delete any args after "--"
		for arg in args:
			if(arg != "--"):
				self.args.append(arg)
			else:
				break

	def raw(self):
		return f"{self.command} {self.args}"

registers = {
	"ra": 0,
	"rb": 0,
	"rc": 0,
	"rd": 0,
	"ro": 0,
	"ri": 0,
	"rr": 0,
	"flag": 0b100000000,
	# flags:
	# 2^0 - out character mode
	# 2^1 - data cursor wrap
	# 2^2 - cmp: greater
	# 2^3 - cmp: less
}
memory = [0] * 511 # 512 bytes
memory_cursor = 0

def deref(value):
	if type(value) is int:
		return value
	if value.isdigit():
		return int(value)
	elif(value in registers):
		return int(registers[value])
	elif value in data_definitions:
		return int(data_definitions[value])
	elif value in labels:
		return int(labels[value])
	else:
		# parse in binary, octal or hex
		if("0b" in value):
			return int(value[2:],2)
		if("0o" in value):
			return int(value[2:],8)
		if("0x" in value):
			return int(value[2:],16)

def isFlagSet(flag_index):
	flipped = ''.join(list(bin(registers["flag"])[2:])[::-1])
	return bool(int(flipped[flag_index]))

def setFlag(index, state):
	global registers
	binn = list(bin(registers["flag"])[2:])[::-1]
	if state:
		binn[index] = "1"
	else:
		binn[index] = "0"
	registers["flag"] = int(''.join(binn[::-1]),2)

def setBit(value, index, state):
	binn = list(bin(value)[2:])[::-1]
	if state:
		binn[index] = "1"
	else:
		binn[index] = "0"
	return int(''.join(binn[::-1]),2)

def write_byte(byte):
	global memory, memory_cursor
	if byte > 0xff:
		raise Exception("Value greater than byte.")
	memory[memory_cursor] = byte
	memory_cursor += 1
	if memory_cursor > len(memory):
		if not isFlagSet(1):
			raise Exception("Exceeded allowed memory. Set flag 1 to allow wrapping memory cursor")
		else:
			memory_cursor = 0

def fixedhex(value, size):
	hexn = hex(value)[2:]
	return "0x" + ("0" * (size - len(hexn))) + hexn

def dump_memory():
	magicString = ""
	width = int(math.sqrt(len(memory)))
	for i in range(0, len(memory)-width, width):
		hexdump = ' '.join([fixedhex(memory[i2], 2) for i2 in range(i, i+width)])
		magicString += f"{hexdump}\n"
	return magicString

print("> Reading code...")
# read file and parse values
code_file = open("./code.pyasm", "r").readlines()
raw_code_lines = []
for line in code_file:
	line = line.strip().replace(",", "").replace("\t","")
	if line == "":
		continue
	data = line.split(" ")
	raw_code_lines.append(Command(data[0], data[1:]))

# find labels to jump to
print("> Assigning labels if any exist...")
labels = {}
for line in raw_code_lines:
	if ":" in line.command:
		labels[line.command[:-1]] = raw_code_lines.index(line)
for name, index in labels.items():
	print(f">> Found '{name}' at {index}")

# run code
print("> Running code...")
cmd_index = 0
data_definitions = {}
while cmd_index < len(raw_code_lines):
	line = raw_code_lines[cmd_index]
	try:
		# memory and event managment
		if line.command == "mov":
			registers[line.args[1]] = deref(line.args[0])
		if line.command == "call":
			if line.args[0] == "out":
				print(chr(registers["ro"]) if isFlagSet(0) else registers["ro"], end="")
			if line.args[0] == "in":
				registers["ri"] = input("? ")
		if line.command == "mrd":
			memory_cursor = deref(line.args[1])
			read_data = []
			if line.args[0] == "int":
				for i in range(4):
					read_data.append(memory[memory_cursor])
					memory_cursor += 1
				raw_data = "".join([hex(i)[2:] for i in read_data])
				registers["ra"] = int(raw_data,16)
		if line.command == "lci":
			memory_cursor -= 1
			if memory_cursor < 0:
				if isFlagSet(1):
					memory_cursor = len(memory)-1
				else:
					raise Exception("Memory limits exceeded while moving.")
		if line.command == "rci":
			memory_cursor += 1
			if memory_cursor > len(memory):
				if isFlagSet(1):
					memory_cursor = 0
				else:
					raise Exception("Memory limits exceeded while moving.")
		if line.command == "rsci":
			memory_cursor = 0
		if line.command == "sdci":
			memory_cursor = deref(line.args[0])
			if not(0 < memory_cursor < len(memory)):
				raise Exception("Memory limits exceeded while moving.")
		if line.command == "rdci":
			registers["ra"] = memory[memory_cursor]
		# allocations
		if line.command == "string":
			block_start = deref(memory_cursor)
			for char in " ".join(line.args[1:]) + chr(0):
				number = ord(char)
				write_byte(number)
			data_definitions[line.args[0]] = block_start
			print("> Added string var", line.args[0], "at", block_start)
		if line.command == "int":
			number = deref(line.args[1])
			if number > 0xffffffff:
				raise Exception("Number too big for type int.")
			data_definitions[line.args[0]] = memory_cursor
			hexn = fixedhex(number,8)[2:]
			for i in range(0, len(hexn), 2):
				write_byte(int(hexn[i:i+2],16))
		# math
		if line.command == "sub":
			registers[line.args[1]] -= deref(line.args[0])
		if line.command == "mul":
			registers["ra"] *= deref(line.args[0])
		if line.command == "div":
			d,m = divmod(registers["ra"], deref(line.args[0]))
			registers["ra"] = d
			registers["rb"] = m
		if line.command == "add":
			registers[line.args[1]] += deref(line.args[0])
		if line.command == "cmp":
			if registers["ra"] > deref(line.args[0]):
				setFlag(2, True)
				setFlag(3, False)
			if registers["ra"] < deref(line.args[0]):
				setFlag(2, False)
				setFlag(3, True)
			if registers["ra"] == deref(line.args[0]):
				setFlag(2, True)
				setFlag(3, True)
		if line.command == "rnd":
			registers["ra"] = random(deref(line.args[0]), deref(line.args[1]))
		# flow control
		if line.command == "jump":
			value = deref(line.args[0]) - 1
			if not (0 <= value < len(raw_code_lines)):
				raise Exception(f"JUMP index error: {value}")
			registers["rr"] = cmd_index
			cmd_index = value
		if line.command == "jmpl":
			registers["rr"] = cmd_index
			cmd_index = labels[line.args[0]]
		if line.command == "jret":
			cmd_index = registers["rr"]
		if line.command == "jgr":
			if isFlagSet(2) and not isFlagSet(3):
				registers["rr"] = cmd_index
				cmd_index = deref(line.args[0])
		if line.command == "jle":
			if isFlagSet(3) and not isFlagSet(2):
				registers["rr"] = cmd_index
				cmd_index = deref(line.args[0])
		if line.command == "jeq":
			if isFlagSet(2) and isFlagSet(3):
				registers["rr"] = cmd_index
				cmd_index = deref(line.args[0])
		# boolean logic
		if line.command == "or":
			registers["ra"] |= deref(line.args[0])
		if line.command == "and":
			registers["ra"] &= deref(line.args[0])
		if line.command == "xor":
			registers["ra"] ^= deref(line.args[0])
		if line.command == "not":
			registers["ra"] = ~registers["ra"]
		if line.command == "rol":
			registers["ra"] <<= deref(line.args[0])
		if line.command == "ror":
			registers["ra"] >>= deref(line.args[0])
		if line.command == "btst":
			registers[line.args[1]] = setBit(registers[line.args[1]], deref(line.args[0]), deref(line.args[2]))

	except Exception as e:
		print("Code execution halted:", e)
		print("Line ", raw_code_lines.index(line), ": ", line.raw(), sep="")
		raise e
		break
	cmd_index += 1
print()