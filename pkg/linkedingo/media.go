package linkedingo

import (
	"fmt"

	"github.com/beeper/linkedin/pkg/linkedingo/routing"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/payload"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/query"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

func (c *Client) UploadMedia(mediaUploadType payload.MediaUploadType, fileName string, mediaBytes []byte, contentType types.ContentType) (*response.MediaMetadata, error) {
	uploadMetadataQuery := query.DoActionQuery{
		Action: query.ACTION_UPLOAD,
	}
	uploadMetadataPayload := payload.UploadMediaMetadataPayload{
		MediaUploadType: mediaUploadType,
		FileSize:        len(mediaBytes),
		Filename:        fileName,
	}

	_, respData, err := c.MakeRoutingRequest(routing.VOYAGER_MEDIA_UPLOAD_METADATA_URL, uploadMetadataPayload, uploadMetadataQuery)
	if err != nil {
		return nil, err
	}

	metaDataResp, ok := respData.(*response.UploadMediaMetadataResponse)
	if !ok {
		return nil, newErrorResponseTypeAssertFailed("*response.UploadMediaMetadataResponse")
	}

	metaData := metaDataResp.Data.Value
	uploadUrl := metaData.SingleUploadURL

	uploadHeaders := c.buildHeaders(types.HeaderOpts{WithCookies: true, WithCsrfToken: true})
	resp, _, err := c.MakeRequest(uploadUrl, "PUT", uploadHeaders, mediaBytes, contentType)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode > 204 {
		return nil, fmt.Errorf("failed to upload media with file name %s (statusCode=%d)", fileName, resp.StatusCode)
	}

	return &metaData, err
}
