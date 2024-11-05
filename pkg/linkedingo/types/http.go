package types

type ContentType string

const (
	NONE                     ContentType = ""
	JSON                     ContentType = "application/json"
	JSON_PLAINTEXT_UTF8      ContentType = "application/json; charset=UTF-8"
	JSON_LINKEDIN_NORMALIZED ContentType = "application/vnd.linkedin.normalized+json+2.1"
	FORM                     ContentType = "application/x-www-form-urlencoded"
	GRAPHQL                  ContentType = "application/graphql"
	TEXT_EVENTSTREAM         ContentType = "text/event-stream"
	PLAINTEXT_UTF8           ContentType = "text/plain;charset=UTF-8"
	IMAGE_JPEG               ContentType = "image/jpeg"
	VIDEO_MP4                ContentType = "video/mp4"
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
