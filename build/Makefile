REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
SCRIPTS := $(REPO_ROOT)/utils/scripts
DIR ?=

.PHONY: all session lecture materials site frontend handbooks test tex clean

all: site

session:
ifndef DIR
	$(error Usage: make -f build/Makefile session DIR=course/lectures/01-intro-ml)
endif
	cd "$(REPO_ROOT)" && python3 "$(SCRIPTS)/build-session.py" "$(DIR)"

tex:
ifndef DIR
	$(error Usage: make -f build/Makefile tex DIR=course/lectures/01-intro-ml)
endif
	cd "$(REPO_ROOT)" && "$(SCRIPTS)/build-presentation.sh" "$(DIR)" --local

lecture: session

materials:
ifndef DIR
	$(error Usage: make -f build/Makefile materials DIR=course/lectures/01-intro-ml)
endif
	cd "$(REPO_ROOT)" && "$(SCRIPTS)/build-materials.sh" "$(DIR)"

frontend:
	npm --prefix "$(REPO_ROOT)/utils/site" run build

handbooks: frontend
	python3 "$(SCRIPTS)/build-handbooks.py"

test:
	cd "$(REPO_ROOT)" && python3 -m unittest discover -s utils/scripts/tests
	npm --prefix "$(REPO_ROOT)/utils/site" test

site: frontend
	"$(SCRIPTS)/build-all.sh"
	python3 "$(SCRIPTS)/generate-site.py"

clean:
	find "$(REPO_ROOT)/course/lectures" "$(REPO_ROOT)/course/practices" "$(REPO_ROOT)/course/assignments" -type f \( \
		-name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
		-o -name '*.nav' -o -name '*.snm' -o -name '*.vrb' -o -name '*.fls' \
		-o -name '*.fdb_latexmk' -o -name '*.synctex.gz' -o -name 'main.pdf' \
	\) -delete 2>/dev/null || true
	rm -rf "$(REPO_ROOT)/_site"
