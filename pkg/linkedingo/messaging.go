package linkedingo

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"

	"github.com/beeper/linkedin/pkg/linkedingo/methods"
	"github.com/beeper/linkedin/pkg/linkedingo/routing"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/payload"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/query"
	"github.com/beeper/linkedin/pkg/linkedingo/types"

	"github.com/google/uuid"
)

// u dont have to pass mailboxUrn if u don't want to
// library will automatically set it for you
func (c *Client) GetThreads(variables query.GetThreadsVariables) (*response.MessengerConversationsResponse, error) {
	if variables.MailboxUrn == "" {
		variables.MailboxUrn = c.pageLoader.CurrentUser.FsdProfileID
	}

	withCursor := variables.LastUpdatedBefore != 0 && variables.NextCursor != ""
	var queryId types.GraphQLQueryIDs
	if withCursor {
		queryId = types.GRAPHQL_QUERY_ID_MESSENGER_CONVERSATIONS_WITH_CURSOR
	} else if variables.SyncToken != "" {
		queryId = types.GRAPHQL_QUERY_ID_MESSENGER_CONVERSATIONS_WITH_SYNC_TOKEN
	} else {
		queryId = types.GRAPHQL_QUERY_ID_MESSENGER_CONVERSATIONS
	}

	variablesQuery, err := variables.Encode()
	if err != nil {
		return nil, err
	}

	threadQuery := query.GraphQLQuery{
		QueryID:   queryId,
		Variables: string(variablesQuery),
	}

	_, respData, err := c.MakeRoutingRequest(routing.VOYAGER_MESSAGING_GRAPHQL_URL, nil, &threadQuery)
	if err != nil {
		return nil, err
	}

	graphQLResponse, ok := respData.(*response.GraphQlResponse)
	if !ok || graphQLResponse == nil {
		return nil, newErrorResponseTypeAssertFailed("*response.GraphQlResponse")
	}

	graphQLResponseData := graphQLResponse.Data
	if withCursor {
		return graphQLResponseData.MessengerConversationsByCategory, nil
	}

	return graphQLResponseData.MessengerConversationsBySyncToken, nil
}

func (c *Client) FetchMessages(variables query.FetchMessagesVariables) (*response.MessengerMessagesResponse, error) {
	withCursor := variables.PrevCursor != ""
	withAnchorTimestamp := variables.DeliveredAt != 0

	var queryId types.GraphQLQueryIDs
	if withCursor {
		queryId = types.GRAPHQL_QUERY_ID_MESSENGER_MESSAGES_BY_CONVERSATION
	} else if withAnchorTimestamp {
		queryId = types.GRAPHQL_QUERY_ID_MESSENGER_MESSAGES_BY_ANCHOR_TIMESTAMP
	} else {
		queryId = types.GRAPHQL_QUERY_ID_MESSENGER_MESSAGES_BY_SYNC_TOKEN
	}

	variablesQuery, err := variables.Encode()
	if err != nil {
		return nil, err
	}
	messagesQuery := query.GraphQLQuery{
		QueryID:   queryId,
		Variables: string(variablesQuery),
	}

	_, respData, err := c.MakeRoutingRequest(routing.VOYAGER_MESSAGING_GRAPHQL_URL, nil, &messagesQuery)
	if err != nil {
		return nil, err
	}

	graphQLResponse, ok := respData.(*response.GraphQlResponse)
	if !ok || graphQLResponse == nil {
		return nil, newErrorResponseTypeAssertFailed("*response.GraphQlResponse")
	}

	graphQLResponseData := graphQLResponse.Data
	if withCursor {
		return graphQLResponseData.MessengerMessagesByConversation, nil
	} else if withAnchorTimestamp {
		return graphQLResponseData.MessengerMessagesByAnchorTimestamp, nil
	}

	return graphQLResponseData.MessengerMessagesBySyncToken, nil
}

func (c *Client) EditMessage(messageUrn string, p payload.MessageBody) error {
	editMessageUrl := fmt.Sprintf("%s/%s", routing.VOYAGER_MESSAGING_DASH_MESSENGER_MESSAGES_URL, url.QueryEscape(messageUrn))

	headerOpts := types.HeaderOpts{
		WithCookies:         true,
		WithCsrfToken:       true,
		Origin:              string(routing.BASE_URL),
		WithXLiTrack:        true,
		WithXLiProtocolVer:  true,
		WithXLiPageInstance: true,
		WithXLiLang:         true,
		Extra:               map[string]string{"accept": string(types.JSON)},
	}
	headers := c.buildHeaders(headerOpts)

	editMessagePayload := payload.GraphQLPatchBody{
		Patch: payload.Patch{
			Set: payload.Set{
				Body: p,
			},
		},
	}

	payloadBytes, err := editMessagePayload.Encode()
	if err != nil {
		return err
	}

	resp, respBody, err := c.MakeRequest(editMessageUrl, http.MethodPost, headers, payloadBytes, types.PLAINTEXT_UTF8)
	if err != nil {
		return err
	}

	if resp.StatusCode > 204 {
		return fmt.Errorf("failed to edit message with urn %s (statusCode=%d, response_body=%s)", messageUrn, resp.StatusCode, string(respBody))
	}

	return nil
}

// function will set mailboxUrn, originToken and trackingId automatically IF it is empty
// so you do not have to set it if u dont want to
func (c *Client) SendMessage(p payload.SendMessagePayload) (*response.MessageSentResponse, error) {
	actionQuery := query.DoActionQuery{
		Action: query.ACTION_CREATE_MESSAGE,
	}

	if p.MailboxUrn == "" {
		p.MailboxUrn = c.pageLoader.CurrentUser.FsdProfileID
	}

	if p.TrackingID == "" {
		p.TrackingID = methods.GenerateTrackingId()
	}

	if p.Message.OriginToken == "" {
		p.Message.OriginToken = uuid.NewString()
	}

	resp, respData, err := c.MakeRoutingRequest(routing.VOYAGER_MESSAGING_DASH_MESSENGER_MESSAGES_URL, p, actionQuery)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode > 204 {
		return nil, fmt.Errorf("failed to send message to conversation with urn %s (statusCode=%d)", p.Message.ConversationUrn, resp.StatusCode)
	}

	messageSentResponse, ok := respData.(*response.MessageSentResponse)
	if !ok {
		return nil, newErrorResponseTypeAssertFailed("*response.MessageSentResponse")
	}

	return messageSentResponse, nil
}

func (c *Client) StartTyping(conversationUrn string) error {
	actionQuery := query.DoActionQuery{
		Action: query.ACTION_TYPING,
	}

	typingPayload := payload.StartTypingPayload{
		ConversationUrn: conversationUrn,
	}

	resp, _, err := c.MakeRoutingRequest(routing.VOYAGER_MESSAGING_DASH_MESSENGER_CONVERSATIONS_URL, typingPayload, actionQuery)
	if err != nil {
		return err
	}

	if resp.StatusCode > 204 {
		return fmt.Errorf("failed to start typing in conversation with urn %s (statusCode=%d)", conversationUrn, resp.StatusCode)
	}

	return nil
}

func (c *Client) DeleteMessage(messageUrn string) error {
	actionQuery := query.DoActionQuery{
		Action: query.ACTION_RECALL,
	}

	deleteMsgPayload := payload.DeleteMessagePayload{
		MessageUrn: messageUrn,
	}

	resp, _, err := c.MakeRoutingRequest(routing.VOYAGER_MESSAGING_DASH_MESSENGER_MESSAGES_URL, deleteMsgPayload, actionQuery)
	if err != nil {
		return err
	}

	if resp.StatusCode > 204 {
		return fmt.Errorf("failed to delete message with message urn %s (statusCode=%d)", messageUrn, resp.StatusCode)
	}

	return nil
}

// this endpoint allows you to mark multiple threads as read/unread at a time
// pass false to second arg to unread all conversations and true to read all of them
func (c *Client) MarkThreadRead(conversationUrns []string, read bool) (*response.MarkThreadReadResponse, error) {
	queryUrnValues := ""
	entities := make(map[string]payload.GraphQLPatchBody, 0)
	for i, convUrn := range conversationUrns {
		if i >= len(conversationUrns)-1 {
			queryUrnValues += url.QueryEscape(convUrn)
		} else {
			queryUrnValues += url.QueryEscape(convUrn) + ","
		}
		entities[convUrn] = payload.GraphQLPatchBody{
			Patch: payload.Patch{
				Set: payload.MarkThreadReadBody{
					Read: read,
				},
			},
		}
	}

	queryStr := fmt.Sprintf("ids=List(%s)", queryUrnValues)
	markReadUrl := fmt.Sprintf("%s?%s", routing.VOYAGER_MESSAGING_DASH_MESSENGER_CONVERSATIONS_URL, queryStr)
	patchEntitiesPayload := payload.PatchEntitiesPayload{
		Entities: entities,
	}

	payloadBytes, err := patchEntitiesPayload.Encode()
	if err != nil {
		return nil, err
	}

	headerOpts := types.HeaderOpts{
		WithCookies:         true,
		WithCsrfToken:       true,
		Origin:              string(routing.BASE_URL),
		WithXLiTrack:        true,
		WithXLiProtocolVer:  true,
		WithXLiPageInstance: true,
		WithXLiLang:         true,
		Extra:               map[string]string{"accept": string(types.JSON)},
	}

	headers := c.buildHeaders(headerOpts)
	resp, respBody, err := c.MakeRequest(markReadUrl, http.MethodPost, headers, payloadBytes, types.PLAINTEXT_UTF8)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode > 204 {
		return nil, fmt.Errorf("failed to read conversations... (statusCode=%d)", resp.StatusCode)
	}

	result := &response.MarkThreadReadResponse{}
	return result, json.Unmarshal(respBody, result)
}

func (c *Client) DeleteConversation(conversationUrn string) error {
	deleteConvUrl := fmt.Sprintf("%s/%s", routing.VOYAGER_MESSAGING_DASH_MESSENGER_CONVERSATIONS_URL, url.QueryEscape(conversationUrn))

	headers := c.buildHeaders(types.HeaderOpts{
		WithCookies:         true,
		WithCsrfToken:       true,
		WithXLiTrack:        true,
		WithXLiPageInstance: true,
		WithXLiLang:         true,
		WithXLiProtocolVer:  true,
		Origin:              string(routing.BASE_URL),
		Extra: map[string]string{
			"accept": string(types.GRAPHQL),
		},
	})

	resp, _, err := c.MakeRequest(deleteConvUrl, http.MethodDelete, headers, nil, types.NONE)
	if err != nil {
		return err
	}

	if resp.StatusCode > 204 {
		return fmt.Errorf("failed to delete conversation with conversation urn %s (statusCode=%d)", conversationUrn, resp.StatusCode)
	}

	return nil
}

// pass true to second arg to react and pass false to unreact
func (c *Client) SendReaction(p payload.SendReactionPayload, react bool) error {
	action := query.ACTION_REACT_WITH_EMOJI
	if !react {
		action = query.ACTION_UNREACT_WITH_EMOJI
	}
	actionQuery := query.DoActionQuery{
		Action: action,
	}

	resp, _, err := c.MakeRoutingRequest(routing.VOYAGER_MESSAGING_DASH_MESSENGER_MESSAGES_URL, p, actionQuery)
	if err != nil {
		return err
	}

	if resp.StatusCode > 204 {
		return fmt.Errorf("failed to perform reaction with emoji %s on message with urn %s (statusCode=%d)", p.Emoji, p.MessageUrn, resp.StatusCode)
	}

	return nil
}

func (c *Client) GetReactionsForEmoji(vars query.GetReactionsForEmojiVariables) ([]types.ConversationParticipant, error) {
	variablesQuery, err := vars.Encode()
	if err != nil {
		return nil, err
	}

	gqlQuery := query.GraphQLQuery{
		QueryID:   "messengerMessagingParticipants.3d2e0e93494e9dbf4943dc19da98bdf6",
		Variables: string(variablesQuery),
	}

	_, respData, err := c.MakeRoutingRequest(routing.VOYAGER_MESSAGING_GRAPHQL_URL, nil, &gqlQuery)
	if err != nil {
		return nil, err
	}

	graphQLResponse, ok := respData.(*response.GraphQlResponse)
	if !ok || graphQLResponse == nil {
		return nil, newErrorResponseTypeAssertFailed("*response.GraphQlResponse")
	}

	graphQLResponseData := graphQLResponse.Data

	return graphQLResponseData.MessengerMessagingParticipantsByMessageAndEmoji.Participants, nil
}
