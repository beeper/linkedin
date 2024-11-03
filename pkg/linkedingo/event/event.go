package event

import (
	"time"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type MessageEvent struct {
	Message response.MessageElement
}

type SystemMessageEvent struct {
	Message response.MessageElement
}

type MessageEditedEvent struct {
	Message response.MessageElement
}

type MessageDeleteEvent struct {
	Message response.MessageElement
}

type MessageSeenEvent struct {
	Receipt response.MessageSeenReceipt
}

type MessageReactionEvent struct {
	Reaction response.MessageReaction
}

type UserPresenceEvent struct {
	FsdProfileId string
	Status       types.PresenceAvailabilityStatus
	LastActiveAt time.Time
}

type TypingIndicatorEvent struct {
	Indicator response.TypingIndicator
}

// this event is responsible for most thread updates like:
// Title changes, archived, unarchived etc
type ThreadUpdateEvent struct {
	Thread response.ThreadElement
}

type ThreadDeleteEvent struct {
	Thread response.Conversation
}

type ConnectionReady struct{}

type ConnectionClosed struct {
	Reason types.ConnectionClosedReason
}
