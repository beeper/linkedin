package connector

import (
	"context"
	"path"
	"time"

	"github.com/rs/zerolog"
	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/networkid"
	"maunium.net/go/mautrix/bridgev2/simplevent"

	"github.com/beeper/linkedin/pkg/linkedingo/event"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
)

func (lc *LinkedInClient) HandleLinkedInEvent(rawEvt any) {
	switch evtData := rawEvt.(type) {
	case event.MessageEvent, event.MessageEditedEvent:
		message := evtData.(event.MessageEvent).Message
		sender := message.Sender
		isFromMe := sender.HostIdentityUrn == string(lc.userLogin.ID)

		msgType := bridgev2.RemoteEventMessage
		switch rawEvt.(type) {
		case event.MessageEditedEvent:
			msgType = bridgev2.RemoteEventEdit
		}

		lc.connector.br.QueueRemoteEvent(lc.userLogin, &simplevent.Message[*response.MessageElement]{
			EventMeta: simplevent.EventMeta{
				Type: msgType,
				LogContext: func(c zerolog.Context) zerolog.Context {
					return c.
						Str("message_id", message.EntityUrn).
						Str("sender", sender.HostIdentityUrn).
						Str("sender_login", path.Base(sender.ParticipantType.Member.ProfileURL)).
						Bool("is_from_me", isFromMe)
				},
				PortalKey:    lc.MakePortalKey(lc.threadCache[message.Conversation.EntityUrn]),
				CreatePortal: false, // todo debate
				Sender: bridgev2.EventSender{
					IsFromMe:    isFromMe,
					SenderLogin: networkid.UserLoginID(sender.HostIdentityUrn),
					Sender:      networkid.UserID(sender.HostIdentityUrn),
				},
				Timestamp: time.UnixMilli(message.DeliveredAt),
			},
			ID:                 networkid.MessageID(message.EntityUrn),
			TargetMessage:      networkid.MessageID(message.EntityUrn),
			Data:               &message,
			ConvertMessageFunc: lc.convertToMatrix,
			ConvertEditFunc:    lc.convertEditToMatrix,
		})
	case event.MessageReactionEvent:
		reactionRemoteEvent := lc.wrapReaction(evtData.Reaction)
		lc.connector.br.QueueRemoteEvent(lc.userLogin, reactionRemoteEvent)
	case event.MessageDeleteEvent:
		messageDeleteRemoteEvent := &simplevent.MessageRemove{
			EventMeta: simplevent.EventMeta{
				Type:      bridgev2.RemoteEventMessageRemove,
				PortalKey: lc.MakePortalKey(lc.threadCache[evtData.Message.Conversation.EntityUrn]),
				LogContext: func(c zerolog.Context) zerolog.Context {
					return c.
						Str("message_id", evtData.Message.EntityUrn)
				},
				Timestamp: time.UnixMilli(evtData.Message.DeliveredAt),
			},
			TargetMessage: networkid.MessageID(evtData.Message.EntityUrn),
		}
		lc.connector.br.QueueRemoteEvent(lc.userLogin, messageDeleteRemoteEvent)
	case event.MessageSeenEvent:
		//
	case event.TypingIndicatorEvent:
		lc.connector.br.QueueRemoteEvent(lc.userLogin, &simplevent.Typing{
			EventMeta: simplevent.EventMeta{
				Type:       bridgev2.RemoteEventTyping,
				LogContext: nil,
				PortalKey: networkid.PortalKey{
					ID:       networkid.PortalID(evtData.Indicator.Conversation.EntityUrn),
					Receiver: lc.userLogin.ID,
				}, // todo use function (make by id)
				Sender: bridgev2.EventSender{
					IsFromMe: evtData.Indicator.TypingParticipant.HostIdentityUrn == string(lc.userLogin.ID),
					Sender:   networkid.UserID(evtData.Indicator.TypingParticipant.HostIdentityUrn),
				}, // todo use function
				Timestamp: time.Now(),
			},
			Timeout: 15 * time.Second,
			Type:    bridgev2.TypingTypeText,
		})
	case event.ThreadUpdateEvent:
		evt := &simplevent.ChatResync{
			EventMeta: simplevent.EventMeta{
				Type: bridgev2.RemoteEventChatResync,
				LogContext: func(c zerolog.Context) zerolog.Context {
					return c.
						Str("portal_key", evtData.Thread.EntityUrn)
				},
				PortalKey:    lc.MakePortalKey(evtData.Thread),
				CreatePortal: true,
			},
			ChatInfo:        lc.ConversationToChatInfo(&evtData.Thread),
			LatestMessageTS: time.UnixMilli(evtData.Thread.LastActivityAt),
		}
		lc.connector.br.QueueRemoteEvent(lc.userLogin, evt)
	case event.ThreadDeleteEvent:
		portalDeleteRemoteEvent := &simplevent.ChatDelete{
			EventMeta: simplevent.EventMeta{
				Type:      bridgev2.RemoteEventChatDelete,
				PortalKey: lc.MakePortalKey(lc.threadCache[evtData.Thread.EntityUrn]),
				LogContext: func(c zerolog.Context) zerolog.Context {
					return c.
						Str("conversation_id", evtData.Thread.EntityUrn)
				},
				Timestamp: time.Now(),
			},
			OnlyForMe: true,
		}
		lc.connector.br.QueueRemoteEvent(lc.userLogin, portalDeleteRemoteEvent)
		lc.client.Logger.Info().Any("data", evtData).Msg("Deleted conversation")
	default:
		lc.client.Logger.Warn().Any("event_data", evtData).Msg("Received unhandled event case from linkedin library")
	}
}

func (lc *LinkedInClient) wrapReaction(reaction response.MessageReaction) *simplevent.Reaction {
	var eventType bridgev2.RemoteEventType
	if reaction.ReactionAdded {
		eventType = bridgev2.RemoteEventReaction
	} else {
		eventType = bridgev2.RemoteEventReactionRemove
	}

	messageData, _ := lc.connector.br.DB.Message.GetFirstPartByID(context.TODO(), lc.userLogin.ID, networkid.MessageID(reaction.Message.EntityUrn))

	return &simplevent.Reaction{
		EventMeta: simplevent.EventMeta{
			Type: eventType,
			LogContext: func(c zerolog.Context) zerolog.Context {
				return c.
					Str("message_id", reaction.Message.EntityUrn).
					Str("sender", reaction.Actor.HostIdentityUrn).
					Str("emoji_reaction", reaction.ReactionSummary.Emoji)
			},
			PortalKey: messageData.Room,
			Timestamp: time.Now(),
			Sender: bridgev2.EventSender{
				IsFromMe: reaction.Actor.HostIdentityUrn == string(lc.userLogin.ID),
				Sender:   networkid.UserID(reaction.Actor.HostIdentityUrn),
			},
		},
		EmojiID:       "",
		Emoji:         reaction.ReactionSummary.Emoji,
		TargetMessage: networkid.MessageID(reaction.Message.EntityUrn),
	}
}
