package types

type ContentType string

const (
	ContentTypeJSON                   ContentType = "application/json"
	ContentTypeJSONPlaintextUTF8      ContentType = "application/json; charset=UTF-8"
	ContentTypeJSONLinkedInNormalized ContentType = "application/vnd.linkedin.normalized+json+2.1"
	ContentTypeGraphQL                ContentType = "application/graphql"
	ContentTypeTextEventStream        ContentType = "text/event-stream"
	ContentTypePlaintextUTF8          ContentType = "text/plain;charset=UTF-8"
)

type HeaderOpts struct {
	WithCookies         bool
	WithCsrfToken       bool
	WithXLiTrack        bool
	WithXLiPageInstance bool
	WithXLiProtocolVer  bool
	WithXLiLang         bool
	Referer             string
	Origin              string
	Extra               map[string]string
}
