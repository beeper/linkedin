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
	LinkedInMessagingBaseURL: {
		Method: http.MethodGet,
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
	LinkedInVoyagerMessagingGraphQLURL: {
		Method: http.MethodGet,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiTrack:        true,
			WithXLiPageInstance: true,
			WithXLiProtocolVer:  true,
			Referer:             string(LinkedInMessagingBaseURL) + "/",
			Extra: map[string]string{
				"accept": string(types.ContentTypeGraphQL),
			},
		},
		ResponseDefinition: response.GraphQlResponse{},
	},
	LinkedInVoyagerMessagingDashMessengerMessagesURL: {
		Method:      http.MethodPost,
		ContentType: types.ContentTypePlaintextUTF8,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiLang:         true,
			WithXLiPageInstance: true,
			WithXLiTrack:        true,
			WithXLiProtocolVer:  true,
			Origin:              string(LinkedInBaseURL),
			Extra: map[string]string{
				"accept": string(types.ContentTypeJSON),
			},
		},
		ResponseDefinition: response.MessageSentResponse{},
	},
	LinkedInMessagingDashMessengerConversationsURL: {
		Method:      http.MethodPost,
		ContentType: types.ContentTypePlaintextUTF8,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiTrack:        true,
			WithXLiPageInstance: true,
			WithXLiProtocolVer:  true,
			WithXLiLang:         true,
			Origin:              string(LinkedInBaseURL),
			Extra: map[string]string{
				"accept": string(types.ContentTypeJSON),
			},
		},
	},
	LinkedInVoyagerMediaUploadMetadataURL: {
		Method:      http.MethodPost,
		ContentType: types.ContentTypeJSONPlaintextUTF8,
		HeaderOpts: types.HeaderOpts{
			WithCookies:         true,
			WithCsrfToken:       true,
			WithXLiTrack:        true,
			WithXLiPageInstance: true,
			WithXLiProtocolVer:  true,
			WithXLiLang:         true,
			Extra: map[string]string{
				"accept": string(types.ContentTypeJSONLinkedInNormalized),
			},
		},
		ResponseDefinition: response.UploadMediaMetadataResponse{},
	},
	LinkedInLogoutURL: {
		Method: http.MethodGet,
		HeaderOpts: types.HeaderOpts{
			WithCookies: true,
		},
	},
}
