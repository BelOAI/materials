REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
SCRIPTS := $(REPO_ROOT)/utils/scripts
JOBS ?= 2
DIR ?=

.PHONY: all session lecture materials site frontend handbooks handbook-pdf test tex clean

all: site

session:
ifndef DIR
	$(error Usage: make -f build/Makefile session DIR=course/01-intro-ml/lecture)
endif
	cd "$(REPO_ROOT)" && python3 "$(SCRIPTS)/build-session.py" "$(DIR)"

tex:
ifndef DIR
	$(error Usage: make -f build/Makefile tex DIR=course/01-intro-ml/lecture)
endif
	cd "$(REPO_ROOT)" && "$(SCRIPTS)/build-presentation.sh" "$(DIR)" --local

lecture: session

materials:
ifndef DIR
	$(error Usage: make -f build/Makefile materials DIR=course/01-intro-ml/lecture)
endif
	cd "$(REPO_ROOT)" && "$(SCRIPTS)/build-materials.sh" "$(DIR)"

frontend:
	npm --prefix "$(REPO_ROOT)/utils/site" run build

handbooks: frontend
	python3 "$(SCRIPTS)/build-handbooks.py"

handbook-pdf:
	cd "$(REPO_ROOT)" && python3 "$(SCRIPTS)/build-handbook-pdf.py" $(if $(DIR),"$(DIR)",--all) --jobs "$(JOBS)"

test:
	cd "$(REPO_ROOT)" && python3 -m unittest discover -s utils/scripts/tests
	npm --prefix "$(REPO_ROOT)/utils/site" test

site: frontend
	"$(SCRIPTS)/build-all.sh"
	python3 "$(SCRIPTS)/generate-site.py"

clean:
	find "$(REPO_ROOT)/course" -type f \( \
		-name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
		-o -name '*.nav' -o -name '*.snm' -o -name '*.vrb' -o -name '*.fls' \
		-o -name '*.fdb_latexmk' -o -name '*.synctex.gz' -o -name 'main.pdf' \
	\) -delete 2>/dev/null || true
	rm -f "$(REPO_ROOT)/handbooks/ml/01-classic-ml/01-first-experiment/content.pdf"
	rm -rf "$(REPO_ROOT)/_site"
