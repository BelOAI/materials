REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTS := $(REPO_ROOT)/scripts
DIR ?=

.PHONY: all session lecture materials site frontend handbook test notebooks-check tex clean

all: site

session:
ifndef DIR
	$(error Usage: make session DIR=lectures/01-project-setup)
endif
	python3 $(SCRIPTS)/build-session.py "$(DIR)"

tex:
ifndef DIR
	$(error Usage: make tex DIR=lectures/01-intro-ml)
endif
	$(SCRIPTS)/build-presentation.sh "$(DIR)" --local

lecture: session

materials:
ifndef DIR
	$(error Usage: make materials DIR=lectures/01-project-setup)
endif
	$(SCRIPTS)/build-materials.sh "$(DIR)"

frontend:
	npm --prefix $(REPO_ROOT)/site run build

handbook: frontend
	python3 $(SCRIPTS)/build-handbook.py

test:
	python3 -m unittest discover -s scripts/tests
	npm --prefix $(REPO_ROOT)/site test

notebooks-check:
	python3 -m unittest discover -s scripts/tests -p test_handbook.py -k test_all_

site: frontend
	$(SCRIPTS)/build-all.sh
	python3 $(SCRIPTS)/generate-site.py

clean:
	find $(REPO_ROOT)/lectures $(REPO_ROOT)/practices $(REPO_ROOT)/assignments -type f \( \
		-name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
		-o -name '*.nav' -o -name '*.snm' -o -name '*.vrb' -o -name '*.fls' \
		-o -name '*.fdb_latexmk' -o -name '*.synctex.gz' -o -name 'main.pdf' \
	\) -delete 2>/dev/null || true
	rm -rf $(REPO_ROOT)/_site
