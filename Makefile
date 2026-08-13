.PHONY: all data clean kpis dashboard docs verify fresh

all: data kpis dashboard docs

data:
	bash scripts/00_download_data.sh
	python3 scripts/01_clean_data.py

kpis:
	python3 scripts/02_build_kpis.py

dashboard:
	python3 scripts/03_build_dashboard.py

docs:
	python3 scripts/05_write_docs.py

verify:
	node scripts/04_verify_dashboard.mjs

fresh: clean all verify

clean:
	rm -f data/processed/*.csv dashboard/kpis.json dashboard/zomato_dashboard.html
