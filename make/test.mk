# make/test.mk - Test runner targets

.PHONY: test

test:
	uv run pytest
