#!/bin/bash

# Check for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Install Apache Benchmark
    brew install apache-bench
# Check for Linux (RHEL-based)
elif [[ "$OSTYPE" == "rhel"* ]]; then
    # Install Apache Benchmark
    sudo dnf install -y httpd-tools
fi

# all benchmarks gonna be executed by Apache Benchmark
benchmarks=(
    "10,1"
    "100,2"
    "500,5"
    "1000,10"
    "5000,20"
    "10000,50"
    "20000,100"
    "50000,200"
)

mkdir -p benchmarks

for bench in "${benchmarks[@]}"; do
    IFS=',' read n c <<< "$bench"
    ab -n $n -c $c "http://localhost:5000/admin" > "benchmarks/$n-$c.txt"
done

echo "Benchmarks completed."
