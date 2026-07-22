#!/usr/bin/env bash
# Entrypoint: runs verify.py and writes /logs/verifier/reward.txt
mkdir -p /logs/verifier
python3 /tests/verify.py > /logs/verifier/verify.log 2>&1
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
cat /logs/verifier/verify.log
