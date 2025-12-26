// common/crypto.go
package common

import (
	"crypto/cipher"
	"crypto/rand"
	"golang.org/x/crypto/chacha20poly1305"
	"golang.org/x/crypto/poly1305"
)

const (
	NonceSize   = chacha20poly1305.NonceSizeX
	KeySize     = chacha20poly1305.KeySize
	Overhead    = poly1305.TagSize
	SessionIDSize = 8
)

func NewAEAD(key []byte) (cipher.AEAD, error) {
	return chacha20poly1305.NewX(key)
}

func GenerateSessionID() []byte {
	id := make([]byte, SessionIDSize)
	rand.Read(id)
	return id
}

func GenerateNonce() []byte {
	nonce := make([]byte, NonceSize)
	rand.Read(nonce)
	return nonce
}
