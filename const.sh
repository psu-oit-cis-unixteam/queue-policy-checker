#!/usr/bin/env bash

function fibonacciWait {
    a=0
    b=1
    i=0
    while [ $i -lt $1 ]
    do
        echo -n '*'
        sleep $a
        let sum=$a+$b
        let a=$b
        let b=$sum
        let i=$i+1
    done
    echo
}

doAndWait(){
    ./queue_check --who Nobody
    fibonacciWait 7
}

while true; do
    doAndWait
done;
