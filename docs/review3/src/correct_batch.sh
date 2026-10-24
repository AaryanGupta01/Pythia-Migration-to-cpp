cd /mnt/c/Users/visha/OneDrive/Desktop/Documents/programming/pythia
E=docs/review3/src/evidence
V=.venv/bin/python
( date -Iseconds; $V scripts/check_libmode.py; echo "exit=$?" ) > $E/libmode_run.txt 2>&1
rm -rf /tmp/fz && ( date -Iseconds; $V tools/fuzz.py --n 150 --seed 0 --out /tmp/fz; $V tools/fuzz_run.py /tmp/fz; echo "exit=$?" ) > $E/fuzz_run.txt 2>&1
( date -Iseconds; $V scripts/property_test.py; echo "exit=$?" ) > $E/property_run.txt 2>&1
