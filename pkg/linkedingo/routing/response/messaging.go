package response

import (
	"encoding/json"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/payload"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/query"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type Metadata struct {
	NextCursor       string `json:"nextCursor,omitempty"`
	PrevCursor       string `json:"prevCursor,omitempty"`
	NewSyncToken     string `json:"newSyncToken,omitempty"`
	RecipeType       string `json:"_recipeType,omitempty"`
	Type             string `json:"_type,omitempty"`
	ShouldClearCache bool   `json:"shouldClearCache,omitempty"`
	DeletedUrns      []any  `json:"deletedUrns,omitempty"`
}

type DisabledFeatures struct {
	Type            string `json:"_type,omitempty"`
	DisabledFeature string `json:"disabledFeature,omitempty"`
	ReasonText      any    `json:"reasonText,omitempty"`
	RecipeType      string `json:"_recipeType,omitempty"`
}

type Creator struct {
	HostIdentityUrn       string                `json:"hostIdentityUrn,omitempty"`
	Preview               any                   `json:"preview,omitempty"`
	EntityUrn             string                `json:"entityUrn,omitempty"`
	ShowPremiumInBug      bool                  `json:"showPremiumInBug,omitempty"`
	ShowVerificationBadge bool                  `json:"showVerificationBadge,omitempty"`
	Type                  string                `json:"_type,omitempty"`
	ParticipantType       types.ParticipantType `json:"participantType,omitempty"`
	RecipeType            string                `json:"_recipeType,omitempty"`
	BackendUrn            string                `json:"backendUrn,omitempty"`
}

type Sender struct {
	HostIdentityUrn       string `json:"hostIdentityUrn,omitempty"`
	Type                  string `json:"_type,omitempty"`
	RecipeType            string `json:"_recipeType,omitempty"`
	EntityUrn             string `json:"entityUrn,omitempty"`
	ShowPremiumInBug      bool   `json:"showPremiumInBug,omitempty"`
	ShowVerificationBadge bool   `json:"showVerificationBadge,omitempty"`
}

type Conversation struct {
	RecipeType string `json:"_recipeType,omitempty"`
	Type       string `json:"_type,omitempty"`
	EntityUrn  string `json:"entityUrn,omitempty"`
}

type MessageBodyRenderFormat string

const (
	RenderFormatDefault  MessageBodyRenderFormat = "DEFAULT"
	RenderFormatEdited   MessageBodyRenderFormat = "EDITED"
	RenderFormatReCalled MessageBodyRenderFormat = "RECALLED"
	RenderFormatSystem   MessageBodyRenderFormat = "SYSTEM"
)

type MessageElement struct {
	ReactionSummaries         []ReactionSummary             `json:"reactionSummaries,omitempty"`
	Footer                    any                           `json:"footer,omitempty"`
	Subject                   any                           `json:"subject,omitempty"`
	Type                      string                        `json:"_type,omitempty"`
	InlineWarning             any                           `json:"inlineWarning,omitempty"`
	Body                      payload.MessageBody           `json:"body,omitempty"`
	RecipeType                string                        `json:"_recipeType,omitempty"`
	OriginToken               string                        `json:"originToken,omitempty"`
	BackendUrn                string                        `json:"backendUrn,omitempty"`
	DeliveredAt               int64                         `json:"deliveredAt,omitempty"`
	Actor                     types.ConversationParticipant `json:"actor,omitempty"`
	RenderContentFallbackText any                           `json:"renderContentFallbackText,omitempty"`
	EntityUrn                 string                        `json:"entityUrn,omitempty"`
	Sender                    types.ConversationParticipant `json:"sender,omitempty"`
	BackendConversationUrn    string                        `json:"backendConversationUrn,omitempty"`
	IncompleteRetriableData   bool                          `json:"incompleteRetriableData,omitempty"`
	MessageBodyRenderFormat   MessageBodyRenderFormat       `json:"messageBodyRenderFormat,omitempty"`
	RenderContent             []payload.RenderContent       `json:"renderContent,omitempty"`
	Conversation              Conversation                  `json:"conversation,omitempty"`
	PreviousMessages          Messages                      `json:"previousMessages,omitempty"`
}

type Messages struct {
	Type       string           `json:"_type,omitempty"`
	RecipeType string           `json:"_recipeType,omitempty"`
	Messages   []MessageElement `json:"elements,omitempty"`
}

type ThreadElement struct {
	NotificationStatus                  string                          `json:"notificationStatus,omitempty"`
	ConversationParticipants            []types.ConversationParticipant `json:"conversationParticipants,omitempty"`
	UnreadCount                         int                             `json:"unreadCount,omitempty"`
	ConversationVerificationLabel       any                             `json:"conversationVerificationLabel,omitempty"`
	LastActivityAt                      int64                           `json:"lastActivityAt,omitempty"`
	DescriptionText                     any                             `json:"descriptionText,omitempty"`
	ConversationVerificationExplanation any                             `json:"conversationVerificationExplanation,omitempty"`
	Title                               string                          `json:"title,omitempty"`
	BackendUrn                          string                          `json:"backendUrn,omitempty"`
	ShortHeadlineText                   any                             `json:"shortHeadlineText,omitempty"`
	CreatedAt                           int64                           `json:"createdAt,omitempty"`
	LastReadAt                          int64                           `json:"lastReadAt,omitempty"`
	HostConversationActions             []any                           `json:"hostConversationActions,omitempty"`
	EntityUrn                           string                          `json:"entityUrn,omitempty"`
	Categories                          []query.InboxCategory           `json:"categories,omitempty"`
	State                               any                             `json:"state,omitempty"`
	DisabledFeatures                    []DisabledFeatures              `json:"disabledFeatures,omitempty"`
	Creator                             Creator                         `json:"creator,omitempty"`
	Read                                bool                            `json:"read,omitempty"`
	GroupChat                           bool                            `json:"groupChat,omitempty"`
	Type                                string                          `json:"_type,omitempty"`
	ContentMetadata                     any                             `json:"contentMetadata,omitempty"`
	RecipeType                          string                          `json:"_recipeType,omitempty"`
	ConversationURL                     string                          `json:"conversationUrl,omitempty"`
	HeadlineText                        any                             `json:"headlineText,omitempty"`
	IncompleteRetriableData             bool                            `json:"incompleteRetriableData,omitempty"`
	MessageElements                     Messages                        `json:"messages,omitempty"`
	ConversationTypeText                any                             `json:"conversationTypeText,omitempty"`
}

type MessageSeenReceipt struct {
	Type              string                        `json:"_type,omitempty"`
	SeenAt            int64                         `json:"seenAt,omitempty"`
	RecipeType        string                        `json:"_recipeType,omitempty"`
	Message           MessageReceiptData            `json:"message,omitempty"`
	SeenByParticipant types.ConversationParticipant `json:"seenByParticipant,omitempty"`
}

type MessageReceiptData struct {
	RecipeType string `json:"_recipeType,omitempty"`
	Type       string `json:"_type,omitempty"`
	EntityUrn  string `json:"entityUrn,omitempty"`
}

type MessengerConversationsResponse struct {
	Type       string          `json:"_type,omitempty"`
	Metadata   Metadata        `json:"metadata,omitempty"`
	RecipeType string          `json:"_recipeType,omitempty"`
	Threads    []ThreadElement `json:"elements,omitempty"`
}

type MessengerMessagesResponse struct {
	Type       string           `json:"_type,omitempty"`
	Metadata   Metadata         `json:"metadata,omitempty"`
	RecipeType string           `json:"_recipeType,omitempty"`
	Messages   []MessageElement `json:"elements,omitempty"`
}

type MessengerMessagingParticipantsByMessageAndEmojiResponse struct {
	Type         string                          `json:"_type,omitempty"`
	Metadata     Metadata                        `json:"metadata,omitempty"`
	RecipeType   string                          `json:"_recipeType,omitempty"`
	Participants []types.ConversationParticipant `json:"elements,omitempty"`
}

type TypingIndicator struct {
	Type              string                        `json:"_type,omitempty"`
	TypingParticipant types.ConversationParticipant `json:"typingParticipant,omitempty"`
	RecipeType        string                        `json:"_recipeType,omitempty"`
	Conversation      Conversation                  `json:"conversation,omitempty"`
}

type ShortMessageElement struct {
	RecipeType string `json:"_recipeType,omitempty"`
	Type       string `json:"_type,omitempty"`
	EntityUrn  string `json:"entityUrn,omitempty"`
}

type ReactionSummary struct {
	Count          int    `json:"count,omitempty"`
	Type           string `json:"_type,omitempty"`
	FirstReactedAt int64  `json:"firstReactedAt,omitempty"`
	Emoji          string `json:"emoji,omitempty"`
	RecipeType     string `json:"_recipeType,omitempty"`
	ViewerReacted  bool   `json:"viewerReacted,omitempty"`
}

type MessageReaction struct {
	ReactionAdded   bool                          `json:"reactionAdded,omitempty"`
	Type            string                        `json:"_type,omitempty"`
	Actor           types.ConversationParticipant `json:"actor,omitempty"`
	RecipeType      string                        `json:"_recipeType,omitempty"`
	Message         ShortMessageElement           `json:"message,omitempty"`
	ReactionSummary ReactionSummary               `json:"reactionSummary,omitempty"`
}

type MessageSentResponse struct {
	Data MessageSentData `json:"value,omitempty"`
}

func (r MessageSentResponse) Decode(data []byte) (any, error) {
	respData := &MessageSentResponse{}
	return respData, json.Unmarshal(data, &respData)
}

type MessageSentData struct {
	RenderContentUnions    []payload.RenderContent `json:"renderContentUnions,omitempty"`
	EntityUrn              string                  `json:"entityUrn,omitempty"`
	BackendConversationUrn string                  `json:"backendConversationUrn,omitempty"`
	SenderUrn              string                  `json:"senderUrn,omitempty"`
	OriginToken            string                  `json:"originToken,omitempty"`
	Body                   payload.MessageBody     `json:"body,omitempty"`
	BackendUrn             string                  `json:"backendUrn,omitempty"`
	ConversationUrn        string                  `json:"conversationUrn,omitempty"`
	DeliveredAt            int64                   `json:"deliveredAt,omitempty"`
}

type MarkThreadReadResponse struct {
	Results map[string]MarkThreadReadResult `json:"results,omitempty"`
	Errors  any                             `json:"errors,omitempty"`
}

type MarkThreadReadResult struct {
	Status int `json:"status,omitempty"`
}
