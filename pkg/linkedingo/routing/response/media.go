package response

import "encoding/json"

type UploadMediaMetadataResponse struct {
	Data     MediaMetadataValue `json:"data,omitempty"`
	Included []any              `json:"included,omitempty"`
}

func (r UploadMediaMetadataResponse) Decode(data []byte) (any, error) {
	respData := &UploadMediaMetadataResponse{}
	return respData, json.Unmarshal(data, &respData)
}

type SingleUploadHeaders struct {
}
type MediaMetadata struct {
	Urn                 string              `json:"urn,omitempty"`
	MediaArtifactUrn    string              `json:"mediaArtifactUrn,omitempty"`
	Recipes             []string            `json:"recipes,omitempty"`
	SingleUploadHeaders SingleUploadHeaders `json:"singleUploadHeaders,omitempty"`
	AssetRealtimeTopic  string              `json:"assetRealtimeTopic,omitempty"`
	PollingURL          string              `json:"pollingUrl,omitempty"`
	SingleUploadURL     string              `json:"singleUploadUrl,omitempty"`
	Type                string              `json:"type,omitempty"`
	Type0               string              `json:"$type,omitempty"`
}
type MediaMetadataValue struct {
	Value MediaMetadata `json:"value,omitempty"`
	Type  string        `json:"$type,omitempty"`
}
