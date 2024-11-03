package raw

import (
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type DecoratedEventResponse struct {
	Topic               string                `json:"topic,omitempty"`
	PublisherTrackingID string                `json:"publisherTrackingId,omitempty"`
	LeftServerAt        int64                 `json:"leftServerAt,omitempty"`
	ID                  string                `json:"id,omitempty"`
	Payload             DecoratedEventPayload `json:"payload,omitempty"`
	TrackingID          string                `json:"trackingId,omitempty"`
}

type DecoratedEventPayload struct {
	Data         DecoratedEventData               `json:"data,omitempty"`
	Metadata     Metadata                         `json:"$metadata,omitempty"`
	LastActiveAt int64                            `json:"lastActiveAt,omitempty"`
	Availability types.PresenceAvailabilityStatus `json:"availability,omitempty"`
}

type DecoratedMessageRealtime struct {
	Result     response.MessageElement `json:"result,omitempty"`
	RecipeType string                  `json:"_recipeType,omitempty"`
	Type       string                  `json:"_type,omitempty"`
}

type DecoratedSeenReceipt struct {
	Result     response.MessageSeenReceipt `json:"result,omitempty"`
	RecipeType string                      `json:"_recipeType,omitempty"`
	Type       string                      `json:"_type,omitempty"`
}

type DecoratedTypingIndiciator struct {
	Result     response.TypingIndicator `json:"result,omitempty"`
	RecipeType string                   `json:"_recipeType,omitempty"`
	Type       string                   `json:"_type,omitempty"`
}

type DecoratedMessageReaction struct {
	Result     response.MessageReaction `json:"result,omitempty"`
	RecipeType string                   `json:"_recipeType,omitempty"`
	Type       string                   `json:"_type,omitempty"`
}

type DecoratedDeletedConversation struct {
	Result     response.Conversation `json:"result,omitempty"`
	RecipeType string                `json:"_recipeType,omitempty"`
	Type       string                `json:"_type,omitempty"`
}

type DecoratedUpdatedConversation struct {
	Result     response.ThreadElement `json:"result,omitempty"`
	RecipeType string                 `json:"_recipeType,omitempty"`
	Type       string                 `json:"_type,omitempty"`
}

type DecoratedEventData struct {
	RecipeType                   string                        `json:"_recipeType,omitempty"`
	Type                         string                        `json:"_type,omitempty"`
	DecoratedMessage             *DecoratedMessageRealtime     `json:"doDecorateMessageMessengerRealtimeDecoration,omitempty"`
	DecoratedSeenReceipt         *DecoratedSeenReceipt         `json:"doDecorateSeenReceiptMessengerRealtimeDecoration,omitempty"`
	DecoratedTypingIndicator     *DecoratedTypingIndiciator    `json:"doDecorateTypingIndicatorMessengerRealtimeDecoration,omitempty"`
	DecoratedMessageReaction     *DecoratedMessageReaction     `json:"doDecorateRealtimeReactionSummaryMessengerRealtimeDecoration,omitempty"`
	DecoratedDeletedConversation *DecoratedDeletedConversation `json:"doDecorateConversationDeleteMessengerRealtimeDecoration,omitempty"`
	DecoratedUpdatedConversation *DecoratedUpdatedConversation `json:"doDecorateConversationMessengerRealtimeDecoration,omitempty"`
}

type Metadata struct{}
