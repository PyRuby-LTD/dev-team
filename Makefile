.PHONY: regression

# Everything a reviewer should trust. `make regression` runs it all;
# `make regression TEST=tests.test_runner` runs one module, class or test.
regression:
	uv run python -m unittest $(if $(TEST),$(TEST),discover -s tests)
