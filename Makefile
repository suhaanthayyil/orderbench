.PHONY: help install validate demo figures panel panel-neutral ablation test clean all bridge

help:
	@echo "OrderBench targets:"
	@echo "  make install   - install runtime + dev deps"
	@echo "  make validate  - construct-validity gate (reference clean / buggy leaks)"
	@echo "  make demo      - run reference/buggy/null eval -> results/demo/"
	@echo "  make figures   - regenerate paper figures + LaTeX tables from demo results"
	@echo "  make test      - run pytest smoke suite"
	@echo "  make all       - validate + demo + figures + test"

install:
	python3 -m pip install -r requirements.txt

validate:
	python3 scripts/validate_all.py

demo:
	python3 scripts/run_eval.py --models reference buggy null --tag demo

figures:
	python3 scripts/make_figures.py results/panel/results.json

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
