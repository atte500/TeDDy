import sys

# Emit a byte undefined in cp1252 (0x90) and invalid as a UTF-8 start
# byte, so a parent decoding in text mode fails regardless of its locale.
sys.stdout.buffer.write(b"\x90")
sys.stdout.buffer.write(b"\n")
sys.stdout.buffer.flush()