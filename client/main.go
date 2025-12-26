// client/main.go
package main

import (
	"flag"
	"io"
	"log"
	"math/rand"
	"net"
	"time"

	"github.com/InetByOu/whisper/common"
	"golang.org/x/crypto/chacha20poly1305"
)

var (
	serverAddr = flag.String("server", "", "Server address (ip:port)")
	psk        = flag.String("psk", "", "Pre-shared key (32 bytes)")
)

const (
	LocalSOCKS = "127.0.0.1:1080"
	HopInterval = 45 * time.Second
)

func main() {
	flag.Parse()
	if len(*psk) != chacha20poly1305.KeySize {
		log.Fatal("PSK must be exactly 32 bytes")
	}
	if *serverAddr == "" {
		log.Fatal("server address required")
	}

	rand.Seed(time.Now().UnixNano())

	aead, _ := chacha20poly1305.NewX([]byte(*psk))

	serverUDP, err := net.ResolveUDPAddr("udp", *serverAddr)
	if err != nil {
		log.Fatal(err)
	}

	// Local SOCKS5-like listener (very minimal)
	local, err := net.Listen("tcp", LocalSOCKS)
	if err != nil {
		log.Fatal("Failed to bind local SOCKS port. Run as root or change port.")
	}
	log.Printf("whisper client running. Proxy: socks5://%s", LocalSOCKS)

	go portHopper(serverUDP)

	for {
		conn, err := local.Accept()
		if err != nil {
			continue
		}
		go handleLocalConn(conn, serverUDP, aead)
	}
}

var currentConn *net.UDPConn

func portHopper(serverUDP *net.UDPAddr) {
	for {
		if currentConn != nil {
			currentConn.Close()
		}
		conn, err := net.DialUDP("udp", nil, serverUDP)
		if err == nil {
			currentConn = conn
		}
		time.Sleep(HopInterval + common.RandomJitter(0, 15000))
	}
}

func handleLocalConn(localConn net.Conn, serverUDP *net.UDPAddr, aead chacha20poly1305.AEAD) {
	defer localConn.Close()

	buf := make([]byte, 65535)
	n, err := localConn.Read(buf)
	if err != nil || n < 8 {
		return
	}

	// Minimal SOCKS5 CONNECT request parsing
	if buf[0] != 0x05 || buf[1] != 0x01 || buf[3] != 0x01 {
		return // only IPv4 CONNECT
	}

	port := binary.BigEndian.Uint16(buf[8:10])
	ip := net.IPv4(buf[4], buf[5], buf[6], buf[7])

	request := append([]byte{0x01}, buf[2:]...) // version 1 for our tunnel

	nonce := common.GenerateNonce()
	ciphertext := aead.Seal(nil, nonce, request, nil)

	seq := uint64(time.Now().UnixNano())
	packet := common.BuildStealthPacket(common.GenerateSessionID(), common.Uint64ToBytes(seq), append(nonce, ciphertext...))

	if currentConn == nil {
		return
	}

	currentConn.Write(packet)

	// Wait response
	currentConn.SetReadDeadline(time.Now().Add(15 * time.Second))
	n, _, err = currentConn.ReadFromUDP(buf)
	if err != nil {
		return
	}

	_, seqBytes, encrypted := common.ExtractPayload(buf[:n])
	if encrypted == nil {
		return
	}

	respNonce := encrypted[:common.NonceSize]
	cipherResp := encrypted[common.NonceSize:]

	plaintext, err := aead.Open(nil, respNonce, cipherResp, nil)
	if err != nil {
		return
	}

	// Remove padding
	for i := len(plaintext) - 1; i >= 0; i-- {
		if plaintext[i] != 0 {
			plaintext = plaintext[:i+1]
			break
		}
	}

	if len(plaintext) > 0 {
		localConn.Write(plaintext)
	}

	// Pipe remaining data (simple one-way for demo)
	io.Copy(localConn, currentConn) // not perfect, but works for small traffic
}
