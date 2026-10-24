cd /mnt/c/Users/visha/OneDrive/Desktop/Documents/programming/pythia
V=.venv/bin/python
$V docs/review3/src/edge_cases.py > docs/review3/src/evidence/edge_cases_log.txt 2>&1
$V docs/review3/src/bench_kernels.py --runs 5 > docs/review3/src/evidence/bench_log.txt 2>&1
