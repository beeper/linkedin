package connector

import (
	"context"
	"sort"
	"strconv"

	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/networkid"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/query"
)

var _ bridgev2.BackfillingNetworkAPI = (*LinkedInClient)(nil)

func (lc *LinkedInClient) FetchMessages(ctx context.Context, params bridgev2.FetchMessagesParams) (*bridgev2.FetchMessagesResponse, error) {
	conversationUrn := string(params.Portal.PortalKey.ID)

	variables := query.FetchMessagesVariables{
		ConversationUrn: conversationUrn,
		CountBefore:     int64(params.Count),
	}

	if params.Cursor == "" {
		variables.DeliveredAt = params.AnchorMessage.Timestamp.UnixMilli()
	} else {
		cursorInt, err := strconv.Atoi(string(params.Cursor))
		if err != nil {
			return nil, err
		}
		variables.DeliveredAt = int64(cursorInt)
	}

	fetchMessages, err := lc.client.FetchMessages(variables)
	if err != nil {
		return nil, err
	}

	messages := fetchMessages.Messages
	sort.Slice(messages, func(j, i int) bool {
		return messages[j].DeliveredAt < messages[i].DeliveredAt
	})

	if err != nil {
		return nil, err
	}

	backfilledMessages, err := lc.MessagesToBackfillMessages(ctx, messages, params.Portal) // get convo by id property missing
	if err != nil {
		return nil, err
	}

	fetchMessagesResp := &bridgev2.FetchMessagesResponse{
		Messages: backfilledMessages,
		Cursor:   networkid.PaginationCursor(messages[0].DeliveredAt),
		HasMore:  len(messages) >= params.Count,
		Forward:  params.Forward,
	}

	return fetchMessagesResp, nil
}
