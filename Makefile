YEAR    ?= 2024
COUNTRY ?= Bahrain
SESSION ?= Race
CSV     ?= data/pit_$(YEAR)_$(shell echo $(COUNTRY) | tr '[:upper:]' '[:lower:]').csv
OUT_DIR ?= data

.PHONY: help download analyze stints report compare test install clean

help:
	@echo ""
	@echo "F1 Pitstop Analyzer — available targets"
	@echo "----------------------------------------"
	@echo "  make install              Install all dependencies"
	@echo "  make download             Download pit data (YEAR=2024 COUNTRY=Bahrain SESSION=Race)"
	@echo "  make analyze              Analyze + plot a race CSV (CSV=data/pit_2024_bahrain.csv)"
	@echo "  make stints               Reconstruct stints and detect undercuts"
	@echo "  make report               Generate interactive HTML report"
	@echo "  make compare              Compare all CSVs found in data/"
	@echo "  make test                 Run the full test suite"
	@echo "  make clean                Remove generated plots and reports"
	@echo ""
	@echo "Examples:"
	@echo "  make download YEAR=2023 COUNTRY=Italy"
	@echo "  make analyze  CSV=data/pit_2023_italy.csv"
	@echo "  make compare  OUT_DIR=reports"
	@echo ""

install:
	pip install -r requirements.txt

download:
	python src/download_pitstops_openf1.py \
	    --year $(YEAR) --country "$(COUNTRY)" --session "$(SESSION)" \
	    --out-dir $(OUT_DIR)

analyze:
	python src/analyze.py --csv $(CSV) --out-dir $(OUT_DIR)

stints:
	python src/stints.py --csv $(CSV) --out-dir $(OUT_DIR)

report:
	python src/report.py --csv $(CSV) --out-dir $(OUT_DIR)

compare:
	@CSVS=$$(ls $(OUT_DIR)/pit_*.csv 2>/dev/null | tr '\n' ' '); \
	if [ -z "$$CSVS" ]; then \
	    echo "No pit_*.csv files found in $(OUT_DIR)/. Run 'make download' first."; \
	    exit 1; \
	fi; \
	python src/compare.py --csvs $$CSVS --out-dir $(OUT_DIR)

test:
	python -m pytest tests/ -v

clean:
	rm -f data/*_analysis.png data/*_stints.png data/*_report.html data/comparison*.png
