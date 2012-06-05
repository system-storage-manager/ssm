all: help

help:
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets are:"
	@echo " help                    show this text"
	@echo " clean                   remove python bytecode and temp files"
	@echo " install                 install program on current system"
	@echo " spec                    prepare changelog for spec file"
	@echo " log                     prepare changelog"
	@echo " authors                 prepare list of authors"
	@echo " docs                    generate up-to-date documentation"
	@echo " source                  create source tarball"
	@echo " test                    run tests/run_tests.py"

check_vars:
ifndef VERSION
	@echo "VERSION variable not defined"
	@exit 1
endif
ifndef PREVIOUS
	@echo "PREVIOUS variable not defined"
	@exit 1
endif

clean:
	@python setup.py clean
	@make clean -C doc
	rm -f MANIFEST
	find . -\( -name "*.pyc" -o -name '*.pyo' -o -name "*~" -\) -delete

install:
	@python setup.py install

spec: check_vars
	@(LC_ALL=C date +"* %a %b %e %Y `git config --get user.name` <`git config --get user.email`> - $(VERSION)"; git log --pretty="format:- %s (%an)" $(PREVIOUS)..HEAD| cat) | less

log: check_vars
	@(LC_ALL=C date +"[%a %b %e %Y] `git config --get user.name` <`git config --get user.email`> - $(VERSION)"; echo; git shortlog -e $(PREVIOUS)..HEAD | cat; git diff --stat $(PREVIOUS)..HEAD | cat) | sed -e 's/@/_O_/g' | less

authors:
	@(echo -e "System Storage Manager was written by:\n\tLukáš Czerner <lczerner@redhat.com>"; echo -e "\nContributions (commits):"; git log --no-merges | grep '^Author:' | sort | uniq -c | sort -rn | sed -e 's/^\s*\([0-9]*\) Author: /\t(\1) /') | sed -e 's/@/_O_/g' | less

docs:
	@make dist -C doc

source: test clean
	@python setup.py sdist

test:
	@python test.py

release: check_vars authors log spec docs source
