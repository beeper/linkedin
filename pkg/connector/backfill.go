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
		CountBefore:     20,
	}

	if params.Cursor == "" {
		if params.AnchorMessage != nil {
			variables.DeliveredAt = params.AnchorMessage.Timestamp.UnixMilli()
		}
	} else {
		var err error
		variables.DeliveredAt, err = strconv.ParseInt(string(params.Cursor), 10, 64)
		if err != nil {
			return nil, err
		}
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

	backfilledMessages := make([]*bridgev2.BackfillMessage, len(messages))
	cursor := networkid.PaginationCursor("")
	if len(messages) > 0 {
		cursor = networkid.PaginationCursor(strconv.FormatInt(messages[0].DeliveredAt, 10))

		backfilledMessages, err = lc.MessagesToBackfillMessages(ctx, messages, params.Portal)
		if err != nil {
			return nil, err
		}
	}

	fetchMessagesResp := &bridgev2.FetchMessagesResponse{
		Messages: backfilledMessages,
		Cursor:   cursor,
		HasMore:  len(messages) >= 20,
		Forward:  params.Forward,
	}

	return fetchMessagesResp, nil
}
