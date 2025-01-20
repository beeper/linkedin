package types

type GraphQLQueryIDs string

const (
	GraphQLQueryIDMessengerConversations              GraphQLQueryIDs = "messengerConversations.95e0a4b80fbc6bc53550e670d34d05d9"
	GraphQLQueryIDMessengerConversationsWithCursor    GraphQLQueryIDs = "messengerConversations.18240d6a3ac199067a703996eeb4b163"
	GraphQLQueryIDMessengerConversationsWithSyncToken GraphQLQueryIDs = "messengerConversations.be2479ed77df3dd407dd90efc8ac41de"
	GraphQLQueryIDMessengerMessagesBySyncToken        GraphQLQueryIDs = "messengerMessages.d1b494ac18c24c8be71ea07b5bd1f831"
	GraphQLQueryIDMessengerMessagesByAnchorTimestamp  GraphQLQueryIDs = "messengerMessages.b52340f92136e74c2aab21dac7cf7ff2"
	GraphQLQueryIDMessengerMessagesByConversation     GraphQLQueryIDs = "messengerMessages.86ca573adc64110d94d8bce89c5b2f3b"
)
