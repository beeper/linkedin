package raw

import (
	"github.com/beeper/linkedin/pkg/linkedingo/event"

	"time"
)

func (p *DecoratedEventPayload) ToPresenceStatusUpdateEvent(fsdProfileId string) event.UserPresenceEvent {
	return event.UserPresenceEvent{
		FsdProfileId: fsdProfileId,
		Status:       p.Availability,
		LastActiveAt: time.UnixMilli(p.LastActiveAt),
	}
}
