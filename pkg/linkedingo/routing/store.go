package routing

import (
	"net/http"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type PayloadDataInterface interface {
	Encode() ([]byte, error)
}

type ResponseDataInterface interface {
	Decode(data []byte) (any, error)
}

type RequestEndpointInfo struct {
	Method             string
	HeaderOpts         types.HeaderOpts
	ContentType        types.ContentType
	ResponseDefinition ResponseDataInterface
}

var RequestStoreDefinition = map[RequestEndpointURL]RequestEndpointInfo{
	MESSAGES_BASE_URL: {
		Method:      http.MethodGet,
		ContentType: types.NONE,
		HeaderOpts: types.HeaderOpts{
			WithCookies: true,
			Extra: map[string]string{
				"Sec-Fetch-Dest":            "document",
				"Sec-Fetch-Mode":            "navigate",
				"Sec-Fetch-Site":            "none",
				"Sec-Fetch-User":            "?1",
				"Upgrade-Insecure-Requests": "1",
			},
		},
	},
	VOYAGER_MESSAGING_GRAPHQL_URL: {
		Method:      http.MethodGet,
		ContentType: types.NONE,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiTrack:        true,
			WithXLiPageInstance: true,
			WithXLiProtocolVer:  true,
			Referer:             string(MESSAGES_BASE_URL) + "/",
			Extra: map[string]string{
				"accept": string(types.GRAPHQL),
			},
		},
		ResponseDefinition: response.GraphQlResponse{},
	},
	VOYAGER_MESSAGING_DASH_MESSENGER_MESSAGES_URL: {
		Method:      http.MethodPost,
		ContentType: types.PLAINTEXT_UTF8,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiLang:         true,
			WithXLiPageInstance: true,
			WithXLiTrack:        true,
			WithXLiProtocolVer:  true,
			Origin:              string(BASE_URL),
			Extra: map[string]string{
				"accept": string(types.JSON),
			},
		},
		ResponseDefinition: response.MessageSentResponse{},
	},
	VOYAGER_MESSAGING_DASH_MESSENGER_CONVERSATIONS_URL: {
		Method:      http.MethodPost,
		ContentType: types.PLAINTEXT_UTF8,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiTrack:        true,
			WithXLiPageInstance: true,
			WithXLiProtocolVer:  true,
			WithXLiLang:         true,
			Origin:              string(BASE_URL),
			Extra: map[string]string{
				"accept": string(types.JSON),
			},
		},
	},
	VOYAGER_MEDIA_UPLOAD_METADATA_URL: {
		Method:      http.MethodPost,
		ContentType: types.JSON_PLAINTEXT_UTF8,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiTrack:        true,
			WithXLiPageInstance: true,
			WithXLiProtocolVer:  true,
			WithXLiLang:         true,
			Extra: map[string]string{
				"accept": string(types.JSON_LINKEDIN_NORMALIZED),
			},
		},
		ResponseDefinition: response.UploadMediaMetadataResponse{},
	},
	LOGOUT_URL: {
		Method:      http.MethodGet,
		ContentType: types.NONE,
		HeaderOpts: types.HeaderOpts{
			WithCookies: true,
		},
	},
}
