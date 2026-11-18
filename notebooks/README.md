# Model comparison notebook

Open `Resume_NER_Model_Training.ipynb` in Jupyter. Install notebook dependencies with `python -m pip install -r notebooks/requirements.txt` from the project root. The notebook compares Rule-Based, ML-Based, and Hybrid phrase classification on a shared stratified held-out split from `backend/data/skill_phrase_benchmark.csv`. It outputs accuracy, precision, recall, F1, confusion matrices, a metrics chart, normalization examples, disagreement review, and saved model/metrics files.

The benchmark is small and curated for reproducible demonstration, not production validation. Metrics are phrase-level skill-relatedness metrics, not exact-span NER metrics and not job ranking metrics.
