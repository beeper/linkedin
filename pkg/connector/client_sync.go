package connector

import (
	"context"
	"fmt"
	"path"
	"sort"
	"time"

	"github.com/rs/zerolog"
	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/networkid"
	"maunium.net/go/mautrix/bridgev2/simplevent"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/query"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
)

func (lc *LinkedInClient) syncChannels(ctx context.Context) {
	log := zerolog.Ctx(ctx)

	getThreadsVariables := query.GetThreadsVariables{
		Count:             20,
		LastUpdatedBefore: 0,
		NextCursor:        "",
	}
	conversations, err := lc.client.GetThreads(query.GetThreadsVariables{})
	if err != nil {
		log.Error().Err(err).Msg("failed to fetch initial inbox state:")
		return
	}

	threads := conversations.Threads
	getThreadsVariables.LastUpdatedBefore = threads[len(threads)-1].LastActivityAt
	getThreadsVariables.NextCursor = conversations.Metadata.NextCursor
	getThreadsVariables.SyncToken = conversations.Metadata.NewSyncToken

	hasMore := len(conversations.Threads) >= 20

	// loop until no more threads can be found
	for hasMore {
		moreConversations, err := lc.client.GetThreads(getThreadsVariables)
		if err != nil {
			log.Error().Err(err).Msg(fmt.Sprintf("failed to fetch threads in trusted inbox using cursor %v,%s:", getThreadsVariables.LastUpdatedBefore, getThreadsVariables.NextCursor))
			return
		}

		hasMore = len(moreConversations.Threads) > 0

		if !hasMore {
			continue
		}

		threads = append(threads, moreConversations.Threads...)

		getThreadsVariables.NextCursor = moreConversations.Metadata.NextCursor
		getThreadsVariables.LastUpdatedBefore = threads[len(threads)-1].LastActivityAt
		getThreadsVariables.SyncToken = moreConversations.Metadata.NextCursor
	}

	for _, thread := range threads {
		messages := thread.MessageElements.Messages
		sort.Slice(messages, func(j, i int) bool {
			return messages[j].DeliveredAt < messages[i].DeliveredAt
		})

		for _, participant := range thread.ConversationParticipants {
			if member := lc.userCache[participant.HostIdentityUrn]; member.Type != "" {
				continue
			}
			lc.userCache[participant.HostIdentityUrn] = participant.ParticipantType.Member
		}

		lc.threadCache[thread.EntityUrn] = thread

		evt := &simplevent.ChatResync{
			EventMeta: simplevent.EventMeta{
				Type: bridgev2.RemoteEventChatResync,
				LogContext: func(c zerolog.Context) zerolog.Context {
					return c.
						Str("portal_key", thread.EntityUrn)
				},
				PortalKey:    lc.MakePortalKey(thread),
				CreatePortal: true,
			},
			ChatInfo:        lc.ConversationToChatInfo(&thread),
			LatestMessageTS: time.UnixMilli(messages[len(messages)-1].DeliveredAt),
		}
		lc.connector.br.QueueRemoteEvent(lc.userLogin, evt)

		// drop initial message(s)
		for _, message := range thread.MessageElements.Messages {
			sender := message.Sender
			isFromMe := sender.HostIdentityUrn == string(lc.userLogin.ID)

			msgEvt := &simplevent.Message[*response.MessageElement]{
				EventMeta: simplevent.EventMeta{
					Type: bridgev2.RemoteEventMessage,
					LogContext: func(c zerolog.Context) zerolog.Context {
						return c.
							Str("message_id", message.EntityUrn).
							Str("sender", sender.HostIdentityUrn).
							Str("sender_login", path.Base(sender.ParticipantType.Member.ProfileURL)).
							Bool("is_from_me", isFromMe)
					},
					PortalKey:    lc.MakePortalKey(thread),
					CreatePortal: false,
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
			}
			lc.connector.br.QueueRemoteEvent(lc.userLogin, msgEvt)
		}
	}
}
