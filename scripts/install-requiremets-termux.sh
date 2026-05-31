#!/usr/bin/env bash
# >>> bash scripts/install-requirements-termux.sh

file="$(pwd)/requirements-termux.txt"
pkg='python-psutil'

if ! command -v pip3 &> /dev/null; then
    echo '— Error: pip3 not found'
    exit 1
fi

spinner() {
    local pid=$1
    local frames=('[>   ]' '[=>  ]' '[==> ]' '[===>]'
        '[ ===>]' '[  ==>]' '[   =>]' '[    >]')
    local i=0
    while kill -0 $pid 2>/dev/null; do
        printf "\r%-60s" "${frames[$((i++%${#frames[@]}))]} • Install requirements, please wait"
        sleep 0.12
    done
    printf "\r\033[K"
    printf "| [===>] • OK"
}
run_cmd() {
    local cmd=$1
    local tmpfile=$(mktemp)
    trap 'rm -f "$tmpfile"' RETURN

    eval "$cmd" > "$tmpfile" 2>&1 &
    local pid=$!

    printf "— Run • %s\n| Command • \"%s\"\n" "$pid" "$cmd"
    spinner $pid
    wait $pid
    local exit_code=$?

    if [[ $exit_code -ge 1 ]]; then
        printf "\n— Error install requirements\n| Code • %s\n| PID  • %s\n| Logs •\n" "$exit_code" "$pid"
        while read -r line; do
            echo "|  $line"
        done < "$tmpfile"
        return 1
    else
        printf "\n— Successfully installed\n| Code • %s\n| PID  • %s\n" "$exit_code" "$pid"
    fi
}
run_cmd "pip3 install --upgrade pip"
run_cmd "pip3 install -r $file" || exit 1
if ! command -v pkg &> /dev/null; then
    echo '- Unknown command: pkg, skipping'
else
    run_cmd "pkg install $pkg" || exit 1
fi

read -p "- Install cryptg? [N/y] • " answer
if [[ ${answer,,} == "y" ]]; then
    run_cmd "pip3 install cryptg" || exit 1
fi
