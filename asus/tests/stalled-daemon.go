// Startup-failure fixture, never shipped as a release payload.
package main

import (
	"fmt"
	"os"
	"strings"
	"time"
)

var core string

func main() {
	if len(os.Args) > 1 && os.Args[1] == "--version" {
		fmt.Println(core)
		return
	}
	// Exercise the RAM logger with oversized lines as well as a log storm.
	for range 100 {
		fmt.Println(strings.Repeat("x", 65536))
	}
	for {
		time.Sleep(time.Second)
	}
}
