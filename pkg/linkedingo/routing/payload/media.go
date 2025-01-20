package payload

import "encoding/json"

type MediaUploadType string

const (
	MediaUploadTypePhotoAttachment MediaUploadType = "MESSAGING_PHOTO_ATTACHMENT"
	MediaUploadFileAttachment      MediaUploadType = "MESSAGING_FILE_ATTACHMENT"
)

type UploadMediaMetadataPayload struct {
	MediaUploadType MediaUploadType `json:"mediaUploadType,omitempty"`
	FileSize        int             `json:"fileSize,omitempty"`
	Filename        string          `json:"filename,omitempty"`
}

func (p UploadMediaMetadataPayload) Encode() ([]byte, error) {
	return json.Marshal(p)
}
