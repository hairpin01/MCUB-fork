#!/usr/bin/env bash
# >>> bash scripts/install-requirements-termux.sh

file="$(pwd)/requirements-termux.txt"
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

if ! command -v pip3 &> /dev/null; then
    echo 'No install python-pip'
    exit 1
fi

cmd="pip3 install -r $file > $tmpfile"

spinner() {
    local pid=$1
    local frames='|\-/|'
    while kill -0 $pid 2>/dev/null; do
        for (( i=0; i<${#frames}; i++ )); do
            printf "\r${frames:$i:1} installing..."
            sleep 0.1
        done
    done
    printf "\r"
}

eval "$cmd" &
pid=$!
spinner $pid
wait $pid
exit_code=$?

if [[ $exit_code -ge 1 ]]; then
    printf "\nError install requirements termux\nerror code: $exit_code\nPID: $pid\nLogs:\n"
    while read -r line; do
        echo "$line"
    done < "$tmpfile"
    exit 1
else
    printf "\nSuccessfully install\nCode: $exit_code\nPID: $pid\n"
fi
