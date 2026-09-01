REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTS := $(REPO_ROOT)/scripts
DIR ?=

.PHONY: all session lecture materials site clean

all: site

session:
ifndef DIR
	$(error Usage: make session DIR=lectures/01-project-setup)
endif
	@if [ -f "$(DIR)/main.tex" ]; then \
		$(SCRIPTS)/build-presentation.sh $(DIR); \
	fi
	$(SCRIPTS)/build-materials.sh $(DIR)

lecture: session

materials:
ifndef DIR
	$(error Usage: make materials DIR=lectures/01-project-setup)
endif
	$(SCRIPTS)/build-materials.sh $(DIR)

site:
	$(SCRIPTS)/build-all.sh
	python3 $(SCRIPTS)/generate-site.py

clean:
	find $(REPO_ROOT)/lectures $(REPO_ROOT)/practices -type f \( \
		-name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
		-o -name '*.nav' -o -name '*.snm' -o -name '*.vrb' -o -name '*.fls' \
		-o -name '*.fdb_latexmk' -o -name '*.synctex.gz' -o -name 'main.pdf' \
	\) -delete 2>/dev/null || true
	rm -rf $(REPO_ROOT)/_site
