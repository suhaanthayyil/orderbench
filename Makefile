.PHONY: help install validate demo figures panel panel-neutral ablation test clean all bridge \
        smoke reproduce-tables ext-tables k3-table repair-table

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

repair-table:
	python3 scripts/run_repair.py --models claude-code:haiku claude-code:sonnet

reproduce-tables: ablation ext-tables k3-table bridge
	@echo "regenerated all paper tables into out/tables/"
