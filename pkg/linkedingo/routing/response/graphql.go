package response

import "encoding/json"

type GraphQlResponse struct {
	Data GraphQLData `json:"data,omitempty"`
}

type GraphQLData struct {
	RecipeType                        string                          `json:"_recipeType,omitempty"`
	Type                              string                          `json:"_type,omitempty"`
	MessengerConversationsBySyncToken *MessengerConversationsResponse `json:"messengerConversationsBySyncToken,omitempty"`
	MessengerConversationsByCategory  *MessengerConversationsResponse `json:"messengerConversationsByCategory,omitempty"`

	MessengerMessagesBySyncToken                    *MessengerMessagesResponse                               `json:"messengerMessagesBySyncToken,omitempty"`
	MessengerMessagesByAnchorTimestamp              *MessengerMessagesResponse                               `json:"messengerMessagesByAnchorTimestamp,omitempty"`
	MessengerMessagesByConversation                 *MessengerMessagesResponse                               `json:"messengerMessagesByConversation,omitempty"`
	MessengerMessagingParticipantsByMessageAndEmoji *MessengerMessagingParticipantsByMessageAndEmojiResponse `json:"messengerMessagingParticipantsByMessageAndEmoji,omitempty"`
}

func (r GraphQlResponse) Decode(data []byte) (any, error) {
	respData := &GraphQlResponse{}
	return respData, json.Unmarshal(data, &respData)
}
