package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/config"
	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/server"
)

func main() {
	configPath := flag.String("config", "/etc/sg-gateway/sgnet.json", "path to SG-Net server config")
	check := flag.Bool("check", false, "validate configuration and exit")
	flag.Parse()

	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "sgnet-server: invalid configuration")
		os.Exit(2)
	}
	if *check {
		fmt.Println("sgnet-server: configuration OK")
		return
	}
	srv, err := server.New(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, "sgnet-server: initialization failed")
		os.Exit(2)
	}
	if err := srv.Serve(); err != nil {
		fmt.Fprintln(os.Stderr, "sgnet-server: server stopped")
		os.Exit(1)
	}
}
