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
		queryId = types.GraphQLQueryIDMessengerConversationsWithCursor
	} else if variables.SyncToken != "" {
		queryId = types.GraphQLQueryIDMessengerConversationsWithSyncToken
	} else {
		queryId = types.GraphQLQueryIDMessengerConversations
	}

	variablesQuery, err := variables.Encode()
	if err != nil {
		return nil, err
	}

	threadQuery := query.GraphQLQuery{
		QueryID:   queryId,
		Variables: string(variablesQuery),
	}

	_, respData, err := c.MakeRoutingRequest(routing.LinkedInVoyagerMessagingGraphQLURL, nil, &threadQuery)
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
		queryId = types.GraphQLQueryIDMessengerMessagesByConversation
	} else if withAnchorTimestamp {
		queryId = types.GraphQLQueryIDMessengerMessagesByAnchorTimestamp
	} else {
		queryId = types.GraphQLQueryIDMessengerMessagesBySyncToken
	}

	variablesQuery, err := variables.Encode()
	if err != nil {
		return nil, err
	}
	messagesQuery := query.GraphQLQuery{
		QueryID:   queryId,
		Variables: string(variablesQuery),
	}

	_, respData, err := c.MakeRoutingRequest(routing.LinkedInVoyagerMessagingGraphQLURL, nil, &messagesQuery)
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
	editMessageUrl := fmt.Sprintf("%s/%s", routing.LinkedInVoyagerMessagingDashMessengerMessagesURL, url.QueryEscape(messageUrn))

	headerOpts := types.HeaderOpts{
		WithCookies:         true,
		WithCsrfToken:       true,
		Origin:              string(routing.LinkedInBaseURL),
		WithXLiTrack:        true,
		WithXLiProtocolVer:  true,
		WithXLiPageInstance: true,
		WithXLiLang:         true,
		Extra:               map[string]string{"accept": string(types.ContentTypeJSON)},
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

	resp, respBody, err := c.MakeRequest(editMessageUrl, http.MethodPost, headers, payloadBytes, types.ContentTypePlaintextUTF8)
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
		Action: query.ActionCreateMessage,
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

	resp, respData, err := c.MakeRoutingRequest(routing.LinkedInVoyagerMessagingDashMessengerMessagesURL, p, actionQuery)
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
		Action: query.ActionTyping,
	}

	typingPayload := payload.StartTypingPayload{
		ConversationUrn: conversationUrn,
	}

	resp, _, err := c.MakeRoutingRequest(routing.LinkedInMessagingDashMessengerConversationsURL, typingPayload, actionQuery)
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
		Action: query.ActionRecall,
	}

	deleteMsgPayload := payload.DeleteMessagePayload{
		MessageUrn: messageUrn,
	}

	resp, _, err := c.MakeRoutingRequest(routing.LinkedInVoyagerMessagingDashMessengerMessagesURL, deleteMsgPayload, actionQuery)
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
	markReadUrl := fmt.Sprintf("%s?%s", routing.LinkedInMessagingDashMessengerConversationsURL, queryStr)
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
		Origin:              string(routing.LinkedInBaseURL),
		WithXLiTrack:        true,
		WithXLiProtocolVer:  true,
		WithXLiPageInstance: true,
		WithXLiLang:         true,
		Extra:               map[string]string{"accept": string(types.ContentTypeJSON)},
	}

	headers := c.buildHeaders(headerOpts)
	resp, respBody, err := c.MakeRequest(markReadUrl, http.MethodPost, headers, payloadBytes, types.ContentTypePlaintextUTF8)
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
	deleteConvUrl := fmt.Sprintf("%s/%s", routing.LinkedInMessagingDashMessengerConversationsURL, url.QueryEscape(conversationUrn))

	headers := c.buildHeaders(types.HeaderOpts{
		WithCookies:         true,
		WithCsrfToken:       true,
		WithXLiTrack:        true,
		WithXLiPageInstance: true,
		WithXLiLang:         true,
		WithXLiProtocolVer:  true,
		Origin:              string(routing.LinkedInBaseURL),
		Extra: map[string]string{
			"accept": string(types.ContentTypeGraphQL),
		},
	})

	resp, _, err := c.MakeRequest(deleteConvUrl, http.MethodDelete, headers, nil, "")
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
	action := query.ActionReactWithEmoji
	if !react {
		action = query.ActionUnreactWithEmoji
	}
	actionQuery := query.DoActionQuery{
		Action: action,
	}

	resp, _, err := c.MakeRoutingRequest(routing.LinkedInVoyagerMessagingDashMessengerMessagesURL, p, actionQuery)
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

	_, respData, err := c.MakeRoutingRequest(routing.LinkedInVoyagerMessagingGraphQLURL, nil, &gqlQuery)
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
