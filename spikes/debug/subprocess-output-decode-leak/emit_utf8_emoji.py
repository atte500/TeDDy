import sys

# U+2705 encodes as the three bytes e2 9c 85, all defined in cp1252.
# A locale decode therefore succeeds and silently mojibakes the text,
# while a UTF-8 decode round-trips it exactly.
sys.stdout.buffer.write(b"\xe2\x9c\x85 utf8 ok")
sys.stdout.buffer.write(b"\n")
sys.stdout.buffer.flush()