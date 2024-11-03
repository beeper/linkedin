package connector

import (
	"context"
	"fmt"
	"sort"
	"time"

	"github.com/rs/zerolog"
	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/simplevent"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/query"
)

func (lc *LinkedInClient) syncChannels(ctx context.Context) {
	log := zerolog.Ctx(ctx)

	getThreadsVariables := query.GetThreadsVariables{
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
	hasMore := true

	// loop until no more threads can be found
	for hasMore == true {
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
	}

	for _, thread := range threads {
		messages := thread.MessageElements.Messages
		sort.Slice(messages, func(j, i int) bool {
			return messages[j].DeliveredAt < messages[i].DeliveredAt
		})

		latestMessage := messages[len(messages)-1]
		latestMessageTS := time.UnixMilli(latestMessage.DeliveredAt)

		for _, participant := range thread.ConversationParticipants {
			if member, _ := lc.userCache[participant.HostIdentityUrn]; member.Type != "" {
				continue
			}
			lc.userCache[participant.HostIdentityUrn] = participant.ParticipantType.Member
		}

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
			LatestMessageTS: latestMessageTS,
		}
		lc.connector.br.QueueRemoteEvent(lc.userLogin, evt)
	}
}
