.PHONY: help install validate demo figures panel panel-neutral ablation test clean all bridge \
        smoke reproduce-tables ext-tables k3-table headline repair-table cue2x2 idioms \
        static-baselines regrade-check paper-assets pack-solutions unpack-solutions panel-table

help:
	@echo "OrderBench targets:"
	@echo "  make install         - install runtime + dev deps"
	@echo "  make smoke           - 30-second check: validity gate + smoke tests (no API keys)"
	@echo "  make validate        - construct-validity gate (reference clean / buggy leaks)"
	@echo "  make demo            - run reference/buggy/null eval -> results/demo/"
	@echo "  make figures         - regenerate result figures + LaTeX tables (-> out/)"
	@echo "  make bridge          - 8-primitive real-stdlib validity bridge (-> out/tables/bridge.tex)"
	@echo "  make ext-tables      - output-only-vs-OrderBench + neutral per-class tables"
	@echo "  make k3-table        - k=1 vs k=3 generation-robustness table"
	@echo "  make cue2x2          - 2x2 prompt-cue ablation table"
	@echo "  make idioms          - which cleanup idiom each candidate used (with/finally/none)"
	@echo "  make static-baselines- pylint R1732 + AST leak detector vs OrderBench's oracle"
	@echo "  make regrade-check   - re-grade every cached solution; must match committed rows"
	@echo "  make paper-assets    - regenerate tables/figures and sync them into paper/"
	@echo "  make unpack-solutions- unpack the cached generations needed by regrade-check"
	@echo "  make reproduce-tables- regenerate ALL paper tables from committed results"
	@echo "  make test            - run pytest smoke suite"
	@echo "  make all             - validate + demo + figures + test"

install:
	python3 -m pip install -r requirements.txt

validate:
	python3 scripts/validate_all.py

demo:
	python3 scripts/run_eval.py --models reference buggy null --tag demo

figures:
	python3 scripts/make_figures.py results/demo/results.json

panel:
	python3 scripts/run_eval.py --models reference buggy null \
	  claude-code:haiku claude-code:sonnet claude-code:opus ollama:gemma4:12b \
	  --repeats 1 --prompt-mode instructed --tag panel

panel-neutral:
	python3 scripts/run_eval.py --models reference buggy null \
	  claude-code:haiku claude-code:sonnet claude-code:opus ollama:gemma4:12b \
	  --repeats 1 --prompt-mode neutral --tag panel_neutral

ablation:
	python3 scripts/make_ablation.py

test:
	python3 -m pytest -q || python3 tests/test_smoke.py

clean:
	rm -rf results/_pytest results/**/solutions
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

all: validate demo figures test

bridge:
	python3 scripts/validity_bridge.py

smoke:
	python3 scripts/validate_all.py && (python3 -m pytest -q || python3 tests/test_smoke.py)

ext-tables:
	python3 scripts/make_extended_tables.py

k3-table:
	python3 scripts/make_k3_table.py

cue2x2:
	python3 scripts/make_2x2_table.py

idioms:
	python3 scripts/idiom_stats.py

panel-table:
	python3 scripts/make_panel_table.py

static-baselines:
	python3 scripts/static_baselines.py

regrade-check:
	python3 scripts/regrade_check.py

# The cached generations ship compressed so a plain `git clone` is enough to re-grade every
# published number offline. Excludes __pycache__, which the harness regenerates and which
# otherwise outnumbered the solutions it was shipped alongside.
pack-solutions:
	tar --exclude='__pycache__' --exclude='*.pyc' \
	    -czf results/solutions.tar.gz $$(find results -type d -name solutions | sort)
	@ls -lh results/solutions.tar.gz

unpack-solutions:
	tar -xzf results/solutions.tar.gz
	@echo "unpacked cached solutions; 'make regrade-check' now has data"

headline:
	python3 scripts/make_headline.py && python3 scripts/make_ablation_fig.py

repair-table:
	python3 scripts/run_repair.py --models claude-code:haiku claude-code:sonnet

reproduce-tables: ablation headline ext-tables k3-table cue2x2 idioms panel-table static-baselines bridge
	@echo "regenerated all paper tables/figures into out/"

# main.tex \input{}s from paper/tables/ and \includegraphics from paper/figures/, while the
# generators write to out/. This is the one explicit step that promotes a regenerated asset
# into the manuscript, so a table never changes in the paper without someone asking for it.
# Only the two tables main.tex actually \input{}s; the rest stay in out/ so the manuscript
# directory holds exactly what is needed to build it.
paper-assets: reproduce-tables
	mkdir -p paper/tables
	cp out/tables/ablation.tex out/tables/panel.tex paper/tables/
	@echo "synced out/tables -> paper/tables"
