package payload

import (
	"encoding/json"

	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type SendMessagePayload struct {
	Message                      SendMessageData `json:"message,omitempty"`
	MailboxUrn                   string          `json:"mailboxUrn,omitempty"`
	TrackingID                   string          `json:"trackingId,omitempty"`
	DedupeByClientGeneratedToken bool            `json:"dedupeByClientGeneratedToken"`
	HostRecipientUrns            []string        `json:"hostRecipientUrns,omitempty"`
	ConversationTitle            string          `json:"conversationTitle,omitempty"`
}

func (p SendMessagePayload) Encode() ([]byte, error) {
	return json.Marshal(p)
}

type SendMessageData struct {
	Body                MessageBody     `json:"body,omitempty"`
	RenderContentUnions []RenderContent `json:"renderContentUnions,omitempty"`
	ConversationUrn     string          `json:"conversationUrn,omitempty"`
	OriginToken         string          `json:"originToken,omitempty"`
}

type AttributeBold struct {
	Typename   string `json:"__typename"`
	Type       string `json:"_type"`
	RecipeType string `json:"_recipeType"`
}

type AttributeKind struct {
	Hyperlink   any           `json:"hyperlink"`
	ListItem    any           `json:"listItem"`
	Paragraph   any           `json:"paragraph"`
	LineBreak   any           `json:"lineBreak"`
	Subscript   any           `json:"subscript"`
	Underline   any           `json:"underline"`
	Superscript any           `json:"superscript"`
	Bold        AttributeBold `json:"bold"`
	List        any           `json:"list"`
	Italic      any           `json:"italic"`
	Entity      any           `json:"entity"`
}

type Attributes struct {
	Start         int           `json:"start"`
	Length        int           `json:"length"`
	Type          string        `json:"_type"`
	RecipeType    string        `json:"_recipeType"`
	AttributeKind AttributeKind `json:"attributeKind"`
}

type MessageBody struct {
	Type       string       `json:"_type,omitempty"`
	Attributes []Attributes `json:"attributes,omitempty"`
	Text       string       `json:"text"`
	RecipeType string       `json:"_recipeType,omitempty"`
}

type StartTypingPayload struct {
	ConversationUrn string `json:"conversationUrn,omitempty"`
}

func (p StartTypingPayload) Encode() ([]byte, error) {
	return json.Marshal(p)
}

type DeleteMessagePayload struct {
	MessageUrn string `json:"messageUrn,omitempty"`
}

func (p DeleteMessagePayload) Encode() ([]byte, error) {
	return json.Marshal(p)
}

type RenderContent struct {
	Audio                         *Audio                   `json:"audio,omitempty"`
	AwayMessage                   any                      `json:"awayMessage,omitempty"`
	ConversationAdsMessageContent any                      `json:"conversationAdsMessageContent,omitempty"`
	ExternalMedia                 *ExternalMedia           `json:"externalMedia,omitempty"`
	File                          *File                    `json:"file,omitempty"`
	ForwardedMessageContent       *ForwardedMessageContent `json:"forwardedMessageContent,omitempty"`
	HostUrnData                   any                      `json:"hostUrnData,omitempty"`
	MessageAdRenderContent        any                      `json:"messageAdRenderContent,omitempty"`
	RepliedMessageContent         *RepliedMessageContent   `json:"repliedMessageContent,omitempty"`
	UnavailableContent            any                      `json:"unavailableContent,omitempty"`
	VectorImage                   *VectorImage             `json:"vectorImage,omitempty"`
	Video                         *Video                   `json:"video,omitempty"`
	VideoMeeting                  any                      `json:"videoMeeting,omitempty"`
}

type Video struct {
	Thumbnail struct {
		DigitalMediaAsset any    `json:"digitalmediaAsset,omitempty"`
		Type              string `json:"_type,omitempty"`
		Attribution       any    `json:"attribution,omitempty"`
		RecipeType        string `json:"_recipeType,omitempty"`
		FocalPoint        any    `json:"focalPoint,omitempty"`
		Artifacts         []struct {
			Width                         int    `json:"width,omitempty"`
			Type                          string `json:"_type,omitempty"`
			RecipeType                    string `json:"_recipeType,omitempty"`
			FileIdentifyingUrlPathSegment string `json:"fileIdentifyingUrlPathSegment,omitempty"`
			Height                        int    `json:"height,omitempty"`
		} `json:"artifacts,omitempty"`
		RootUrl string `json:"rootUrl,omitempty"`
	} `json:"thumbnail,omitempty"`
	ProgressiveStreams []struct {
		StreamingLocations []struct {
			Type       string `json:"_type,omitempty"`
			RecipeType string `json:"_recipeType,omitempty"`
			Url        string `json:"url,omitempty"`
			ExpiresAt  any    `json:"expiresAt,omitempty"`
		} `json:"streamingLocations,omitempty"`
		Size       int    `json:"size,omitempty"`
		BitRate    int    `json:"bitRate,omitempty"`
		Width      int    `json:"width,omitempty"`
		Type       string `json:"_type,omitempty"`
		MediaType  string `json:"mediaType,omitempty"`
		MimeType   any    `json:"mimeType,omitempty"`
		RecipeType string `json:"_recipeType,omitempty"`
		Height     int    `json:"height,omitempty"`
	} `json:"progressiveStreams,omitempty"`
	LiveStreamCreatedAt any     `json:"liveStreamCreatedAt,omitempty"`
	Transcripts         []any   `json:"transcripts,omitempty"`
	PrevMedia           any     `json:"prevMedia,omitempty"`
	Type                string  `json:"_type,omitempty"`
	AspectRatio         float64 `json:"aspectRatio,omitempty"`
	Media               string  `json:"media,omitempty"`
	RecipeType          string  `json:"_recipeType,omitempty"`
	AdaptiveStreams     []any   `json:"adaptiveStreams,omitempty"`
	LiveStreamEndedAt   any     `json:"liveStreamEndedAt,omitempty"`
	Duration            int     `json:"duration,omitempty"`
	EntityUrn           string  `json:"entityUrn,omitempty"`
	Provider            string  `json:"provider,omitempty"`
	NextMedia           any     `json:"nextMedia,omitempty"`
	TrackingId          string  `json:"trackingId,omitempty"`
}

type RepliedMessageContent struct {
	OriginalSenderUrn  string      `json:"originalSenderUrn,omitempty"`
	OriginalSendAt     int64       `json:"originalSendAt,omitempty"`
	OriginalMessageUrn string      `json:"originalMessageUrn,omitempty"`
	MessageBody        MessageBody `json:"messageBody,omitempty"`
}

type ForwardedMessageContent struct {
	RecipeType     string                        `json:"_recipeType,omitempty"`
	Type           string                        `json:"_type,omitempty"`
	FooterText     FooterText                    `json:"footerText,omitempty"`
	ForwardedBody  ForwardedBody                 `json:"forwardedBody,omitempty"`
	OriginalSendAt int64                         `json:"originalSendAt,omitempty"`
	OriginalSender types.ConversationParticipant `json:"originalSender,omitempty"`
}

type FooterText struct {
	RecipeType string `json:"_recipeType,omitempty"`
	Type       string `json:"_type,omitempty"`
	Attributes []any  `json:"attributes,omitempty"`
	Text       string `json:"text,omitempty"`
}

type ForwardedBody struct {
	RecipeType string `json:"_recipeType,omitempty"`
	Type       string `json:"_type,omitempty"`
	Attributes []any  `json:"attributes,omitempty"`
	Text       string `json:"text,omitempty"`
}

type Audio struct {
	Duration   int    `json:"duration,omitempty"`
	Type       string `json:"_type,omitempty"`
	RecipeType string `json:"_recipeType,omitempty"`
	URL        string `json:"url,omitempty"`
}

type VectorImage struct {
	DigitalmediaAsset string `json:"digitalmediaAsset,omitempty"`
	Type              string `json:"_type,omitempty"`
	Attribution       any    `json:"attribution,omitempty"`
	RecipeType        string `json:"_recipeType,omitempty"`
	FocalPoint        any    `json:"focalPoint,omitempty"`
	RootURL           string `json:"rootUrl,omitempty"`
	Artifacts         []any  `json:"artifacts,omitempty"`
}

type Media struct {
	Type           string `json:"_type,omitempty"`
	OriginalHeight int    `json:"originalHeight,omitempty"`
	RecipeType     string `json:"_recipeType,omitempty"`
	OriginalWidth  int    `json:"originalWidth,omitempty"`
	URL            string `json:"url,omitempty"`
}
type PreviewMedia struct {
	Type           string `json:"_type,omitempty"`
	OriginalHeight int    `json:"originalHeight,omitempty"`
	RecipeType     string `json:"_recipeType,omitempty"`
	OriginalWidth  int    `json:"originalWidth,omitempty"`
	URL            string `json:"url,omitempty"`
}

type ExternalMedia struct {
	Type         string       `json:"_type,omitempty"`
	Media        Media        `json:"media,omitempty"`
	Title        string       `json:"title,omitempty"`
	RecipeType   string       `json:"_recipeType,omitempty"`
	EntityUrn    string       `json:"entityUrn,omitempty"`
	PreviewMedia PreviewMedia `json:"previewMedia,omitempty"`
}

type File struct {
	AssetUrn   string            `json:"assetUrn,omitempty"`
	ByteSize   int               `json:"byteSize,omitempty"`
	MediaType  types.ContentType `json:"mediaType,omitempty"`
	Name       string            `json:"name,omitempty"`
	URL        string            `json:"url,omitempty"`
	Type       string            `json:"type,omitempty"`
	RecipeType string            `json:"_recipeType,omitempty"`
}

type MarkThreadReadBody struct {
	Read bool `json:"read"`
}

type SendReactionPayload struct {
	MessageUrn string `json:"messageUrn,omitempty"`
	Emoji      string `json:"emoji,omitempty"`
}

func (p SendReactionPayload) Encode() ([]byte, error) {
	return json.Marshal(p)
}
