package types

import "encoding/json"

type DeviceTrack struct {
	ClientVersion    string  `json:"clientVersion,omitempty"`
	MpVersion        string  `json:"mpVersion,omitempty"`
	OsName           string  `json:"osName,omitempty"`
	TimezoneOffset   int     `json:"timezoneOffset,omitempty"`
	Timezone         string  `json:"timezone,omitempty"`
	DeviceFormFactor string  `json:"deviceFormFactor,omitempty"`
	MpName           string  `json:"mpName,omitempty"`
	DisplayDensity   float64 `json:"displayDensity,omitempty"`
	DisplayWidth     float64 `json:"displayWidth,omitempty"`
	DisplayHeight    int     `json:"displayHeight,omitempty"`
}

func (dt *DeviceTrack) Encode() ([]byte, error) {
	return json.Marshal(dt)
}
