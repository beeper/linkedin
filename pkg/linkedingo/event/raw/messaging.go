package raw

import "github.com/beeper/linkedin/pkg/linkedingo/event"

func (p *DecoratedEventData) ToMessageEvent() event.MessageEvent {
	return event.MessageEvent{
		Message: p.DecoratedMessage.Result,
	}
}

func (p *DecoratedEventData) ToSystemMessageEvent() event.SystemMessageEvent {
	return event.SystemMessageEvent{
		Message: p.DecoratedMessage.Result,
	}
}

func (p *DecoratedEventData) ToMessageEditedEvent() event.MessageEditedEvent {
	return event.MessageEditedEvent{
		Message: p.DecoratedMessage.Result,
	}
}

func (p *DecoratedEventData) ToMessageDeleteEvent() event.MessageDeleteEvent {
	return event.MessageDeleteEvent{
		Message: p.DecoratedMessage.Result,
	}
}

func (p *DecoratedEventData) ToMessageSeenEvent() event.MessageSeenEvent {
	return event.MessageSeenEvent{
		Receipt: p.DecoratedSeenReceipt.Result,
	}
}

func (p *DecoratedEventData) ToMessageReactionEvent() event.MessageReactionEvent {
	return event.MessageReactionEvent{
		Reaction: p.DecoratedMessageReaction.Result,
	}
}

func (p *DecoratedEventData) ToTypingIndicatorEvent() event.TypingIndicatorEvent {
	return event.TypingIndicatorEvent{
		Indicator: p.DecoratedTypingIndicator.Result,
	}
}

func (p *DecoratedEventData) ToThreadUpdateEvent() event.ThreadUpdateEvent {
	return event.ThreadUpdateEvent{
		Thread: p.DecoratedUpdatedConversation.Result,
	}
}

func (p *DecoratedEventData) ToThreadDeleteEvent() event.ThreadDeleteEvent {
	return event.ThreadDeleteEvent{
		Thread: p.DecoratedDeletedConversation.Result,
	}
}
