# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINX_OPTS   ?=
SPHINX_BUILD  ?= sphinx-build
HTTP_PORT     ?= 8000
SOURCE_DIR     = .
BUILD_DIR     ?= build
GHPAGES_BRANCH = gh-pages

html:
	@$(SPHINX_BUILD) -M html "$(SOURCE_DIR)" "$(BUILD_DIR)" $(SPHINX_OPTS) $(O)

publish: clean html
	BUILD_DIR=$(BUILD_DIR) tools/publish-github-pages.sh

clean:
	rm -rf $(BUILD_DIR)

test: html
	python -m http.server --directory $(BUILD_DIR)/html $(HTTP_PORT)

.PHONY: html publish
