import sys
import re

file = sys.argv[1]

input = open('raw/' + file, 'r')
output = open('modern/' + file, 'w')

output.write('[')

dialog = ''

# Convert to tuple format, each tuple has speaker in pos 0 then line in pos 1.

for line in input:

	line = line.replace('\n', '')
	line = re.sub(r'(?<=[\.\!\?])(?=[A-Z])', r' ', line)
	if line == '<T>' or line == '</T>' or len(line) == 0:
		pass
	elif line == line.upper():
		name = '("' + line[0] + line.lower()[1:] + '", '
		if len(dialog) > 0:
			str = '"' + dialog + '"), '
			output.write(str)
                        dialog = ''
		output.write(name)
	else:
		if len(dialog) > 0:
			dialog = dialog + ' '
		dialog = dialog + line
t = '"' + dialog + '")'
output.write(t)
output.write(']')
	
