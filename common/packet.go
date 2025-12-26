// common/packet.go
package common

import (
	"encoding/binary"
	"math/rand"
)

const (
	MinFakeHeader = 18
	MaxFakeHeader = 32
	MaxPadding    = 64
)

func BuildStealthPacket(sessionID, seq []byte, payload []byte) []byte {
	// Fake QUIC-like header
	fakeLen := MinFakeHeader + rand.Intn(MaxFakeHeader-MinFakeHeader+1)
	fakeHeader := make([]byte, fakeLen)
	rand.Read(fakeHeader)

	// QUIC Initial packet mimic: first byte 0xc0 | long header
	fakeHeader[0] = 0xc0 | byte(rand.Intn(16))
	// Version-like field
	binary.BigEndian.PutUint32(fakeHeader[1:5], 0x00000001|uint32(rand.Intn(0xffffffff)))
	// Destination Connection ID length + ID
	fakeHeader[5] = 8
	copy(fakeHeader[6:14], sessionID)

	// Encrypted payload: nonce (24) + ciphertext + tag (16)
	paddingLen := rand.Intn(MaxPadding + 1)
	padding := make([]byte, paddingLen)
	rand.Read(padding)

	encrypted := append(payload, padding...)

	packet := append(fakeHeader, seq...)
	packet = append(packet, encrypted...)

	return packet
}

func ExtractPayload(data []byte) ([]byte, []byte, []byte) {
	if len(data) < MaxFakeHeader+8 {
		return nil, nil, nil
	}

	// Skip fake header (find longest possible that matches pattern, but we just take max)
	fakeLen := MaxFakeHeader
	if len(data) < fakeLen+8 {
		fakeLen = len(data) - 8
	}

	seq := data[fakeLen : fakeLen+8]
	payload := data[fakeLen+8:]

	return data[:fakeLen], seq, payload
}
