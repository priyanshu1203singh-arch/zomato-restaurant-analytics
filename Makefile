.PHONY: all data kpis dashboard docs verify verify-all app fresh clean

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

# Run the Streamlit app locally on http://localhost:8501
app:
	streamlit run streamlit_app.py

# Everything that does not need a running server
verify:
	node scripts/04_verify_dashboard.mjs
	python3 scripts/06_verify_docs.py
	python3 tests/test_streamlit_measures.py

# Also drives the Streamlit app in a browser. Starts and stops the server.
verify-all: verify
	@echo "Starting Streamlit on :8501 ..."
	@streamlit run streamlit_app.py --server.port 8501 --server.headless true & \
	 SERVER_PID=$$!; \
	 sleep 15; \
	 node tests/test_streamlit_app.mjs; STATUS=$$?; \
	 kill $$SERVER_PID; \
	 exit $$STATUS

fresh: clean all verify

clean:
	rm -f data/processed/*.csv dashboard/kpis.json dashboard/zomato_dashboard.html
