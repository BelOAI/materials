REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTS := $(REPO_ROOT)/scripts
DIR ?=

.PHONY: all lecture site clean

all: site

lecture:
ifndef DIR
	$(error Usage: make lecture DIR=lectures/01-project-setup)
endif
	$(SCRIPTS)/build-presentation.sh $(DIR)

site:
	$(SCRIPTS)/build-all.sh
	python3 $(SCRIPTS)/generate-site.py

clean:
	find $(REPO_ROOT)/lectures -type f \( \
		-name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
		-o -name '*.nav' -o -name '*.snm' -o -name '*.vrb' -o -name '*.fls' \
		-o -name '*.fdb_latexmk' -o -name '*.synctex.gz' -o -name 'main.pdf' \
	\) -delete
	rm -rf $(REPO_ROOT)/_site
